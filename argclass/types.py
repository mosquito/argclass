"""Type definitions, enums, and constants for argclass."""

from enum import Enum, IntEnum
from typing import Any, Union, Literal
from collections.abc import Callable

# Type aliases
ConverterType = Callable[[Any], Any]
MetavarType = str | tuple[str, ...]
NoneType = type(None)
# Introspection helper: the class of a typing.Union alias, used to detect
# ``Optional[T]`` / ``Union[...]`` annotations (PEP 604 ``X | Y`` is handled
# separately via ``types.UnionType``). Must stay a typing.Union at runtime.
UnionClass = Union[None, int].__class__  # noqa: UP007


class Actions(str, Enum):
    """Argparse action types."""

    STORE = "store"
    STORE_CONST = "store_const"
    STORE_TRUE = "store_true"
    STORE_FALSE = "store_false"
    APPEND = "append"
    APPEND_CONST = "append_const"
    COUNT = "count"
    HELP = "help"
    VERSION = "version"

    @classmethod
    def default(cls) -> "Actions":
        return cls.STORE


class Nargs(Enum):
    """Argparse nargs values."""

    ZERO_OR_ONE = "?"
    ZERO_OR_MORE = "*"
    ONE_OR_MORE = "+"


NargsType = int | str | Nargs | Literal["?", "*", "+"]


class LogLevelEnum(IntEnum):
    """Standard logging levels."""

    CRITICAL = 50
    FATAL = 50
    ERROR = 40
    WARNING = 30
    WARN = 30
    INFO = 20
    DEBUG = 10
    NOTSET = 0


# Container types for automatic nargs handling
CONTAINER_TYPES: tuple[type, ...] = (list, set, frozenset, tuple)


# Boolean string values
TEXT_TRUE_VALUES = frozenset(
    (
        "y",
        "yes",
        "true",
        "t",
        "enable",
        "enabled",
        "1",
        "on",
    )
)
