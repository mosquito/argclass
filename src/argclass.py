import argparse
import configparser
from abc import ABCMeta
from argparse import ArgumentParser
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import (
    Any, Dict, Iterable, Mapping, Optional, Sequence, Type, TypeVar, Union,
)


T = TypeVar("T")


class ConfigAction(argparse.Action):
    def __init__(
        self, option_strings: Sequence[str], dest: str, search_paths=()
    ):
        super().__init__(option_strings, dest)
        self.search_paths = list(map(Path, search_paths))
        self.__parser = configparser.ConfigParser(
            default_section="__default__"
        )

    def __call__(self, parser, namespace, values, option_string=None):
        filenames = list(self.search_paths)
        if values is not None:
            filenames.insert(0, Path(values))
        self.__parser.read(filenames)

        result = {}
        for section in self.__parser.sections():
            config = dict(
                self.__parser.items(section, raw=True)
            )

            if section == self.__parser.default_section:
                result.update(**config)
            else:
                result[section] = config


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


@dataclass(frozen=True)
class Argument:
    action: Union[Actions, argparse.Action] = Actions.default()
    aliases: Iterable[str] = frozenset()
    choices: Optional[Iterable[T]] = None
    const: Optional[T] = None
    default: Optional[T] = None
    help: Optional[str] = None
    metavar: Optional[str] = None
    nargs: Optional[Union[int, Nargs]] = Nargs.default()
    required: Optional[bool] = None
    type: Any = None

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

        kwargs = dict(self.__dict__)
        kwargs.pop("aliases", None)
        kwargs.update(action=action, nargs=nargs)

        return {k: v for k, v in kwargs.items() if v is not None}


@dataclass(frozen=True)
class Config(Argument):
    action: ConfigAction = ConfigAction
    search_paths: Optional[Iterable[Union[Path, str]]] = None


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


class AbstractGroup:
    pass


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
                    value = replace(value, type=kind)
                arguments[key] = value
            elif isinstance(value, AbstractGroup):
                argument_groups[key] = value

        for key, value in attrs.items():
            if isinstance(value, Argument):
                arguments[key] = value
            elif isinstance(value, AbstractGroup):
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


class Group(AbstractGroup, Base):
    def __init__(self, title: str, description: Optional[str] = None):
        self.title: str = title
        self.description: str = description


class Parser(Base):
    @staticmethod
    def _add_argument(parser: Any, argument: Argument, dest: str, *aliases):
        kwargs = argument.get_kwargs()
        kwargs["dest"] = dest

        if argument.is_positional:
            dest = kwargs.pop("dest", None)

        return dest, parser.add_argument(*aliases, **kwargs)

    @staticmethod
    def get_cli_name(name: str):
        return name.replace("_", "-")

    def __init__(self, *args, **kwargs):
        self._parser = ArgumentParser(*args, **kwargs)
        self._groups = {}
        self._destinations = {}

        for name, argument in self.__arguments__.items():
            aliases = set(argument.aliases)

            if not aliases:
                aliases.add(f"--{name.replace('_', '-')}")

            dest, action = self._add_argument(
                self._parser, argument, name, *aliases
            )
            self._destinations[dest] = (self, name, argument, action)

        for group_name, group in self.__argument_groups__.items():
            parser = self._parser.add_argument_group(
                title=group.title,
                description=group.description,
            )

            for name, argument in group.__arguments__.items():
                aliases = set(argument.aliases)
                dest = "_".join((group_name, name))

                if not aliases:
                    aliases.add(f"--{self.get_cli_name(dest)}")

                dest, action = self._add_argument(
                    parser, argument, dest, *aliases
                )
                self._destinations[dest] = (group, name, argument, action)

    def parse_args(self, args: Optional[Sequence[str]]) -> "Parser":
        ns = self._parser.parse_args(args)
        for attr, dest_value in self._destinations.items():
            target, name, argument, action = dest_value
            value = getattr(ns, attr)

            if argument.action == ConfigAction:
                action(self._parser, ns, value, None)
            else:
                setattr(target, name, value)

        return self

    def print_help(self):
        return self._parser.print_help()


__all__ = (
    "Actions",
    "Argument",
    "Group",
    "Nargs",
    "Parser",
)
