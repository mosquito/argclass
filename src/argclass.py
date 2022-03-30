import argparse
import collections
import configparser
import logging
import os
from abc import ABCMeta
from argparse import ArgumentParser
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import (
    Any, Dict, Iterable, Mapping, NamedTuple, Optional, Sequence, Tuple, Type,
    TypeVar, Union,
)


T = TypeVar("T")


def read_config(*paths: Union[str, Path]) -> Dict[str, Any]:
    parser = configparser.ConfigParser()
    filenames = list(
        map(
            lambda p: p.resolve(),
            filter(
                lambda p: p.is_file(),
                map(Path, paths)
            )
        )
    )
    parser.read(filenames)

    result = dict(parser.items(parser.default_section, raw=True))
    for section in parser.sections():
        config = dict(parser.items(section, raw=True))
        result[section] = config

    return result


class ConfigAction(argparse.Action):
    def __init__(
        self, option_strings: Sequence[str], dest: str, search_paths=(),
        type: Type[MappingProxyType] = MappingProxyType({}), help: str = '',
        default: Any = None
    ):
        if not isinstance(type, MappingProxyType):
            raise ValueError("type must be MappingProxyType")
        super().__init__(
            option_strings, dest, type=Path, help=help, default=default
        )
        self.search_paths = list(map(Path, search_paths))
        self._result = None

    def __call__(self, parser, namespace, values, option_string=None):
        if not self._result:
            filenames = list(self.search_paths)
            if values is not None:
                filenames.insert(0, Path(values))
            self._result = read_config(*filenames)
        setattr(namespace, self.dest, MappingProxyType(self._result))


class Actions(str, Enum):
    APPEND = "append"
    APPEND_CONST = "append_const"
    COUNT = "count"
    EXTEND = "extend"
    HELP = "help"
    PARSERS = "parsers"
    STORE = "store"
    STORE_CONST = "store_const"
    STORE_FALSE = "store_true"
    STORE_TRUE = "store_true"
    VERSION = "version"

    @classmethod
    def default(cls):
        return cls.STORE


class Nargs(Enum):
    ANY = None
    ONE_OR_MORE = "+"
    OPTIONAL = "?"
    ZERO_OR_MORE = "*"

    @classmethod
    def default(cls):
        return cls.ANY


def deep_getattr(name, attrs: Dict[str, Any], *bases: Type) -> Any:
    if name in attrs:
        return attrs[name]
    for base in bases:
        if hasattr(base, name):
            return getattr(base, name)
    raise KeyError(f"Key {name} was not declared")


def merge_annotations(
    annotations: Dict[str, Any], *bases: Type
) -> Dict[str, Any]:
    result = {}

    for base in bases:
        result.update(getattr(base, "__annotations__", {}))
    result.update(annotations)
    return result


class StoreMeta(type):
    def __new__(mcs, name, bases, attrs: Dict[str, Any]):
        annotations = merge_annotations(
            attrs.get("__annotations__", {}), *bases
        )
        attrs["__annotations__"] = annotations
        attrs["_fields"] = tuple(annotations.keys())
        return super().__new__(mcs, name, bases, attrs)


class Store(metaclass=StoreMeta):
    _default_value = object()

    def __new__(cls, **kwargs):
        obj = super().__new__(cls)

        type_map: Dict[str, Tuple[Type, Any]] = {}
        for key, value in obj.__annotations__.items():
            type_map[key] = (value, getattr(obj, key, cls._default_value))

        for key, (value_type, default) in type_map.items():
            if default is cls._default_value and key not in kwargs:
                raise TypeError(f"required argument {key!r} must be passed")
            value = kwargs.get(key, default)
            setattr(obj, key, value)
        return obj

    def copy(self, **overrides) -> "Store":
        kwargs = self.as_dict()
        for key, value in overrides.items():
            kwargs[key] = value
        return self.__class__(**kwargs)

    def as_dict(self) -> Dict[str, Any]:
        # noinspection PyProtectedMember
        return {
            field: getattr(self, field) for field in self._fields
        }

    def __repr__(self) -> str:
        values = ", ".join([f"{k!s}={v!r}" for k, v in self.as_dict().items()])
        return f"<{self.__class__.__name__}: {values}>"


class ArgumentBase(Store):
    aliases: Iterable[str] = frozenset()
    nargs: Optional[Union[int, Nargs]] = Nargs.default()
    action: Union[Actions, argparse.Action] = Actions.default()
    type: Any = None

    def __init__(self, **kwargs):
        self._values = collections.OrderedDict()

        # noinspection PyUnresolvedReferences
        for key in self._fields:
            self._values[key] = kwargs.get(key, getattr(self.__class__, key))

    def __getattr__(self, item):
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

    def get_kwargs(self):
        nargs = self.nargs
        if isinstance(nargs, Nargs):
            nargs = nargs.value

        action = self.action
        if isinstance(action, Actions):
            action = action.value

        kwargs = self.as_dict()
        kwargs.pop("aliases", None)
        kwargs.pop("env_var", None)
        kwargs.update(action=action, nargs=nargs)

        return {k: v for k, v in kwargs.items() if v is not None}


class Argument(ArgumentBase):
    action: Union[Actions, argparse.Action] = Actions.default()
    aliases: Iterable[str] = frozenset()
    choices: Optional[Iterable[T]] = None
    const: Optional[T] = None
    default: Optional[T] = None
    help: Optional[str] = None
    metavar: Optional[str] = None
    nargs: Optional[Union[int, Nargs]] = Nargs.default()
    required: Optional[bool] = None
    env_var: Optional[str] = None
    type: Any = None


class Config(Argument):
    action: ConfigAction = ConfigAction
    search_paths: Optional[Iterable[Union[Path, str]]] = None


class AbstractGroup:
    pass


class AbstractParser:
    pass


class Meta(ABCMeta):
    def __new__(mcs, name, bases, attrs: Dict[str, Any]):
        annotations = merge_annotations(
            attrs.get("__annotations__", {}), *bases
        )

        arguments = {}
        argument_groups = {}
        subparsers = {}
        for key, kind in annotations.items():
            try:
                value = deep_getattr(key, attrs, *bases)
            except KeyError:
                value = Argument(type=kind)

            if isinstance(value, Argument):
                if value.type is None:
                    value.type = kind
                arguments[key] = value
            elif isinstance(value, AbstractGroup):
                argument_groups[key] = value

        for key, value in attrs.items():
            if isinstance(value, Argument):
                arguments[key] = value
            elif isinstance(value, AbstractGroup):
                argument_groups[key] = value
            elif isinstance(value, AbstractParser):
                subparsers[key] = value

        attrs["__arguments__"] = MappingProxyType(arguments)
        attrs["__argument_groups__"] = MappingProxyType(argument_groups)
        attrs["__subparsers__"] = MappingProxyType(subparsers)
        cls = super().__new__(mcs, name, bases, attrs)
        return cls


class Base(metaclass=Meta):
    __arguments__: Mapping[str, Argument]
    __argument_groups__: Mapping[str, "Group"]
    __subparsers__: Mapping[str, "Parser"]

    def __repr__(self) -> str:
        name = self.__class__.__name__
        attrs = {}
        for attr in self.__arguments__.keys():
            attrs[attr] = getattr(self, attr)
        for attr in self.__argument_groups__.keys():
            attrs[attr] = getattr(self, attr)
        for attr in self.__subparsers__.keys():
            attrs[attr] = getattr(self, attr)

        values = ", ".join(f"{k}={v!r}" for k, v in attrs.items())
        return f"{name}({values})"


class Group(AbstractGroup, Base):
    def __init__(self, title: str = None, description: Optional[str] = None,
                 prefix: Optional[str] = None,
                 defaults: Optional[Dict[str, Any]] = None):
        self._prefix: Optional[str] = prefix
        self._title: Optional[str] = title
        self._description: Optional[str] = description
        self._defaults: Mapping[str, Any] = MappingProxyType(defaults or {})


# noinspection PyProtectedMember
class Parser(AbstractParser, Base):
    @staticmethod
    def _add_argument(parser: Any, argument: Argument, dest: str, *aliases):
        kwargs = argument.get_kwargs()
        kwargs["dest"] = dest

        if argument.is_positional:
            dest = kwargs.pop("dest", None)

        if argument.default is not None:
            kwargs['help'] = (
                f"{kwargs.get('help', '')} (default: {argument.default})"
            ).strip()

        if argument.env_var is not None:
            kwargs['default'] = os.getenv(
                argument.env_var, kwargs.get('default')
            )
            kwargs['help'] = (
                f"{kwargs.get('help', '')} [ENV: {argument.env_var}]"
            ).strip()

        return dest, parser.add_argument(*aliases, **kwargs)

    @staticmethod
    def get_cli_name(name: str) -> str:
        return name.replace("_", "-")

    def get_env_var(self, name: str, argument: Argument) -> Optional[str]:
        if argument.env_var is not None:
            return argument.env_var
        if self._auto_env_var_prefix is not None:
            return f'{self._auto_env_var_prefix}{name}'.upper()
        return None

    def __init__(
        self, *args,
        config_files: Iterable[Union[str, Path]] = (),
        auto_env_var_prefix: Optional[str] = None,
        **kwargs,
    ):
        super().__init__()
        self._parser = ArgumentParser(*args, **kwargs)
        self._groups = {}
        self._destinations = {}
        self._auto_env_var_prefix: Optional[str] = auto_env_var_prefix
        self._subparsers: Optional[argparse.ArgumentParser] = None
        self._config = read_config(*config_files)

        for name, argument in self.__arguments__.items():
            aliases = set(argument.aliases)
            if not aliases:
                aliases.add(f"--{self.get_cli_name(name)}")
            argument.env_var = self.get_env_var(name, argument)
            argument.default = self._config.get(name, argument.default)
            dest, action = self._add_argument(
                self._parser, argument, name, *aliases
            )
            self._destinations[dest] = (self, name, argument, action)

        for group_name, group in self.__argument_groups__.items():
            parser = self._parser.add_argument_group(
                title=group._title,
                description=group._description,
            )

            for name, argument in group.__arguments__.items():
                aliases = set(argument.aliases)
                dest = "_".join((group._prefix or group_name, name))

                if not aliases:
                    aliases.add(f"--{self.get_cli_name(dest)}")

                dest, action = self._add_argument(
                    parser,
                    argument.copy(
                        default=group._defaults.get(name, argument.default)
                    ),
                    dest, *aliases
                )
                self._destinations[dest] = (group, name, argument, action)

        if self.__subparsers__:
            raise NotImplementedError()

    def _get_destinations(self, ns: argparse.Namespace) -> "_Destination":
        for attr, dest_value in self._destinations.items():
            target, name, argument, action = dest_value
            value = getattr(ns, attr)
            yield _Destination(
                attr=attr, target=target, name=name,
                argument=argument, action=action, value=value,
            )

    def parse_args(self, args: Optional[Sequence[str]] = None) -> "Parser":
        ns: argparse.Namespace = self._parser.parse_args(args)

        destinations: Iterable[_Destination] = list(self._get_destinations(ns))
        configs = list(
            filter(lambda x: x.argument.action == ConfigAction, destinations),
        )

        for config_dest in configs:
            config_dest.action(self._parser, ns, config_dest.value, None)

        for dest in self._get_destinations(ns):
            setattr(dest.target, dest.name, dest.value)

        return self

    def print_help(self):
        return self._parser.print_help()


class _Destination(NamedTuple):
    attr: str
    target: Parser
    name: str
    argument: Argument
    action: Union[Actions, ConfigAction]
    value: Any


LogLevel = Argument(
    choices=('debug', 'info', 'warning', 'error', 'critical'),
    type=lambda v: getattr(logging, v.upper(), logging.INFO),
    default='info'
)


__all__ = (
    "Actions",
    "Argument",
    "Group",
    "Nargs",
    "Parser",
    "LogLevel",
)
