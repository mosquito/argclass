"""
argclass - Declarative argument parser using classes.

A wrapper around the standard `argparse` module that allows you to describe
argument parsers declaratively using classes with type annotations.
"""

from enum import EnumMeta

from ._actions import ConfigAction, INIConfigAction, JSONConfigAction
from ._factory import (
    Argument,
    ArgumentSequence,
    ArgumentSingle,
    Config,
    EnumArgument,
    LogLevel,
    Secret,
)
from ._parser import Base, Destination, Group, Meta, Parser
from ._secret import SecretString
from ._store import (
    AbstractGroup,
    AbstractParser,
    ArgumentBase,
    ConfigArgument,
    INIConfig,
    JSONConfig,
    Store,
    StoreMeta,
    TypedArgument,
)
from ._types import Actions, ConverterType, LogLevelEnum, Nargs, NargsType
from ._utils import parse_bool, read_configs

# For backward compatibility
EnumType = EnumMeta

__all__ = [
    # Types and enums
    "Actions",
    "Nargs",
    "LogLevelEnum",
    "ConverterType",
    "NargsType",
    # Classes
    "SecretString",
    "Store",
    "StoreMeta",
    "TypedArgument",
    "ArgumentBase",
    "ConfigArgument",
    "INIConfig",
    "JSONConfig",
    "AbstractGroup",
    "AbstractParser",
    "Group",
    "Parser",
    "Base",
    "Meta",
    "Destination",
    # Actions
    "ConfigAction",
    "INIConfigAction",
    "JSONConfigAction",
    # Factory functions
    "Argument",
    "ArgumentSingle",
    "ArgumentSequence",
    "EnumArgument",
    "Secret",
    "Config",
    "LogLevel",
    # Utilities
    "read_configs",
    "parse_bool",
]
