"""Default value parsers for loading configuration from files."""

import configparser
import json
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Tuple, Union

try:
    import tomllib

    toml_load = tomllib.load
except ImportError:  # pragma: no cover
    try:
        import tomli  # type: ignore[import-not-found]

        toml_load = tomli.load  # type: ignore[assignment]
    except ImportError:
        toml_load = None  # type: ignore[assignment]


class AbstractDefaultsParser(ABC):
    """Abstract base class for parsing configuration files into defaults.

    Subclass this to implement custom configuration file formats for
    the `config_files` parameter of Parser.
    """

    def __init__(
        self,
        paths: Iterable[Union[str, Path]],
        strict: bool = False,
    ):
        self._paths = list(paths)
        self._strict = strict
        self._loaded_files: Tuple[Path, ...] = ()

    @property
    def loaded_files(self) -> Tuple[Path, ...]:
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


class INIDefaultsParser(AbstractDefaultsParser):
    """Parse INI configuration files for default values.

    This is the default parser used by argclass. It uses Python's
    configparser module to read INI files.

    INI sections map to argument groups, and the [DEFAULT] section
    contains top-level argument defaults.
    """

    def parse(self) -> Mapping[str, Any]:
        parser = configparser.ConfigParser(
            allow_no_value=True,
            strict=self._strict,
        )

        filenames = self._filter_readable_paths()
        loaded = parser.read(filenames)
        self._loaded_files = tuple(Path(f) for f in loaded)

        result: Dict[str, Any] = dict(
            parser.items(parser.default_section, raw=True),
        )

        for section in parser.sections():
            result[section] = dict(parser.items(section, raw=True))

        return result


class JSONDefaultsParser(AbstractDefaultsParser):
    """Parse JSON configuration files for default values.

    The JSON structure should be a flat or nested object where:
    - Top-level keys are argument names or group names
    - Group values are objects with argument names as keys
    """

    def parse(self) -> Mapping[str, Any]:
        result: Dict[str, Any] = {}
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
        return result


class TOMLDefaultsParser(AbstractDefaultsParser):
    """Parse TOML configuration files for default values.

    Uses stdlib tomllib (Python 3.11+) or tomli package as fallback.

    The TOML structure should be:
    - Top-level keys are argument names
    - Tables (sections) map to argument groups
    """

    def parse(self) -> Mapping[str, Any]:
        if toml_load is None:
            raise RuntimeError(
                "TOML support requires Python 3.11+ (tomllib) "
                "or 'tomli' package: pip install tomli"
            )

        result: Dict[str, Any] = {}
        loaded_files = []

        for path in self._filter_readable_paths():
            try:
                with path.open("rb") as fp:
                    data = toml_load(fp)
                    if isinstance(data, dict):
                        result.update(data)
                        loaded_files.append(path)
            except OSError:
                if self._strict:
                    raise

        self._loaded_files = tuple(loaded_files)
        return result
