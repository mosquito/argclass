import argparse
import ast
import collections
import configparser
import logging
import os
import sys
from abc import ABCMeta
from argparse import Action, ArgumentParser
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import (
    Any, Callable, Dict, Iterable, Mapping, MutableMapping, NamedTuple,
    Optional, Sequence, Set, Tuple, Type, TypeVar, Union, List,
)


T = TypeVar("T")
ConverterType = Callable[[str], Any]
NoneType = type(None)
UnionClass = Union[None, int].__class__


def read_config(
    *paths: Union[str, Path], **kwargs: Any
) -> Tuple[Dict[str, Any], Tuple[Path, ...]]:
    kwargs.setdefault("allow_no_value", True)
    kwargs.setdefault("strict", False)
    parser = configparser.ConfigParser(**kwargs)

    filenames = list(
        map(
            lambda p: p.resolve(),
            filter(
                lambda p: p.is_file(),
                map(lambda x: Path(x).expanduser(), paths),
            ),
        ),
    )
    config_paths = parser.read(filenames)

    result: Dict[str, Union[str, Dict[str, str]]] = dict(
        parser.items(parser.default_section, raw=True),
    )

    for section in parser.sections():
        config = dict(parser.items(section, raw=True))
        result[section] = config

    return result, tuple(map(Path, config_paths))


class ConfigAction(Action):
    def __init__(
        self, option_strings: Sequence[str], dest: str,
        search_paths: Iterable[Union[str, Path]] = (),
        type: MappingProxyType = MappingProxyType({}), help: str = "",
        required: bool = False, default: Any = None,
    ):
        if not isinstance(type, MappingProxyType):
            raise ValueError("type must be MappingProxyType")
        super().__init__(
            option_strings, dest, type=Path, help=help, default=default,
            required=required,
        )
        self.search_paths: List[Path] = list(map(Path, search_paths))
        self._result: Optional[Any] = None

    def __call__(
        self, parser: argparse.ArgumentParser, namespace: argparse.Namespace,
        values: Optional[Union[str, Any]], option_string: Optional[str] = None
    ) -> None:
        if not self._result:
            filenames: Sequence[Path] = list(self.search_paths)
            if values:
                filenames = [Path(values)] + list(filenames)
            self._result, filenames = read_config(*filenames)
            if self.required and not filenames:
                raise argparse.ArgumentError(
                    argument=self,
                    message="is required but no one config loaded",
                )
        setattr(namespace, self.dest, MappingProxyType(self._result))


class Actions(str, Enum):
    APPEND = "append"
    APPEND_CONST = "append_const"
    COUNT = "count"
    HELP = "help"
    PARSERS = "parsers"
    STORE = "store"
    STORE_CONST = "store_const"
    STORE_FALSE = "store_false"
    STORE_TRUE = "store_true"
    VERSION = "version"

    if sys.version_info >= (3, 8):
        EXTEND = "extend"

    @classmethod
    def default(cls) -> "Actions":
        return cls.STORE


class Nargs(Enum):
    ANY = None
    ONE_OR_MORE = "+"
    OPTIONAL = "?"
    ZERO_OR_MORE = "*"

    @classmethod
    def default(cls) -> "Nargs":
        return cls.ANY


def deep_getattr(name: str, attrs: Dict[str, Any], *bases: Type) -> Any:
    if name in attrs:
        return attrs[name]
    for base in bases:
        if hasattr(base, name):
            return getattr(base, name)
    raise KeyError(f"Key {name} was not declared")


def merge_annotations(
    annotations: Dict[str, Any], *bases: Type
) -> Dict[str, Any]:
    result: Dict[str, Any] = {}

    for base in bases:
        result.update(getattr(base, "__annotations__", {}))
    result.update(annotations)
    return result


class StoreMeta(type):
    def __new__(mcs, name: str, bases: Tuple[Type["StoreMeta"], ...],
                attrs: Dict[str, Any]) -> "StoreMeta":
        annotations = merge_annotations(
            attrs.get("__annotations__", {}), *bases
        )
        attrs["__annotations__"] = annotations
        attrs["_fields"] = tuple(
            filter(
                lambda x: not x.startswith("_"),
                annotations.keys(),
            ),
        )
        return super().__new__(mcs, name, bases, attrs)


class Store(metaclass=StoreMeta):
    _default_value = object()
    _fields: Tuple[str, ...]

    def __new__(cls, **kwargs: Any) -> "Store":
        obj = super().__new__(cls)

        type_map: Dict[str, Tuple[Type, Any]] = {}
        for key, value in obj.__annotations__.items():
            if key.startswith("_"):
                continue
            type_map[key] = (value, getattr(obj, key, cls._default_value))

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

    def as_dict(self) -> Dict[str, Any]:
        # noinspection PyProtectedMember
        return {
            field: getattr(self, field) for field in self._fields
        }

    def __repr__(self) -> str:
        values = ", ".join([
            f"{k!s}={v!r}" for k, v in sorted(self.as_dict().items())
        ])
        return f"<{self.__class__.__name__}: {values}>"


class ArgumentBase(Store):
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

    def get_kwargs(self) -> Dict[str, Any]:
        nargs = self.nargs
        if isinstance(nargs, Nargs):
            nargs = nargs.value

        action = self.action
        kwargs = self.as_dict()

        if action in (Actions.STORE_TRUE, Actions.STORE_FALSE, Actions.COUNT):
            kwargs.pop("type", None)

        if isinstance(action, Actions):
            action = action.value

        kwargs.pop("aliases", None)
        kwargs.pop("converter", None)
        kwargs.pop("env_var", None)
        kwargs.pop("secret", None)
        kwargs.update(action=action, nargs=nargs)

        return {k: v for k, v in kwargs.items() if v is not None}


class _Argument(ArgumentBase):
    action: Union[Actions, Type[Action]] = Actions.default()
    aliases: Iterable[str] = frozenset()
    choices: Optional[Iterable[str]] = None
    const: Optional[Any] = None
    converter: Optional[ConverterType] = None
    default: Optional[Any] = None
    secret: bool = False
    env_var: Optional[str] = None
    help: Optional[str] = None
    metavar: Optional[str] = None
    nargs: Optional[Union[int, Nargs]] = Nargs.default()
    required: Optional[bool] = None
    type: Any = None

    @property
    def is_nargs(self) -> bool:
        if self.nargs == Nargs.ANY:
            return False
        if isinstance(self.nargs, int):
            return self.nargs > 1
        return True


class _Config(_Argument):
    """ Parse INI file and set results as a value """
    action: Type[ConfigAction] = ConfigAction
    search_paths: Optional[Iterable[Union[Path, str]]] = None


class AbstractGroup:
    pass


class AbstractParser:
    pass


TEXT_TRUE_VALUES = frozenset((
    "y", "yes", "true", "t", "enable", "enabled", "1", "on",
))


def parse_bool(value: str) -> bool:
    return value.lower() in TEXT_TRUE_VALUES


def unwrap_optional(typespec: Any) -> Optional[Any]:
    if typespec.__class__ != UnionClass:
        return None

    union_args = [a for a in typespec.__args__ if a is not NoneType]

    if len(union_args) != 1:
        raise TypeError(
            "Complex types mustn't be used in short form. You have to "
            "specify argclass.Argument with converter or type function."
        )

    return union_args[0]


def _make_action_true_argument(
    kind: Type, default: Any = None,
) -> _Argument:
    kw: Dict[str, Any] = {"type": kind}
    if kind is bool:
        if default is False:
            kw["action"] = Actions.STORE_TRUE
        elif default is True:
            kw["action"] = Actions.STORE_FALSE
        else:
            raise TypeError(f"Can not set default {default!r} for bool")
    elif kind == Optional[bool]:
        kw["action"] = Actions.STORE
        kw["type"] = parse_bool
        kw["default"] = None
    return _Argument(**kw)


def _type_is_bool(kind: Type) -> bool:
    return kind is bool or kind == Optional[bool]


class Meta(ABCMeta):
    def __new__(mcs, name: str, bases: Tuple[Type["Meta"], ...],
                attrs: Dict[str, Any]) -> "Meta":
        annotations = merge_annotations(
            attrs.get("__annotations__", {}), *bases
        )

        arguments = {}
        argument_groups = {}
        subparsers = {}
        for key, kind in annotations.items():
            if key.startswith("_"):
                continue

            try:
                argument = deep_getattr(key, attrs, *bases)
            except KeyError:
                argument = None
                if kind is bool:
                    argument = False

            if not isinstance(
                argument, (_Argument, AbstractGroup, AbstractParser),
            ):
                attrs[key] = ...

                is_required = argument is None

                if _type_is_bool(kind):
                    argument = _make_action_true_argument(kind, argument)
                else:
                    optional_type = unwrap_optional(kind)
                    if optional_type is not None:
                        is_required = False
                        kind = optional_type

                    argument = _Argument(
                        type=kind, default=argument, required=is_required,
                    )

            if isinstance(argument, _Argument):
                if argument.type is None and argument.converter is None:
                    if kind.__class__.__module__ == "typing":
                        kind = unwrap_optional(kind)
                        argument.default = None
                    argument.type = kind
                arguments[key] = argument
            elif isinstance(argument, AbstractGroup):
                argument_groups[key] = argument

        for key, value in attrs.items():
            if key.startswith("_"):
                continue

            if isinstance(value, _Argument):
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
    __arguments__: Mapping[str, _Argument]
    __argument_groups__: Mapping[str, "Group"]
    __subparsers__: Mapping[str, "Parser"]

    def __getattribute__(self, item: str) -> Any:
        value = super().__getattribute__(item)
        if item.startswith("_"):
            return value

        if item in self.__arguments__:
            class_value = getattr(self.__class__, item, None)
            if value is class_value:
                raise AttributeError(f"Attribute {item!r} was not parsed")
        return value

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__}: "
            f"{len(self.__arguments__)} arguments, "
            f"{len(self.__argument_groups__)} groups, "
            f"{len(self.__subparsers__)} subparsers>"
        )


class Destination(NamedTuple):
    target: Base
    attribute: str
    argument: Optional[_Argument]
    action: Optional[Action]


DestinationsType = MutableMapping[str, Set[Destination]]


class Group(AbstractGroup, Base):
    def __init__(
        self, title: Optional[str] = None, description: Optional[str] = None,
        prefix: Optional[str] = None,
        defaults: Optional[Dict[str, Any]] = None,
    ):
        self._prefix: Optional[str] = prefix
        self._title: Optional[str] = title
        self._description: Optional[str] = description
        self._defaults: Mapping[str, Any] = MappingProxyType(defaults or {})


ParserType = TypeVar("ParserType", bound="Parser")


# noinspection PyProtectedMember
class Parser(AbstractParser, Base):
    HELP_APPENDIX_PREAMBLE = (
        " Default values will based on following "
        "configuration files {configs}. "
    )
    HELP_APPENDIX_CURRENT = (
        "Now {num_existent} files has been applied {existent}. "
    )
    HELP_APPENDIX_END = (
        "The configuration files is INI-formatted files "
        "where configuration groups is INI sections."
        "See more https://pypi.org/project/argclass/#configs"
    )

    def _add_argument(
        self, parser: Any, argument: _Argument, dest: str, *aliases: str,
    ) -> Tuple[str, Action]:
        kwargs = argument.get_kwargs()

        if not argument.is_positional:
            kwargs["dest"] = dest

        if argument.default is not None and not argument.secret:
            kwargs["help"] = (
                f"{kwargs.get('help', '')} (default: {argument.default})"
            ).strip()

        if argument.env_var is not None:
            default = kwargs.get("default")
            kwargs["default"] = os.getenv(argument.env_var, default)

            if kwargs["default"] and argument.is_nargs:
                kwargs["default"] = list(
                    map(
                        argument.type or str,
                        ast.literal_eval(kwargs["default"]),
                    )
                )

            kwargs["help"] = (
                f"{kwargs.get('help', '')} [ENV: {argument.env_var}]"
            ).strip()

            if argument.env_var in os.environ:
                self._used_env_vars.add(argument.env_var)

        if kwargs.get("default"):
            kwargs['required'] = False

        return dest, parser.add_argument(*aliases, **kwargs)

    @staticmethod
    def get_cli_name(name: str) -> str:
        return name.replace("_", "-")

    def get_env_var(self, name: str, argument: _Argument) -> Optional[str]:
        if argument.env_var is not None:
            return argument.env_var
        if self._auto_env_var_prefix is not None:
            return f"{self._auto_env_var_prefix}{name}".upper()
        return None

    def __init__(
        self, config_files: Iterable[Union[str, Path]] = (),
        auto_env_var_prefix: Optional[str] = None,
        **kwargs: Any,
    ):
        super().__init__()
        self.current_subparser = None
        self._config_files = config_files
        self._config, filenames = read_config(*config_files)

        self._epilog = kwargs.pop("epilog", "")
        self._epilog += self.HELP_APPENDIX_PREAMBLE.format(
            configs=repr(config_files),
        )

        if filenames:
            self._epilog += self.HELP_APPENDIX_CURRENT.format(
                num_existent=len(filenames),
                existent=repr(list(map(str, filenames))),
            )
        self._epilog += self.HELP_APPENDIX_END
        self._auto_env_var_prefix = auto_env_var_prefix
        self._parser_kwargs = kwargs
        self._used_env_vars: Set[str] = set()

    def _make_parser(
        self, parser: Optional[ArgumentParser] = None,
    ) -> Tuple[ArgumentParser, DestinationsType]:
        if parser is None:
            parser = ArgumentParser(
                epilog=self._epilog, **self._parser_kwargs
            )

        destinations: DestinationsType = collections.defaultdict(set)

        self._fill_arguments(destinations, parser)
        self._fill_groups(destinations, parser)
        if self.__subparsers__:
            self._fill_subparsers(destinations, parser)

        return parser, destinations

    def _fill_arguments(
        self, destinations: DestinationsType, parser: ArgumentParser,
    ) -> None:
        for name, argument in self.__arguments__.items():
            aliases = set(argument.aliases)

            # Add default alias
            if not aliases:
                aliases.add(f"--{self.get_cli_name(name)}")

            default = self._config.get(name, argument.default)
            argument = argument.copy(
                aliases=aliases,
                env_var=self.get_env_var(name, argument),
                default=default,
            )

            if default and argument.required:
                argument = argument.copy(required=False)

            dest, action = self._add_argument(parser, argument, name, *aliases)
            destinations[dest].add(
                Destination(
                    target=self,
                    attribute=name,
                    argument=argument,
                    action=action,
                ),
            )

    def _fill_groups(
        self, destinations: DestinationsType, parser: ArgumentParser,
    ) -> None:
        for group_name, group in self.__argument_groups__.items():
            group_parser = parser.add_argument_group(
                title=group._title,
                description=group._description,
            )
            config = self._config.get(group_name, {})

            for name, argument in group.__arguments__.items():
                aliases = set(argument.aliases)
                dest = "_".join((group._prefix or group_name, name))

                if not aliases:
                    aliases.add(f"--{self.get_cli_name(dest)}")

                default = config.get(
                    name, group._defaults.get(name, argument.default),
                )
                argument = argument.copy(
                    default=default,
                    env_var=self.get_env_var(dest, argument),
                )
                dest, action = self._add_argument(
                    group_parser, argument, dest, *aliases
                )
                destinations[dest].add(
                    Destination(
                        target=group,
                        attribute=name,
                        argument=argument,
                        action=action,
                    ),
                )

    def _fill_subparsers(
        self, destinations: DestinationsType, parser: ArgumentParser,
    ) -> None:
        subparsers = parser.add_subparsers()
        subparser: Parser
        destinations["current_subparser"].add(
            Destination(
                target=self,
                attribute="current_subparser",
                argument=None,
                action=None,
            ),
        )

        for subparser_name, subparser in self.__subparsers__.items():
            current_parser, subparser_dests = (
                subparser._make_parser(
                    subparsers.add_parser(
                        subparser_name, **subparser._parser_kwargs
                    ),
                )
            )
            current_parser.set_defaults(current_subparser=subparser)
            for dest, values in subparser_dests.items():
                for target, name, argument, action in values:
                    destinations[dest].add(
                        Destination(
                            target=subparser,
                            attribute=name,
                            argument=argument,
                            action=action,
                        ),
                    )

    def parse_args(
        self: ParserType, args: Optional[Sequence[str]] = None,
    ) -> ParserType:
        self._used_env_vars.clear()
        parser, destinations = self._make_parser()
        parsed_ns = parser.parse_args(args)

        parsed_value: Any
        current_subparser = getattr(parsed_ns, "current_subparser", None)

        for key, values in destinations.items():
            parsed_value = getattr(parsed_ns, key, None)
            for target, name, argument, action in values:
                if (
                    target is not self and
                    isinstance(target, Parser) and
                    current_subparser is not target
                ):
                    continue

                if isinstance(action, ConfigAction):
                    action(parser, parsed_ns, parsed_value, None)
                    parsed_value = getattr(parsed_ns, key)

                if argument is not None and argument.converter is not None:
                    if argument.nargs and parsed_value is None:
                        parsed_value = []
                    parsed_value = argument.converter(parsed_value)
                setattr(target, name, parsed_value)

        return self

    def print_help(self) -> None:
        parser, _ = self._make_parser()
        return parser.print_help()

    def sanitize_env(self) -> None:
        for name in self._used_env_vars:
            os.environ.pop(name, None)
        self._used_env_vars.clear()


# noinspection PyPep8Naming
def Argument(
    *aliases: str,
    action: Union[Actions, Type[Action]] = Actions.default(),
    choices: Optional[Iterable[str]] = None,
    const: Optional[Any] = None,
    converter: Optional[ConverterType] = None,
    default: Optional[Any] = None,
    secret: bool = False,
    env_var: Optional[str] = None,
    help: Optional[str] = None,
    metavar: Optional[str] = None,
    nargs: Optional[Union[int, str, Nargs]] = Nargs.default(),
    required: Optional[bool] = None,
    type: Any = None
) -> Any:
    return _Argument(
        action=action,
        aliases=aliases,
        choices=choices,
        const=const,
        converter=converter,
        default=default,
        secret=secret,
        env_var=env_var,
        help=help,
        metavar=metavar,
        nargs=nargs,
        required=required,
        type=type,
    )    # type: ignore


# noinspection PyPep8Naming
def Secret(
    *aliases: str,
    action: Union[Actions, Type[Action]] = Actions.default(),
    choices: Optional[Iterable[str]] = None,
    const: Optional[Any] = None,
    converter: Optional[ConverterType] = None,
    default: Optional[Any] = None,
    env_var: Optional[str] = None,
    help: Optional[str] = None,
    metavar: Optional[str] = None,
    nargs: Optional[Union[int, str, Nargs]] = Nargs.default(),
    required: Optional[bool] = None,
    type: Any = None
) -> Any:
    return _Argument(
        action=action,
        aliases=aliases,
        choices=choices,
        const=const,
        converter=converter,
        default=default,
        secret=True,
        env_var=env_var,
        help=help,
        metavar=metavar,
        nargs=nargs,
        required=required,
        type=type,
    )    # type: ignore


# noinspection PyPep8Naming
def Config(
    *aliases: str,
    search_paths: Optional[Iterable[Union[Path, str]]] = None,
    choices: Optional[Iterable[str]] = None,
    converter: Optional[ConverterType] = None,
    const: Optional[Any] = None,
    default: Optional[Any] = None,
    env_var: Optional[str] = None,
    help: Optional[str] = None,
    metavar: Optional[str] = None,
    nargs: Optional[Union[int, str, Nargs]] = Nargs.default(),
    required: Optional[bool] = None,
) -> Any:
    return _Config(
        search_paths=search_paths,
        aliases=aliases,
        choices=choices,
        const=const,
        converter=converter,
        default=default,
        env_var=env_var,
        help=help,
        metavar=metavar,
        nargs=nargs,
        required=required,
    )    # type: ignore


LogLevel: Any = Argument(
    choices=("debug", "info", "warning", "error", "critical"),
    converter=lambda v: getattr(logging, v.upper(), logging.INFO),
    default="info",
)


__all__ = (
    "Actions",
    "Argument",
    "Group",
    "Nargs",
    "Parser",
    "LogLevel",
)
