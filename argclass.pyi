import argparse
from _typeshed import Incomplete
from abc import ABCMeta
from argparse import Action
from enum import Enum, EnumMeta, IntEnum
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Dict, Iterable, Mapping, MutableMapping, NamedTuple, Sequence, Set, Tuple, Type, TypeVar

__all__ = ['Actions', 'Argument', 'ConfigArgument', 'EnumArgument', 'Group', 'LogLevel', 'LogLevelEnum', 'Nargs', 'Parser', 'SecretString', 'JSONConfig', 'INIConfig']

ConverterType = Callable[[str], Any]
EnumType = EnumMeta

class SecretString(str):
    PLACEHOLDER: str
    MODULES_SKIPLIST: Incomplete

class ConfigAction(Action):
    search_paths: Incomplete
    def __init__(self, option_strings: Sequence[str], dest: str, search_paths: Iterable[str | Path] = (), type: MappingProxyType = ..., help: str = '', required: bool = False, default: Any = None) -> None: ...
    def parse(self, *files: Path) -> Any: ...
    def parse_file(self, file: Path) -> Any: ...
    def __call__(self, parser: argparse.ArgumentParser, namespace: argparse.Namespace, values: str | Any | None, option_string: str | None = None) -> None: ...

class INIConfigAction(ConfigAction):
    def parse(self, *files: Path) -> Mapping[str, Any]: ...

class JSONConfigAction(ConfigAction):
    def parse_file(self, file: Path) -> Any: ...

class Actions(str, Enum):
    APPEND: str
    APPEND_CONST: str
    COUNT: str
    HELP: str
    PARSERS: str
    STORE: str
    STORE_CONST: str
    STORE_FALSE: str
    STORE_TRUE: str
    VERSION: str
    EXTEND: str
    @classmethod
    def default(cls) -> Actions: ...

class Nargs(Enum):
    ONE_OR_MORE: str
    OPTIONAL: str
    ZERO_OR_MORE: str

class StoreMeta(type):
    def __new__(mcs, name: str, bases: Tuple[Type['StoreMeta'], ...], attrs: Dict[str, Any]) -> StoreMeta: ...

class Store(metaclass=StoreMeta):
    def __new__(cls, **kwargs: Any) -> Store: ...
    def copy(self, **overrides: Any) -> Any: ...
    def as_dict(self) -> Dict[str, Any]: ...

class ArgumentBase(Store):
    def __init__(self, **kwargs: Any) -> None: ...
    def __getattr__(self, item: str) -> Any: ...
    @property
    def is_positional(self) -> bool: ...
    def get_kwargs(self) -> Dict[str, Any]: ...

class _Argument(ArgumentBase):
    action: Actions | Type[Action]
    aliases: Iterable[str]
    choices: Iterable[str] | None
    const: Any | None
    converter: ConverterType | None
    default: Any | None
    secret: bool
    env_var: str | None
    help: str | None
    metavar: str | None
    nargs: int | Nargs | None
    required: bool | None
    type: Any
    @property
    def is_nargs(self) -> bool: ...

class ConfigArgument(_Argument):
    search_paths: Iterable[Path | str] | None
    action: Type[ConfigAction]

class INIConfig(ConfigArgument):
    action: Type[ConfigAction]

class JSONConfig(ConfigArgument):
    action: Type[ConfigAction]

class AbstractGroup: ...

class AbstractParser:
    __parent__: Parser | None
    def __call__(self) -> None: ...

class Meta(ABCMeta):
    def __new__(mcs, name: str, bases: Tuple[Type['Meta'], ...], attrs: Dict[str, Any]) -> Meta: ...

class Base(metaclass=Meta):
    __arguments__: Mapping[str, _Argument]
    __argument_groups__: Mapping[str, 'Group']
    __subparsers__: Mapping[str, 'Parser']
    def __getattribute__(self, item: str) -> Any: ...

class Destination(NamedTuple):
    target: Base
    attribute: str
    argument: _Argument | None
    action: Action | None
DestinationsType = MutableMapping[str, Set[Destination]]

class Group(AbstractGroup, Base):
    def __init__(self, title: str | None = None, description: str | None = None, prefix: str | None = None, defaults: Dict[str, Any] | None = None) -> None: ...
ParserType = TypeVar('ParserType', bound='Parser')

class Parser(AbstractParser, Base):
    HELP_APPENDIX_PREAMBLE: str
    HELP_APPENDIX_CURRENT: str
    HELP_APPENDIX_END: str
    @staticmethod
    def get_cli_name(name: str) -> str: ...
    def get_env_var(self, name: str, argument: _Argument) -> str | None: ...
    current_subparsers: Incomplete
    def __init__(self, config_files: Iterable[str | Path] = (), auto_env_var_prefix: str | None = None, **kwargs: Any) -> None: ...
    @property
    def current_subparser(self) -> AbstractParser | None: ...
    def parse_args(self, args: Sequence[str] | None = None) -> ParserType: ...
    def print_help(self) -> None: ...
    def sanitize_env(self) -> None: ...
    def __call__(self) -> None: ...

def Argument(*aliases: str, action: Actions | Type[Action] = ..., choices: Iterable[str] | None = None, const: Any | None = None, converter: ConverterType | None = None, default: Any | None = None, secret: bool = False, env_var: str | None = None, help: str | None = None, metavar: str | None = None, nargs: NargsType = None, required: bool | None = None, type: Callable[[str], Any] | None = None) -> Any: ...
def EnumArgument(enum: EnumMeta, *aliases: str, action: Actions | Type[Action] = ..., const: Any | None = None, default: Any | None = None, secret: bool = False, env_var: str | None = None, help: str | None = None, metavar: str | None = None, nargs: NargsType = None, required: bool | None = None) -> Any: ...

class LogLevelEnum(IntEnum):
    debug: Incomplete
    info: Incomplete
    warning: Incomplete
    error: Incomplete
    critical: Incomplete

LogLevel: LogLevelEnum
