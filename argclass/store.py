"""Store metaclass and argument classes for argclass."""

import builtins
import collections
from argparse import Action
from pathlib import Path
from types import MappingProxyType
from typing import (
    Any,
)
from collections.abc import Iterable, Iterator, Mapping

from .actions import (
    ConfigAction,
    INIConfigAction,
    JSONConfigAction,
    TOMLConfigAction,
)
from .types import Actions, ConverterType, Nargs
from .utils import resolve_annotations


class StoreMeta(type):
    """Metaclass that collects and merges annotations from base classes."""

    def __new__(
        mcs,
        name: str,
        bases: tuple[type["StoreMeta"], ...],
        attrs: dict[str, Any],
    ) -> "StoreMeta":
        # Create the class first to ensure annotations are available
        # Python 3.14+ (PEP 649) defers annotation evaluation
        cls = super().__new__(mcs, name, bases, attrs)

        annotations = resolve_annotations(cls)
        setattr(cls, "__annotations__", annotations)
        setattr(
            cls,
            "_fields",
            tuple(
                filter(
                    lambda x: not x.startswith("_"),
                    annotations.keys(),
                ),
            ),
        )
        return cls


class Store(metaclass=StoreMeta):
    """Base class for typed storage with field validation."""

    _default_value = object()
    _fields: tuple[str, ...]

    def __new__(cls, **kwargs: Any) -> "Store":
        obj = super().__new__(cls)

        type_map: dict[str, tuple[type, Any]] = {}
        # Use cls.__annotations__ instead of obj.__annotations__ to avoid
        # triggering __getattr__ before _values is initialized (Python 3.14+)
        for key, value in cls.__annotations__.items():
            if key.startswith("_"):
                continue
            type_map[key] = (value, getattr(cls, key, cls._default_value))

        for key, (value_type, default) in type_map.items():
            if default is cls._default_value and key not in kwargs:
                raise TypeError(f"required argument {key!r} must be passed")
            value = kwargs.get(key, default)
            setattr(obj, key, value)
        return obj

    def copy(self, **overrides: Any) -> Any:
        kwargs = self.as_dict()
        for key, value in overrides.items():
            kwargs[key] = value
        return self.__class__(**kwargs)

    def as_dict(self) -> dict[str, Any]:
        # noinspection PyProtectedMember
        return {field: getattr(self, field) for field in self._fields}

    def __repr__(self) -> str:
        items = sorted(self.as_dict().items())
        values = ", ".join([f"{k!s}={v!r}" for k, v in items])
        return f"<{self.__class__.__name__}: {values}>"


class ArgumentBase(Store):
    """Base class for argument definitions."""

    def __init__(self, **kwargs: Any):
        self._values = collections.OrderedDict()

        # noinspection PyUnresolvedReferences
        for key in self._fields:
            self._values[key] = kwargs.get(key, getattr(self.__class__, key))

    def __getattr__(self, item: str) -> Any:
        try:
            return self._values[item]
        except KeyError as e:
            raise AttributeError from e

    @property
    def is_positional(self) -> bool:
        for alias in self.aliases:
            if alias.startswith("-"):
                return False
        return True

    def get_kwargs(self) -> dict[str, Any]:
        nargs = self.nargs
        if isinstance(nargs, Nargs):
            nargs = nargs.value

        action = self.action
        kwargs = self.as_dict()

        if action in (
            Actions.STORE_TRUE,
            Actions.STORE_FALSE,
            Actions.COUNT,
            Actions.HELP,
            Actions.VERSION,
        ):
            kwargs.pop("type", None)

        if isinstance(action, Actions):
            action = action.value

        extra_kwargs = kwargs.pop("extra_kwargs")
        kwargs.pop("aliases", None)
        kwargs.pop("converter", None)
        kwargs.pop("env_var", None)
        kwargs.pop("secret", None)
        kwargs.update(action=action, nargs=nargs)

        result = {k: v for k, v in kwargs.items() if v is not None}
        result.update(extra_kwargs)
        return result


class TypedArgument(ArgumentBase):
    """Argument with type information."""

    # ``builtins.type`` because the ``type`` field below shadows the
    # builtin in this class's annotation scope (matters on 3.14/PEP 649).
    action: Actions | builtins.type[Action] = Actions.default()
    aliases: Iterable[str] = frozenset()
    choices: Iterable[str] | None = None
    const: Any | None = None
    converter: ConverterType | None = None
    default: Any | None = None
    secret: bool = False
    env_var: str | None = None
    extra_kwargs: Mapping[str, Any] = MappingProxyType({})
    help: str | None = None
    metavar: str | None = None
    nargs: int | Nargs | None = None
    required: bool | None = None
    type: Any = None

    @property
    def is_nargs(self) -> bool:
        if self.nargs is None:
            return False
        if isinstance(self.nargs, int):
            return self.nargs > 1
        return True

    @property
    def has_default(self) -> bool:
        """Check if the argument has a meaningful default value.

        Returns False if default is None or Ellipsis
        (the "no default" sentinel).
        """
        return self.default is not None and self.default is not ...


class ConfigArgument(TypedArgument):
    """Argument for configuration file loading."""

    search_paths: Iterable[Path | str] | None = None
    action: builtins.type[ConfigAction]


class INIConfig(ConfigArgument):
    """Parse INI file and set results as a value."""

    action: builtins.type[ConfigAction] = INIConfigAction


class JSONConfig(ConfigArgument):
    """Parse JSON file and set results as a value."""

    action: builtins.type[ConfigAction] = JSONConfigAction


class TOMLConfig(ConfigArgument):
    """Parse TOML file and set results as a value.

    Uses stdlib tomllib (Python 3.11+) or tomli package as fallback.
    """

    action: builtins.type[ConfigAction] = TOMLConfigAction


class AbstractGroup:
    """Abstract base for argument groups."""

    pass


class AbstractParser:
    """Abstract base for parsers."""

    __parent__: "AbstractParser | None" = None
    current_subparsers: tuple["AbstractParser", ...] = ()

    def _get_chain(self) -> Iterator["AbstractParser"]:
        yield self
        if self.__parent__ is None:
            return
        yield from self.__parent__._get_chain()

    def __call__(self) -> Any:
        raise NotImplementedError()
