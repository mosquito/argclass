"""Default value parsers for loading configuration from files."""

import ast
import configparser
import json
import os
from abc import ABC, abstractmethod
from enum import IntEnum
from pathlib import Path
from typing import Any
from collections.abc import Iterable, Mapping

from .exceptions import ConfigurationError
from .types import TEXT_TRUE_VALUES
from .utils import own_section_items

try:
    import tomllib

    toml_load = tomllib.load
except ImportError:  # pragma: no cover
    try:
        import tomli  # type: ignore[import-not-found]

        toml_load = tomli.load  # type: ignore[assignment]
    except ImportError:
        toml_load = None  # type: ignore[assignment]


class ValueKind(IntEnum):
    """Expected value type for config loading."""

    STRING = 0  # Default, no conversion
    SEQUENCE = 1  # list/tuple or something iterable
    BOOL = 2  # boolean value


class UnexpectedConfigValue(ConfigurationError):
    """Config value doesn't match expected type."""

    def __init__(self, key: str, expected: ValueKind, value: Any):
        self.value = repr(value)
        self.expected = expected
        self.key = key  # Backward compatibility alias
        super().__init__(
            f"expected {expected.name}, "
            f"got {type(value).__name__}: {self.value}",
            field_name=key,
            hint=f"Provide a value of type {expected.name}",
        )


class AbstractDefaultsParser(ABC):
    """Abstract base class for parsing configuration files into defaults.

    Subclass this to implement custom configuration file formats for
    the `config_files` parameter of Parser.
    """

    def __init__(
        self,
        paths: Iterable[str | Path],
        strict: bool = False,
    ):
        self._paths = list(paths)
        self._strict = strict
        self._loaded_files: tuple[Path, ...] = ()
        self._values: dict[str, Any] = {}

    @property
    def loaded_files(self) -> tuple[Path, ...]:
        """Return tuple of successfully loaded file paths."""
        return self._loaded_files

    def _filter_readable_paths(self) -> list[Path]:
        """Filter paths to only include readable, existing files."""
        result = []
        for path in self._paths:
            path_obj = Path(path).expanduser().resolve()
            if os.access(path_obj, os.R_OK) and path_obj.exists():
                result.append(path_obj)
        return result

    @abstractmethod
    def parse(self) -> Mapping[str, Any]:
        """Parse configuration files and return defaults mapping.

        Returns:
            A mapping where keys are argument names or group names,
            and values are either default values (str) or nested
            mappings for groups.
        """
        raise NotImplementedError()

    def get_value(
        self,
        key: str,
        kind: ValueKind = ValueKind.STRING,
        section: str | None = None,
    ) -> Any:
        """Get value with type validation.

        The ``section`` argument may contain dots to address nested
        groups (e.g. ``"endpoint.credentials"``). Resolution tries a
        literal key match first (so INI section names with dots work),
        then falls back to splitting on ``.`` and descending through
        nested dicts (JSON/TOML).

        Args:
            key: The config key name.
            kind: Expected value type for validation.
            section: Optional section/group name for nested values.

        Returns:
            The value, converted if necessary (e.g., INI literal_eval).

        Raises:
            UnexpectedConfigValue: If value doesn't match expected kind.
        """
        if section is not None:
            source: Any = self._values.get(section)
            if not isinstance(source, dict):
                source = self._values
                for part in section.split("."):
                    if not isinstance(source, dict):
                        return None
                    source = source.get(part)
                    if source is None:
                        return None
                if not isinstance(source, dict):
                    return None
        else:
            source = self._values

        value = source.get(key)
        if value is None:
            return None

        # Subclass can convert (INI: literal_eval)
        value = self._convert(key, value, kind)

        # Validate
        if kind == ValueKind.SEQUENCE:
            if not isinstance(value, (list, tuple)):
                raise UnexpectedConfigValue(key, kind, value)
        elif kind == ValueKind.BOOL:
            if not isinstance(value, bool):
                raise UnexpectedConfigValue(key, kind, value)

        return value

    def _convert(self, key: str, value: Any, kind: ValueKind) -> Any:
        """Override for format-specific conversion."""
        return value


class INIDefaultsParser(AbstractDefaultsParser):
    """Parse INI configuration files for default values.

    This is the default parser used by argclass. It uses Python's
    configparser module to read INI files.

    INI sections map to argument groups, and the [DEFAULT] section
    contains top-level argument defaults.

    Values that look like Python literals (lists, bools) are converted
    when requested via get_value() with appropriate ValueKind.
    """

    # Values considered as True for boolean conversion. Aliased to the
    # shared constant so this set and ``argclass.parse_bool`` cannot
    # drift apart; kept as a class attribute so subclasses can still
    # override it.
    BOOL_TRUE_VALUES = TEXT_TRUE_VALUES

    def parse(self) -> Mapping[str, Any]:
        parser = configparser.ConfigParser(
            allow_no_value=True,
            strict=self._strict,
        )

        loaded: list[Path] = []
        for path in self._filter_readable_paths():
            # Mirror the JSON/TOML parsers: in non-strict mode a
            # malformed file is skipped (best effort), in strict mode
            # the error propagates.
            try:
                read_ok = parser.read([path])
            except (configparser.Error, OSError):
                if self._strict:
                    raise
                continue
            loaded.extend(Path(f) for f in read_ok)
        self._loaded_files = tuple(loaded)

        result: dict[str, Any] = dict(
            parser.items(parser.default_section, raw=True),
        )
        for section in parser.sections():
            result[section] = own_section_items(parser, section)

        self._values = result
        return result

    def _convert(self, key: str, value: Any, kind: ValueKind) -> Any:
        """Convert INI string values based on expected kind."""
        if not isinstance(value, str):
            return value

        if kind == ValueKind.SEQUENCE:
            try:
                return ast.literal_eval(value)
            except (ValueError, SyntaxError) as e:
                raise UnexpectedConfigValue(key, kind, value) from e

        if kind == ValueKind.BOOL:
            return value.lower() in self.BOOL_TRUE_VALUES

        return value


class JSONDefaultsParser(AbstractDefaultsParser):
    """Parse JSON configuration files for default values.

    The JSON structure should be a flat or nested object where:
    - Top-level keys are argument names or group names
    - Group values are objects with argument names as keys

    JSON natively supports lists and booleans, so no conversion needed.
    """

    def parse(self) -> Mapping[str, Any]:
        result: dict[str, Any] = {}
        loaded_files = []

        for path in self._filter_readable_paths():
            try:
                with path.open("r") as fp:
                    data = json.load(fp)
                    if isinstance(data, dict):
                        result.update(data)
                        loaded_files.append(path)
            except (json.JSONDecodeError, OSError):
                if self._strict:
                    raise

        self._loaded_files = tuple(loaded_files)
        self._values = result
        return result


class TOMLDefaultsParser(AbstractDefaultsParser):
    """Parse TOML configuration files for default values.

    Uses stdlib tomllib (Python 3.11+) or tomli package as fallback.

    The TOML structure should be:
    - Top-level keys are argument names
    - Tables (sections) map to argument groups

    TOML natively supports lists and booleans, so no conversion needed.
    """

    def parse(self) -> Mapping[str, Any]:
        if toml_load is None:
            raise RuntimeError(
                "TOML support requires Python 3.11+ (tomllib) "
                "or 'tomli' package: pip install tomli"
            )

        result: dict[str, Any] = {}
        loaded_files = []

        for path in self._filter_readable_paths():
            try:
                with path.open("rb") as fp:
                    data = toml_load(fp)
                    if isinstance(data, dict):
                        result.update(data)
                        loaded_files.append(path)
            # TOMLDecodeError subclasses ValueError in both stdlib
            # tomllib and the tomli fallback, so a malformed file is
            # skipped in non-strict mode just like JSON/INI.
            except (OSError, ValueError):
                if self._strict:
                    raise

        self._loaded_files = tuple(loaded_files)
        self._values = result
        return result
