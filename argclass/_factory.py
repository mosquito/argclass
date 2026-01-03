"""Factory functions for creating arguments."""

from functools import partial
from pathlib import Path
from typing import Any, Iterable, Optional, Type, Union

from argparse import Action

from ._store import ConfigArgument, INIConfig, TypedArgument
from ._types import Actions, ConverterType, LogLevelEnum, NargsType


# noinspection PyShadowingBuiltins
def Argument(
    *aliases: str,
    action: Union[Actions, Type[Action]] = Actions.default(),
    choices: Optional[Iterable[str]] = None,
    const: Optional[Any] = None,
    converter: Optional[ConverterType] = None,
    default: Optional[Any] = None,
    env_var: Optional[str] = None,
    help: Optional[str] = None,
    metavar: Optional[str] = None,
    nargs: NargsType = None,
    required: Optional[bool] = None,
    secret: bool = False,
    type: Optional[ConverterType] = None,
) -> Any:
    """
    Create a typed argument for a Parser or Group class.

    Args:
        *aliases: Command-line aliases (e.g., "-n", "--name").
        action: How to handle the argument (store, store_true, etc.).
        choices: Restrict values to these options.
        const: Constant value for store_const/append_const actions.
        converter: Function to transform the final parsed value(s).
            Called after argparse parsing, receives the full result.
            With nargs, receives the list and should return transformed list.
        default: Default value if argument not provided.
        env_var: Environment variable to read default from.
        help: Help text for --help output.
        metavar: Placeholder name in help text.
        nargs: Number of values (int, "?", "*", "+", or Nargs enum).
        required: Whether the argument must be provided.
        secret: If True, hide value from help and wrap str in SecretString.
        type: Function to convert each individual string value from CLI.
            Passed directly to argparse. With nargs, called for EACH value.

    Returns:
        TypedArgument instance.

    Example - type vs converter:
        # type: converts each CLI value individually
        numbers = Argument(nargs="+", type=int)
        # Parsing ["1", "2"] -> calls int("1"), int("2") -> [1, 2]

        # converter: transforms the final result
        unique = Argument(nargs="+", type=int, converter=set)
        # Parsing ["1", "2", "1"] -> [1, 2, 1] -> set([1, 2, 1]) -> {1, 2}
    """
    return TypedArgument(
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
    )


def EnumArgument(
    enum_class: Type,
    *aliases: str,
    action: Union[Actions, Type[Action]] = Actions.default(),
    default: Optional[Any] = None,
    env_var: Optional[str] = None,
    help: Optional[str] = None,
    metavar: Optional[str] = None,
    nargs: NargsType = None,
    required: Optional[bool] = None,
    use_value: bool = False,
    lowercase: bool = False,
) -> Any:
    """
    Create an argument from an Enum class.

    Args:
        enum_class: The Enum class to use for choices and conversion.
        *aliases: Command-line aliases (e.g., "-l", "--level").
        action: How to handle the argument.
        default: Default value (as string name, not enum member).
        env_var: Environment variable to read default from.
        help: Help text for --help output.
        metavar: Placeholder name in help text.
        nargs: Number of values.
        required: Whether the argument must be provided.
        use_value: If True, return enum.value instead of enum member.
        lowercase: If True, use lowercase choices and accept lowercase input.

    Returns:
        TypedArgument instance.
    """
    if lowercase:
        choices = tuple(e.name.lower() for e in enum_class)
    else:
        choices = tuple(e.name for e in enum_class)

    def converter(x: Any) -> Any:
        # Handle existing enum members
        if isinstance(x, enum_class):
            return x.value if use_value else x
        # Convert string to enum
        name = x.upper() if lowercase else x
        member = enum_class[name]
        return member.value if use_value else member

    return TypedArgument(
        action=action,
        aliases=aliases,
        choices=choices,
        converter=converter,
        default=default,
        env_var=env_var,
        help=help,
        metavar=metavar,
        nargs=nargs,
        required=required,
    )


Secret = partial(Argument, secret=True)


# noinspection PyShadowingBuiltins
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
    nargs: NargsType = None,
    required: Optional[bool] = None,
    config_class: Type[ConfigArgument] = INIConfig,
) -> Any:
    """Create a configuration file argument."""
    return config_class(
        search_paths=search_paths,
        aliases=aliases,
        choices=choices,
        converter=converter,
        const=const,
        default=default,
        env_var=env_var,
        help=help,
        metavar=metavar,
        nargs=nargs,
        required=required,
    )


# Pre-built log level argument
LogLevel = EnumArgument(
    LogLevelEnum,
    use_value=True,
    lowercase=True,
    default="info",
)
