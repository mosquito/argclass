"""Core parser classes for argclass."""

import ast
import os
from abc import ABCMeta
from argparse import Action, ArgumentError, ArgumentParser
from collections import defaultdict
from enum import EnumMeta
from pathlib import Path
from types import MappingProxyType
from typing import (
    Any,
    Dict,
    Iterable,
    List,
    Mapping,
    MutableMapping,
    NamedTuple,
    Optional,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
)

from ._actions import ConfigAction
from ._defaults import AbstractDefaultsParser, INIDefaultsParser
from ._secret import SecretString
from ._store import AbstractGroup, AbstractParser, TypedArgument
from ._types import Actions, Nargs
from ._utils import (
    _unwrap_container_type,
    deep_getattr,
    merge_annotations,
    parse_bool,
    unwrap_literal,
    unwrap_optional,
)


def _make_action_true_argument(
    kind: Type,
    default: Any = None,
) -> TypedArgument:
    """Create a TypedArgument for boolean types."""
    kw: Dict[str, Any] = {"type": kind}
    if kind is bool:
        if default is False:
            kw["action"] = Actions.STORE_TRUE
            kw["default"] = False
        elif default is True:
            kw["action"] = Actions.STORE_FALSE
            kw["default"] = True
        else:
            raise TypeError(f"Can not set default {default!r} for bool")
    elif kind == Optional[bool]:
        kw["action"] = Actions.STORE
        kw["type"] = parse_bool
        kw["default"] = None
    return TypedArgument(**kw)


def _type_is_bool(kind: Type) -> bool:
    """Check if a type is bool or Optional[bool]."""
    return kind is bool or kind == Optional[bool]


class Meta(ABCMeta):
    """Metaclass for Parser and Group classes."""

    def __new__(
        mcs,
        name: str,
        bases: Tuple[Type["Meta"], ...],
        attrs: Dict[str, Any],
    ) -> "Meta":
        # Import here to avoid circular import
        from ._factory import EnumArgument

        # Create the class first to ensure annotations are available
        # Python 3.14+ (PEP 649) defers annotation evaluation, so
        # __annotations__ may not be in attrs during class creation
        cls = super().__new__(mcs, name, bases, attrs)

        # Now get annotations from the created class
        annotations = merge_annotations(
            getattr(cls, "__annotations__", {}),
            *bases,
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
                argument,
                (TypedArgument, AbstractGroup, AbstractParser),
            ):
                setattr(cls, key, ...)

                is_required = argument is None or argument is Ellipsis

                # Handle Enum types with auto-generated EnumArgument
                if isinstance(kind, EnumMeta):
                    argument = EnumArgument(kind, default=argument)
                elif _type_is_bool(kind):
                    # For inherited bools, Ellipsis means use default False
                    if argument is Ellipsis:
                        argument = False
                    argument = _make_action_true_argument(kind, argument)
                else:
                    optional_type = unwrap_optional(kind)
                    if optional_type is not None:
                        is_required = False
                        kind = optional_type

                    # Handle Literal types like Literal["a", "b", "c"]
                    literal_info = unwrap_literal(kind)
                    if literal_info is not None:
                        value_type, choices = literal_info
                        argument = TypedArgument(
                            type=value_type,
                            choices=choices,
                            default=argument,
                            required=is_required,
                        )
                    # Handle container types like list[str], List[int], etc.
                    elif (ctr_info := _unwrap_container_type(kind)) is not None:
                        container_type, element_type = ctr_info
                        # Use nargs="+" for required, "*" for optional
                        if is_required:
                            nargs: Union[str, Nargs] = Nargs.ONE_OR_MORE
                        else:
                            nargs = Nargs.ZERO_OR_MORE
                        # Use converter for non-list containers
                        if container_type is not list:
                            converter = container_type
                        else:
                            converter = None
                        default = None if argument is Ellipsis else argument
                        argument = TypedArgument(
                            type=element_type,
                            default=default,
                            required=is_required,
                            nargs=nargs,
                            converter=converter,
                        )
                    else:
                        argument = TypedArgument(
                            type=kind,
                            default=argument,
                            required=is_required,
                        )

            if isinstance(argument, TypedArgument):
                if argument.type is None and argument.converter is None:
                    # First try to unwrap optional
                    optional_inner = unwrap_optional(kind)
                    if optional_inner is not None:
                        kind = optional_inner
                        if argument.default is None:
                            argument.default = None

                    # Handle bool type: set STORE_TRUE/STORE_FALSE action
                    if kind is bool and argument.action == Actions.default():
                        default = argument.default
                        if default is False or default is None:
                            argument = argument.copy(
                                action=Actions.STORE_TRUE,
                                default=False,
                                type=None,
                            )
                        elif default is True:
                            argument = argument.copy(
                                action=Actions.STORE_FALSE,
                                default=True,
                                type=None,
                            )
                    # Handle Literal types
                    elif (lit_info := unwrap_literal(kind)) is not None:
                        value_type, choices = lit_info
                        argument.type = value_type
                        if argument.choices is None:
                            argument.choices = choices
                    # Then check for container types
                    elif (
                        container_info := _unwrap_container_type(kind)
                    ) is not None:
                        container_type, element_type = container_info
                        argument.type = element_type
                        # Only set nargs if not already specified
                        if argument.nargs is None:
                            argument.nargs = Nargs.ZERO_OR_MORE
                        # Only set converter for non-list containers
                        is_non_list = container_type is not list
                        if is_non_list and argument.converter is None:
                            argument.converter = container_type
                    else:
                        argument.type = kind
                arguments[key] = argument
            elif isinstance(argument, AbstractGroup):
                argument_groups[key] = argument

        for key, value in attrs.items():
            if key.startswith("_"):
                continue

            # Skip if already processed from annotations
            if key in arguments or key in argument_groups or key in subparsers:
                continue

            if isinstance(value, TypedArgument):
                arguments[key] = value
            elif isinstance(value, AbstractGroup):
                argument_groups[key] = value
            elif isinstance(value, AbstractParser):
                subparsers[key] = value

        setattr(cls, "__arguments__", MappingProxyType(arguments))
        setattr(cls, "__argument_groups__", MappingProxyType(argument_groups))
        setattr(cls, "__subparsers__", MappingProxyType(subparsers))
        return cls


class Base(metaclass=Meta):
    """Base class for Parser and Group."""

    __arguments__: Mapping[str, TypedArgument]
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
    """Stores destination information for parsed arguments."""

    target: Base
    attribute: str
    argument: Optional[TypedArgument]
    action: Optional[Action]


DestinationsType = MutableMapping[str, Set[Destination]]


class Group(AbstractGroup, Base):
    """Argument group for organizing related arguments."""

    def __init__(
        self,
        title: Optional[str] = None,
        description: Optional[str] = None,
        prefix: Optional[str] = None,
        defaults: Optional[Mapping[str, Any]] = None,
    ):
        self._title = title
        self._description = description
        self._prefix = prefix
        self._defaults: Mapping[str, Any] = defaults or {}


ParserType = TypeVar("ParserType", bound="Parser")


# noinspection PyProtectedMember
class Parser(AbstractParser, Base):
    """Main parser class for command-line argument parsing."""

    HELP_APPENDIX_PREAMBLE = (
        " Default values will based on following "
        "configuration files {configs}. "
    )
    HELP_APPENDIX_CURRENT = (
        "Now {num_existent} files has been applied {existent}. "
    )
    HELP_APPENDIX_END = (
        "The configuration files is INI-formatted files "
        "where configuration groups is INI sections. "
        "See more https://docs.argclass.com/config-files.html"
    )

    def _add_argument(
        self,
        parser: Any,
        argument: TypedArgument,
        dest: str,
        *aliases: str,
    ) -> Tuple[str, Action]:
        kwargs = argument.get_kwargs()

        if not argument.is_positional:
            kwargs["dest"] = dest

        if (
            argument.default is not None
            and argument.default is not ...
            and not argument.secret
        ):
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
                    ),
                )

            kwargs["help"] = (
                f"{kwargs.get('help', '')} [ENV: {argument.env_var}]"
            ).strip()

            if argument.env_var in os.environ:
                self._used_env_vars.add(argument.env_var)
                if argument.secret:
                    self._used_secret_env_vars.add(argument.env_var)

        # Convert string boolean values from config/env to proper bools
        action = kwargs.get("action")
        default = kwargs.get("default")
        if isinstance(default, str) and action in (
            Actions.STORE_TRUE,
            Actions.STORE_FALSE,
            "store_true",
            "store_false",
        ):
            kwargs["default"] = parse_bool(default)

        default = kwargs.get("default")
        if default is not None and default is not ...:
            kwargs["required"] = False

        return dest, parser.add_argument(*aliases, **kwargs)

    @staticmethod
    def get_cli_name(name: str) -> str:
        return name.replace("_", "-")

    def get_env_var(self, name: str, argument: TypedArgument) -> Optional[str]:
        if argument.env_var is not None:
            return argument.env_var
        if self._auto_env_var_prefix is not None:
            return f"{self._auto_env_var_prefix}{name}".upper()
        return None

    def __init__(
        self,
        config_files: Iterable[Union[str, Path]] = (),
        auto_env_var_prefix: Optional[str] = None,
        strict_config: bool = False,
        config_parser_class: Type[AbstractDefaultsParser] = INIDefaultsParser,
        **kwargs: Any,
    ):
        super().__init__()
        self.current_subparsers: Tuple[AbstractParser, ...] = ()
        self._config_files = config_files

        # Parse config files using the specified parser class
        config_parser = config_parser_class(config_files, strict=strict_config)
        self._config = config_parser.parse()
        filenames = config_parser.loaded_files

        self._epilog = kwargs.pop("epilog", "")

        if config_files:
            # If not config files, we don't need to add any to the epilog
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
        self._used_secret_env_vars: Set[str] = set()

    @property
    def current_subparser(self) -> Optional["AbstractParser"]:
        if not self.current_subparsers:
            return None
        return self.current_subparsers[0]

    def _make_parser(
        self,
        parser: Optional[ArgumentParser] = None,
        parent_chain: Tuple["AbstractParser", ...] = (),
    ) -> Tuple[ArgumentParser, DestinationsType]:
        if parser is None:
            parser = ArgumentParser(
                epilog=self._epilog,
                **self._parser_kwargs,
            )

        destinations: DestinationsType = defaultdict(set)
        self._fill_arguments(destinations, parser)
        self._fill_groups(destinations, parser)
        if self.__subparsers__:
            self._fill_subparsers(destinations, parser, parent_chain)

        return parser, destinations

    def create_parser(self) -> ArgumentParser:
        """
        Create an ArgumentParser instance without parsing arguments.
        Can be used to inspect the parser structure in external integrations.
        NOT AN ALTERNATIVE TO parse_args, because it does not back populates
        the parser attributes.
        """
        parser, _ = self._make_parser()
        return parser

    def _fill_arguments(
        self,
        destinations: DestinationsType,
        parser: ArgumentParser,
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

            if default is not None and default is not ... and argument.required:
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
        self,
        destinations: DestinationsType,
        parser: ArgumentParser,
    ) -> None:
        for group_name, group in self.__argument_groups__.items():
            group_parser = parser.add_argument_group(
                title=group._title,
                description=group._description,
            )
            config = self._config.get(group_name, {})

            for name, argument in group.__arguments__.items():
                aliases = set(argument.aliases)
                if group._prefix is not None:
                    prefix = group._prefix
                else:
                    prefix = group_name
                dest = f"{prefix}_{name}" if prefix else name

                if not aliases:
                    aliases.add(f"--{self.get_cli_name(dest)}")

                default = config.get(
                    name,
                    group._defaults.get(name, argument.default),
                )
                argument = argument.copy(
                    default=default,
                    env_var=self.get_env_var(dest, argument),
                )
                dest, action = self._add_argument(
                    group_parser,
                    argument,
                    dest,
                    *aliases,
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
        self,
        destinations: DestinationsType,
        parser: ArgumentParser,
        parent_chain: Tuple["AbstractParser", ...] = (),
    ) -> None:
        subparsers = parser.add_subparsers()
        subparser: AbstractParser
        destinations["current_subparsers"].add(
            Destination(
                target=self,
                attribute="current_subparsers",
                argument=None,
                action=None,
            ),
        )

        for subparser_name, subparser in self.__subparsers__.items():
            # Build the chain for this subparser level
            subparser_chain = (subparser,) + parent_chain
            current_parser, subparser_dests = subparser._make_parser(
                subparsers.add_parser(
                    subparser_name,
                    **subparser._parser_kwargs,
                ),
                parent_chain=subparser_chain,
            )
            subparser.__parent__ = self
            current_parser.set_defaults(
                current_subparsers=subparser_chain,
            )
            for key, value in subparser_dests.items():
                destinations[key].update(value)

    def parse_args(
        self: ParserType,
        args: Optional[List[str]] = None,
        sanitize_secrets: bool = False,
    ) -> ParserType:
        parser, destinations = self._make_parser()
        parsed_ns = parser.parse_args(args=args)

        # Get the chain of selected subparsers from the namespace
        selected_subparsers: Tuple[AbstractParser, ...] = getattr(
            parsed_ns, "current_subparsers", ()
        )

        for key, dests in destinations.items():
            for dest in dests:
                target = dest.target
                name = dest.attribute
                argument = dest.argument
                action = dest.action

                # Skip subparsers that weren't selected
                if (
                    isinstance(target, AbstractParser)
                    and target is not self
                    and target not in selected_subparsers
                ):
                    continue

                parsed_value = getattr(parsed_ns, key, None)

                if isinstance(action, ConfigAction):
                    action(parser, parsed_ns, parsed_value, None)
                    parsed_value = getattr(parsed_ns, key)

                if argument is not None:
                    if argument.secret and isinstance(parsed_value, str):
                        parsed_value = SecretString(parsed_value)
                    if argument.converter is not None:
                        if argument.nargs and parsed_value is None:
                            parsed_value = []
                        try:
                            parsed_value = argument.converter(parsed_value)
                        except Exception as e:
                            msg = f"failed to convert {parsed_value!r}: {e}"
                            raise ArgumentError(action, msg) from e

                # Ensure current_subparsers is always a tuple, not None
                if name == "current_subparsers" and parsed_value is None:
                    parsed_value = ()

                setattr(target, name, parsed_value)

        if sanitize_secrets:
            for name in self._used_secret_env_vars:
                os.environ.pop(name, None)
            self._used_secret_env_vars.clear()

        return self

    def print_help(self) -> None:
        parser, _ = self._make_parser()
        return parser.print_help()

    def sanitize_env(self, only_secrets: bool = False) -> None:
        if only_secrets:
            for name in self._used_secret_env_vars:
                os.environ.pop(name, None)
            self._used_secret_env_vars.clear()
        else:
            for name in self._used_env_vars:
                os.environ.pop(name, None)
            self._used_env_vars.clear()
            self._used_secret_env_vars.clear()

    def __call__(self) -> Any:
        """
        Override this function if you want to equip your parser with an action.

        By default this calls the current_subparser's __call__ method if
        there is a current_subparser, otherwise returns None.

        Example:
            class Parser(argclass.Parser):
                def __call__(self) -> Any:
                    print("Hello world!")

            parser = Parser()
            parser.parse_args([])
            parser()  # Will print "Hello world!"

        When you have subparsers:
            class SubParser(argclass.Parser):
                def __call__(self) -> Any:
                    print("In subparser!")

            class Parser(argclass.Parser):
                sub = SubParser()

            parser = Parser()
            parser.parse_args(["sub"])
            parser()  # Will print "In subparser!"
        """
        if self.current_subparser is not None:
            return self.current_subparser()
        return None
