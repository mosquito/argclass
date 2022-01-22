from dataclasses import dataclass
from abc import ABCMeta
from enum import Enum
from argparse import ArgumentParser
from types import MappingProxyType
from typing import Iterable, Union, Any, TypeVar, Callable, Optional, Dict, \
    Type, Mapping, MutableSet, Sequence

T = TypeVar("T")


class Actions(str, Enum):
    STORE = "store"
    STORE_TRUE = "store_true"
    STORE_FALSE = "store_true"
    STORE_CONST = "store_const"
    APPEND = "append"
    APPEND_CONST = "append_const"
    COUNT = "count"
    HELP = "help"
    VERSION = "version"
    EXTEND = "extend"
    PARSERS = "parsers"


class Nargs(str, Enum):
    OPTIONAL = '?'
    ZERO_OR_MORE = '*'
    ONE_OR_MORE = '+'


@dataclass
class Argument:
    type: Any = None
    aliases: MutableSet[str] = frozenset()
    action: Union[Actions, Callable] = Actions.STORE
    nargs: Optional[Union[int, Nargs]] = None
    const: Optional[T] = None
    default: Optional[T] = None
    converter: Callable[..., T] = str
    choices: Optional[Iterable[T]] = None
    help: str = ""
    required: bool = False
    metavar: Optional[str] = None


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


class Meta(ABCMeta):
    def __new__(mcs, name, bases, attrs: Dict[str, Any]):
        annotations = merge_annotations(
            attrs.get("__annotations__", {}), *bases
        )

        arguments = {}
        argument_groups = {}
        for key, kind in annotations.items():
            try:
                value = deep_getattr(key, attrs, *bases)
            except KeyError:
                value = Argument(type=kind)

            if isinstance(value, Argument):
                if value.type is None:
                    value.type = kind
                if value.converter is None:
                    value.converter = value.type
                arguments[key] = value
            elif isinstance(value, Group):
                argument_groups[key] = value

        for key, value in attrs.items():
            if isinstance(value, Argument):
                arguments[key] = value
            elif isinstance(value, Group):
                argument_groups[key] = value

        attrs["__arguments__"] = MappingProxyType(arguments)
        attrs["__argument_groups__"] = MappingProxyType(argument_groups)
        cls = super().__new__(mcs, name, bases, attrs)
        return cls


class Base(metaclass=Meta):
    __arguments__: Mapping[str, Argument]
    __argument_groups__: Mapping[str, "Group"]

    def __repr__(self) -> str:
        name = self.__class__.__name__
        attrs = {}
        for attr in self.__arguments__.keys():
            attrs[attr] = getattr(self, attr)
        for attr in self.__argument_groups__.keys():
            attrs[attr] = getattr(self, attr)
        values = ", ".join(f"{k}={v!r}" for k, v in attrs.items())
        return f"{name}({values})"


class Group(Base):
    def __init__(self, title: str, description: Optional[str] = None):
        self.title: str = title
        self.description: str = description


class Parser(Base):
    @staticmethod
    def _add_argument(parser: Any, argument: Argument, dest: str, *aliases):
        parser.add_argument(
            *aliases,
            action=argument.action,
            nargs=argument.nargs,
            const=argument.const,
            default=argument.default,
            type=argument.converter,
            choices=argument.choices,
            help=argument.help,
            required=argument.required,
            metavar=argument.metavar,
            dest=dest,
        )
        return dest

    @staticmethod
    def get_cli_name(name: str):
        return name.replace('_', '-')

    def __init__(self, *args, **kwargs):
        self.parser = ArgumentParser(*args, **kwargs)
        self.groups = {}
        self.destinations = {}

        for name, argument in self.__arguments__.items():
            aliases = set(argument.aliases)
            aliases.add(f"--{name.replace('_', '-')}")

            self.destinations[name] = (self, name)

            self._add_argument(self.parser, argument, name, *aliases)

        for group_name, group in self.__argument_groups__.items():
            parser = self.parser.add_argument_group(
                title=group.title,
                description=group.description,
            )

            for name, argument in group.__arguments__.items():
                aliases = set(argument.aliases)
                dest = "_".join((group_name, name))
                aliases.add(f"--{self.get_cli_name(dest)}")
                self.destinations[dest] = (group, name)
                self._add_argument(parser, argument, dest, *aliases)

        self.destinations = MappingProxyType(self.destinations)

    def parse_args(self, args: Optional[Sequence[str]]) -> "Parser":
        ns = self.parser.parse_args(args)
        for attr, (instance, name) in self.destinations.items():
            setattr(instance, name, getattr(ns, attr))
        return self

    def print_help(self):
        return self.parser.print_help()
