"""Core parser classes for argclass."""

import copy
import os
import weakref
from abc import ABCMeta
from argparse import Action, ArgumentParser
from collections import defaultdict
from enum import EnumMeta
from pathlib import Path
from types import MappingProxyType
from typing import (
    Any,
    NamedTuple,
    TypeVar,
)
from collections.abc import Iterable, Mapping, MutableMapping

from .actions import ConfigAction
from .defaults import (
    AbstractDefaultsParser,
    INIDefaultsParser,
    ValueKind,
)
from .exceptions import (
    ArgclassError,
    ArgumentDefinitionError,
    ComplexTypeError,
    TypeConversionError,
)
from .secret import SecretString
from .store import AbstractGroup, AbstractParser, TypedArgument
from .types import Actions, Nargs
from .utils import (
    _unwrap_container_type,
    coerce_env_default,
    deep_getattr,
    own_annotation_keys,
    parse_bool,
    resolve_annotations,
    unwrap_literal,
    unwrap_optional,
)


def _make_action_true_argument(
    kind: type,
    default: Any = None,
) -> TypedArgument:
    """Create a TypedArgument for boolean types."""
    kw: dict[str, Any] = {"type": kind}
    if kind is bool:
        if default is False:
            kw["action"] = Actions.STORE_TRUE
            kw["default"] = False
        elif default is True:
            kw["action"] = Actions.STORE_FALSE
            kw["default"] = True
        else:
            raise TypeError(f"Can not set default {default!r} for bool")
    else:  # kind == Optional[bool], only other case from _type_is_bool
        kw["action"] = Actions.STORE
        kw["type"] = parse_bool
        kw["default"] = None
    return TypedArgument(**kw)


def _type_is_bool(kind: type) -> bool:
    """Check if a type is bool or Optional[bool]."""
    return kind is bool or kind == bool | None


# Attribute names argclass uses for internal parser state. They are
# defined on the base classes and must not be shadowed by user-defined
# arguments, groups, or subparsers.
RESERVED_ATTRIBUTES = frozenset(
    {
        "current_subparsers",
        "current_subparser",
        "__parent__",
    }
)


def reserved_name_error(name: str) -> ArgumentDefinitionError:
    return ArgumentDefinitionError(
        f"{name!r} is a reserved argclass attribute and cannot be used "
        f"as an argument, group, or subparser name.",
        field_name=name,
        hint="Rename it; argclass stores internal parser state under "
        "this name.",
    )


def shadowed_member_error(name: str, member: Any) -> ArgumentDefinitionError:
    kind = "property" if isinstance(member, property) else "method"
    return ArgumentDefinitionError(
        f"Field {name!r} would shadow the {kind} {name!r} defined on a "
        f"base class or in the class body; argclass would silently "
        f"replace it and break the parser API.",
        field_name=name,
        hint="Rename the field, or pass the callable explicitly via "
        "Argument(default=...) if a callable default is intended.",
    )


def _shadowed_api_member(
    key: str,
    attrs: Mapping[str, Any],
    bases: tuple[type, ...],
) -> Any | None:
    """Return the method/property that a member named ``key`` would
    clobber, or ``None`` when the name is safe to use.

    Registering ``key`` as an argument replaces the class attribute
    (the metaclass stores ``...`` placeholders and ``parse_args``
    assigns parsed values), so a name that currently resolves to a
    callable or property — ``parse_args``, a user-defined helper —
    must be rejected instead of silently destroying the API.
    Inherited argclass members (arguments, groups, subparsers and
    their ``...`` placeholders) and plain data defaults remain
    legitimate redefinition targets.
    """
    own = attrs.get(key)
    if (
        own is not None
        and not isinstance(own, (TypedArgument, AbstractGroup, AbstractParser))
        and (
            callable(own)
            or isinstance(own, (property, classmethod, staticmethod))
        )
    ):
        return own
    for base in bases:
        if not hasattr(base, key):
            continue
        value = getattr(base, key)
        if value is None or value is Ellipsis:
            return None
        if isinstance(value, (TypedArgument, AbstractGroup, AbstractParser)):
            return None
        if callable(value) or isinstance(value, property):
            return value
        return None
    return None


class Meta(ABCMeta):
    """Metaclass for Parser and Group classes."""

    def __new__(
        mcs,
        name: str,
        bases: tuple[type["Meta"], ...],
        attrs: dict[str, Any],
    ) -> "Meta":
        # Import here to avoid circular import
        from .factory import EnumArgument

        # Create the class first to ensure annotations are available
        # Python 3.14+ (PEP 649) defers annotation evaluation, so
        # __annotations__ may not be in attrs during class creation
        cls = super().__new__(mcs, name, bases, attrs)

        # Now get annotations from the created class
        annotations = resolve_annotations(cls)
        # Annotations defined directly on this class (not inherited).
        own_annotations = own_annotation_keys(cls)

        # Seed the registries with inherited members so unannotated
        # arguments, groups, and subparsers declared on a base class
        # survive subclassing (annotated fields are re-collected below
        # from the merged annotations either way).
        arguments: dict[str, Any] = {}
        argument_groups: dict[str, Any] = {}
        subparsers: dict[str, Any] = {}
        for base in reversed(bases):
            arguments.update(getattr(base, "__arguments__", {}))
            argument_groups.update(getattr(base, "__argument_groups__", {}))
            subparsers.update(getattr(base, "__subparsers__", {}))

        # Keys (re)defined by this class itself, as opposed to seeded.
        own_keys: set[str] = set()

        def classify(key: str, value: Any, into: dict[str, Any]) -> None:
            # A redefinition may change category (e.g. an inherited
            # argument overridden by a group); drop the stale entry
            # from the other registries.
            for registry in (arguments, argument_groups, subparsers):
                if registry is not into:
                    registry.pop(key, None)
            into[key] = value
            own_keys.add(key)

        for key, kind in annotations.items():
            if key in RESERVED_ATTRIBUTES:
                # Inherited internal attributes are skipped; declaring one
                # in this class's own body shadows internal state -> error.
                if key in own_annotations:
                    raise reserved_name_error(key)
                continue
            if key.startswith("_"):
                continue

            # A purely inherited member (not re-annotated and not
            # re-assigned here) is already fully processed in the
            # seeded registries. Rebuilding it from the annotation
            # would lose state the base class attrs no longer carry:
            # plain defaults become ``...`` placeholders on the class,
            # so a re-build would turn ``name: str = "x"`` into a
            # required argument in every subclass.
            if (
                key not in own_annotations
                and key not in attrs
                and (
                    key in arguments
                    or key in argument_groups
                    or key in subparsers
                )
            ):
                continue

            try:
                argument = deep_getattr(key, attrs, *bases)
                has_explicit_default = True
            except KeyError:
                argument = None
                has_explicit_default = False

            shadowed = _shadowed_api_member(key, attrs, bases)
            if shadowed is not None:
                raise shadowed_member_error(key, shadowed)

            # Subparsers are defined by instances, not annotations: a
            # bare ``serve: Serve`` (or ``Serve | None``) would
            # otherwise fall through and silently become a required
            # CLI argument with ``type=Serve``.
            parser_kind: type | None = None
            if isinstance(kind, type) and issubclass(kind, AbstractParser):
                parser_kind = kind
            else:
                try:
                    _inner = unwrap_optional(kind)
                except ComplexTypeError:
                    _inner = None
                if isinstance(_inner, type) and issubclass(
                    _inner, AbstractParser
                ):
                    parser_kind = _inner
            if parser_kind is not None and not isinstance(
                argument, AbstractParser
            ):
                raise ArgumentDefinitionError(
                    f"Subparser field '{key}' is annotated with parser "
                    f"class {parser_kind.__name__} but no instance is "
                    f"assigned; an annotation alone cannot define a "
                    f"subcommand.",
                    field_name=key,
                    hint=f"Use '{key} = {parser_kind.__name__}()'.",
                )

            annotated_group_cls: type[AbstractGroup] | None = None
            if isinstance(kind, type) and issubclass(kind, AbstractGroup):
                annotated_group_cls = kind
            else:
                try:
                    optional_inner = unwrap_optional(kind)
                except ComplexTypeError:
                    optional_inner = None
                    # Complex union (e.g. `G | int`, `G | None | int`,
                    # `G1 | G2`). If any member is a Group, raise a
                    # Group-specific message — otherwise the generic
                    # argument path raises the same ComplexTypeError
                    # without mentioning Group, which is confusing.
                    union_groups = [
                        arg
                        for arg in getattr(kind, "__args__", ())
                        if isinstance(arg, type)
                        and issubclass(arg, AbstractGroup)
                    ]
                    if union_groups:
                        g = union_groups[0]
                        raise ArgumentDefinitionError(
                            f"Group field '{key}' cannot be part of a "
                            f"complex Union ({kind!r}). Group instances "
                            f"hold parsed state and only one Group "
                            f"class is meaningful per attribute.",
                            field_name=key,
                            hint=(
                                f"Use '{key}: {g.__name__}' "
                                f"(auto-instantiated) or "
                                f"'{key}: {g.__name__} = "
                                f"{g.__name__}()'."
                            ),
                        )
                if (
                    optional_inner is not None
                    and isinstance(optional_inner, type)
                    and issubclass(optional_inner, AbstractGroup)
                ):
                    raise ArgumentDefinitionError(
                        f"Group field '{key}' cannot be Optional. Group "
                        f"instances hold parsed state and cannot be None.",
                        field_name=key,
                        hint=(
                            f"Use '{key}: {optional_inner.__name__}' "
                            f"(auto-instantiated) or "
                            f"'{key}: {optional_inner.__name__} = "
                            f"{optional_inner.__name__}()'."
                        ),
                    )

            if annotated_group_cls is not None:
                if isinstance(argument, AbstractGroup):
                    if not isinstance(argument, annotated_group_cls):
                        raise ArgumentDefinitionError(
                            f"Group field '{key}' annotated as "
                            f"{annotated_group_cls.__name__} but assigned "
                            f"an incompatible instance of "
                            f"{type(argument).__name__}",
                            field_name=key,
                        )
                elif not has_explicit_default or argument is Ellipsis:
                    argument = annotated_group_cls()
                    setattr(cls, key, argument)
                else:
                    raise ArgumentDefinitionError(
                        f"Group field '{key}' got a non-Group default "
                        f"value: {argument!r}",
                        field_name=key,
                        hint=(
                            f"Use '{key}: {annotated_group_cls.__name__}' "
                            f"(auto-instantiated) or "
                            f"'{key}: {annotated_group_cls.__name__} = "
                            f"{annotated_group_cls.__name__}()'."
                        ),
                    )

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
                    # Plain bool fields must have explicit default (True/False)
                    # because store_true/store_false can't be "required".
                    # Optional[bool] is allowed without default (tri-state).
                    # For inherited fields, reuse the existing TypedArgument.
                    inherited_arg = None
                    for b in bases:
                        base_args = getattr(b, "__arguments__", {})
                        if key in base_args:
                            inherited_arg = base_args[key]
                            break

                    if inherited_arg is not None:
                        argument = inherited_arg
                    elif kind is bool and (
                        argument is None or argument is Ellipsis
                    ):
                        raise TypeError(
                            f"Bool field '{key}' must have an explicit default "
                            f"(True or False). Use 'flag: bool = False' or "
                            f"'flag: bool = True', or Optional[bool] for "
                            f"tri-state."
                        )
                    else:
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
                            nargs: str | Nargs = Nargs.ONE_OR_MORE
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
                    # The same Argument() instance may be shared by
                    # several fields or classes; mutate a private copy
                    # so this field's inferred type/nargs/choices do
                    # not leak into the other bindings.
                    argument = argument.copy()
                    # First try to unwrap optional
                    optional_inner = unwrap_optional(kind)
                    if optional_inner is not None:
                        kind = optional_inner

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
                        else:
                            raise TypeError(
                                f"Invalid default {default!r} for bool"
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
                classify(key, argument, arguments)
            elif isinstance(argument, AbstractGroup):
                classify(key, argument, argument_groups)
            else:
                # Only Parser instances can reach this point: the
                # block above converts every non-argclass value into
                # a TypedArgument.
                classify(key, argument, subparsers)

        for key, value in attrs.items():
            if key in RESERVED_ATTRIBUTES:
                # A reserved name assigned an argument/group/subparser
                # value shadows internal state; internal properties and
                # plain defaults are left untouched.
                if isinstance(
                    value, (TypedArgument, AbstractGroup, AbstractParser)
                ):
                    raise reserved_name_error(key)
                continue
            if key.startswith("_"):
                continue

            # Skip if already processed from annotations
            if key in own_keys:
                continue

            if isinstance(
                value, (TypedArgument, AbstractGroup, AbstractParser)
            ):
                shadowed = _shadowed_api_member(key, attrs, bases)
                if shadowed is not None:
                    raise shadowed_member_error(key, shadowed)

            if isinstance(value, TypedArgument):
                classify(key, value, arguments)
            elif isinstance(value, AbstractGroup):
                classify(key, value, argument_groups)
            elif isinstance(value, AbstractParser):
                classify(key, value, subparsers)

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
    argument: TypedArgument | None
    action: Action | None


DestinationsType = MutableMapping[str, set[Destination]]


class Group(AbstractGroup, Base):
    """Argument group for organizing related arguments."""

    def __init__(
        self,
        title: str | None = None,
        description: str | None = None,
        prefix: str | None = None,
        defaults: Mapping[str, Any] | None = None,
    ):
        self._title = title
        self._description = description
        self._prefix = prefix
        self._defaults: Mapping[str, Any] = defaults or {}


def _group_reuse_error(path: str) -> ArgclassError:
    return ArgclassError(
        "Group instance is referenced more than once in the parser "
        f"tree (current path: {path}): the group tree must not "
        "contain cycles.",
        hint="Remove the self-reference; a group cannot (directly or "
        "indirectly) contain itself.",
    )


def _clone_group_tree(
    group: Group,
    ancestors: set[int],
    attr_path: tuple[str, ...],
) -> Group:
    """Copy ``group`` and its nested groups for one parser instance.

    The group instances registered by the metaclass live on the class
    body and would otherwise be shared by every instance of the Parser
    class — a second ``parse_args()`` on another instance would
    overwrite the first one's values.

    Because every occurrence gets its own copy, assigning one Group
    instance to several attributes is fine — each binding becomes an
    independent copy. ``ancestors`` holds the ids along the current
    path only, so the recursion rejects exactly the unclonable case:
    a group that (directly or indirectly) contains itself.
    """
    if id(group) in ancestors:
        raise _group_reuse_error(".".join(attr_path))
    ancestors.add(id(group))
    try:
        clone = copy.copy(group)
        nested: dict[str, Group] = {}
        for child_name, child in group.__argument_groups__.items():
            child_clone = _clone_group_tree(
                child, ancestors, attr_path + (child_name,)
            )
            setattr(clone, child_name, child_clone)
            nested[child_name] = child_clone
        clone.__argument_groups__ = MappingProxyType(nested)
        return clone
    finally:
        ancestors.discard(id(group))


ParserType = TypeVar("ParserType", bound="Parser")


# Out-of-band back-references: argparse_parser -> argclass Parser.
# Lets custom actions (e.g. ``GenerateConfigAction``) recover the
# argclass Parser without mutating any argparse object. Auto-cleans
# entries when the argparse parser is garbage-collected.
_BackRefMap = weakref.WeakKeyDictionary
_argclass_back_refs: "_BackRefMap[ArgumentParser, AbstractParser]" = (
    _BackRefMap()
)


def get_argclass_parser(
    argparse_parser: ArgumentParser,
) -> "Parser | None":
    """Return the :class:`argclass.Parser` that built
    ``argparse_parser``, or ``None`` if it wasn't built through
    argclass (e.g. a bare ``argparse.ArgumentParser``).

    Useful for writing custom argparse Actions that need access to
    the argclass-level parser at invocation time —
    :class:`argclass.GenerateConfigAction` uses this internally.
    """
    return _argclass_back_refs.get(argparse_parser)  # type: ignore[return-value]


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
    ) -> tuple[str, Action]:
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
            # Only coerce when the env var was actually set; an
            # absent env must not retype the existing default
            # (a string ``"0"`` default with ``type=int`` would
            # otherwise silently become the integer ``0`` here).
            raw = os.environ.get(argument.env_var)
            if raw is not None:
                kwargs["default"] = coerce_env_default(raw, argument)
                self._used_env_vars.add(argument.env_var)
                if argument.secret:
                    self._used_secret_env_vars.add(argument.env_var)

            kwargs["help"] = (
                f"{kwargs.get('help', '')} [ENV: {argument.env_var}]"
            ).strip()

        # Safety net: env vars are read above, so default may have changed.
        # If we now have a default, remove the required flag.
        # Note: positional arguments don't support "required" in argparse.
        # Check actual aliases (not argument.aliases which may be empty).
        is_optional = any(a.startswith("-") for a in aliases)

        # Positional arguments don't support "required" in argparse
        if not is_optional and "required" in kwargs:
            raise ArgumentDefinitionError(
                "positional arguments do not support 'required' parameter",
                field_name=dest,
                aliases=tuple(aliases),
                hint="Remove 'required' from positional argument, or add '--' "
                "prefix to make it optional",
            )

        default = kwargs.get("default")
        if (
            is_optional
            and default is not None
            and default is not ...
            and "required" in kwargs
        ):
            kwargs["required"] = False

        try:
            return dest, parser.add_argument(*aliases, **kwargs)
        except Exception as e:
            raise ArgumentDefinitionError(
                str(e),
                field_name=dest,
                aliases=tuple(aliases),
                kwargs=kwargs,
                hint="Check that argument options are compatible with argparse",
            ) from e

    @staticmethod
    def get_cli_name(name: str) -> str:
        return name.replace("_", "-")

    def get_env_var(self, name: str, argument: TypedArgument) -> str | None:
        if argument.env_var is not None:
            return argument.env_var
        if self._auto_env_var_prefix is not None:
            return f"{self._auto_env_var_prefix}{name}".upper()
        return None

    def __init__(
        self,
        config_files: Iterable[str | Path] = (),
        auto_env_var_prefix: str | None = None,
        strict_config: bool = False,
        config_parser_class: type[AbstractDefaultsParser] = INIDefaultsParser,
        **kwargs: Any,
    ):
        super().__init__()
        self.current_subparsers: tuple[AbstractParser, ...] = ()
        self._config_files = config_files

        # Parse config files using the specified parser class
        self._config_parser = config_parser_class(
            config_files, strict=strict_config
        )
        self._config = self._config_parser.parse()
        # Backward compatibility: ensure _values is populated for custom parsers
        if not self._config_parser._values:
            self._config_parser._values = dict(self._config)
        filenames = self._config_parser.loaded_files

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
        self._used_env_vars: set[str] = set()
        self._used_secret_env_vars: set[str] = set()
        self._materialize_members()

    def _materialize_members(self) -> None:
        """Give this parser instance its own copies of the declared
        groups and subparsers.

        The instances collected by the metaclass live on the class
        body and are shared by every instance of this Parser class;
        parsing through them would let a second instance overwrite
        the first one's values. Copying them per instance
        (recursively, for nested groups and subparser trees) makes
        every Parser instance own its parsed state, while the
        class-level prototypes stay pristine.
        """
        cls = type(self)

        ancestors: set[int] = set()
        groups: dict[str, Group] = {}
        for name, group in cls.__argument_groups__.items():
            clone = _clone_group_tree(group, ancestors, (name,))
            setattr(self, name, clone)
            groups[name] = clone
        self.__argument_groups__ = MappingProxyType(groups)

        subparsers: dict[str, Any] = {}
        for name, subparser in cls.__subparsers__.items():
            sub_clone = copy.copy(subparser)
            # The shallow copy still references the prototype's own
            # member clones and env-var bookkeeping; rebuild them.
            sub_clone._materialize_members()
            sub_clone._used_env_vars = set(subparser._used_env_vars)
            sub_clone._used_secret_env_vars = set(
                subparser._used_secret_env_vars
            )
            setattr(self, name, sub_clone)
            subparsers[name] = sub_clone
        self.__subparsers__ = MappingProxyType(subparsers)

    @property
    def current_subparser(self) -> "AbstractParser | None":
        if not self.current_subparsers:
            return None
        return self.current_subparsers[0]

    def _make_parser(
        self,
        parser: ArgumentParser | None = None,
        parent_chain: tuple["AbstractParser", ...] = (),
    ) -> tuple[ArgumentParser, DestinationsType]:
        if parser is None:
            parser = ArgumentParser(
                epilog=self._epilog,
                **self._parser_kwargs,
            )

        _argclass_back_refs[parser] = self

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

    @staticmethod
    def _get_value_kind(argument: TypedArgument) -> ValueKind:
        """Determine ValueKind from argument for config loading."""
        # Check for nargs that produce lists
        if argument.nargs in (Nargs.ONE_OR_MORE, Nargs.ZERO_OR_MORE, "*", "+"):
            return ValueKind.SEQUENCE
        if isinstance(argument.nargs, int) and argument.nargs >= 1:
            return ValueKind.SEQUENCE

        # Check for bool actions
        if argument.action in (
            Actions.STORE_TRUE,
            Actions.STORE_FALSE,
            "store_true",
            "store_false",
        ):
            return ValueKind.BOOL

        return ValueKind.STRING

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

            # Get default from config with type-aware loading
            kind = self._get_value_kind(argument)
            config_default = self._config_parser.get_value(name, kind)

            # Apply type converter to config values
            if config_default is not None and argument.type is not None:
                if isinstance(config_default, (list, tuple)):
                    config_default = [argument.type(x) for x in config_default]
                else:
                    # Check if already correct type (only for types)
                    type_func = argument.type
                    try:
                        is_correct_type = isinstance(config_default, type_func)
                    except TypeError:
                        # type_func is a function, not a type
                        is_correct_type = False
                    if not is_correct_type:
                        config_default = type_func(config_default)

            default = (
                config_default
                if config_default is not None
                else argument.default
            )

            argument = argument.copy(
                aliases=aliases,
                env_var=self.get_env_var(name, argument),
                default=default,
            )

            # Check if this will be an optional argument (has -- prefix)
            is_optional = any(a.startswith("-") for a in aliases)
            if is_optional and argument.has_default and argument.required:
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
        visited: set[int] = set()
        for group_name, group in self.__argument_groups__.items():
            cli_seg = group._prefix if group._prefix is not None else group_name
            cli_path: tuple[str, ...] = (cli_seg,) if cli_seg else ()
            self._fill_group(
                group=group,
                parser=parser,
                attr_path=(group_name,),
                cli_path=cli_path,
                destinations=destinations,
                visited=visited,
            )

    def _fill_group(
        self,
        group: "Group",
        parser: ArgumentParser,
        attr_path: tuple[str, ...],
        cli_path: tuple[str, ...],
        destinations: DestinationsType,
        visited: set[int],
    ) -> None:
        # Backstop: instance trees are validated at construction time
        # by ``_clone_group_tree``; this catches cycles wired into the
        # per-instance mappings after ``__init__``.
        if id(group) in visited:
            raise _group_reuse_error(".".join(attr_path))
        visited.add(id(group))

        section = ".".join(attr_path)
        cli_prefix = "_".join(cli_path)

        title = group._title
        if title is None and len(attr_path) > 1:
            title = section

        group_parser = parser.add_argument_group(
            title=title,
            description=group._description,
        )

        for name, argument in group.__arguments__.items():
            aliases = set(argument.aliases)
            dest = f"{cli_prefix}_{name}" if cli_prefix else name

            if not aliases:
                aliases.add(f"--{self.get_cli_name(dest)}")

            # Get default from config with type-aware loading
            kind = self._get_value_kind(argument)
            config_default = self._config_parser.get_value(
                name,
                kind,
                section=section,
            )

            # Apply type converter to config values
            if config_default is not None and argument.type is not None:
                type_func = argument.type
                if isinstance(config_default, (list, tuple)):
                    config_default = [type_func(x) for x in config_default]
                else:
                    val = config_default
                    try:
                        already_correct = isinstance(val, type_func)
                    except TypeError:
                        already_correct = False
                    if not already_correct:
                        config_default = type_func(val)

            default = (
                config_default
                if config_default is not None
                else group._defaults.get(name, argument.default)
            )

            argument = argument.copy(
                default=default,
                env_var=self.get_env_var(dest, argument),
            )

            is_optional = any(a.startswith("-") for a in aliases)
            if is_optional and argument.has_default and argument.required:
                argument = argument.copy(required=False)

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

        for child_name, child_group in group.__argument_groups__.items():
            child_cli_seg = (
                child_group._prefix
                if child_group._prefix is not None
                else child_name
            )
            child_cli_path = cli_path + (
                (child_cli_seg,) if child_cli_seg else ()
            )
            self._fill_group(
                group=child_group,
                parser=parser,
                attr_path=attr_path + (child_name,),
                cli_path=child_cli_path,
                destinations=destinations,
                visited=visited,
            )

    def _fill_subparsers(
        self,
        destinations: DestinationsType,
        parser: ArgumentParser,
        parent_chain: tuple["AbstractParser", ...] = (),
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
        args: list[str] | None = None,
        sanitize_secrets: bool = False,
    ) -> ParserType:
        parser, destinations = self._make_parser()
        parsed_ns = parser.parse_args(args=args)

        # Get the chain of selected subparsers from the namespace
        selected_subparsers: tuple[AbstractParser, ...] = getattr(
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
                    if argument.secret:
                        if isinstance(parsed_value, str):
                            parsed_value = SecretString(parsed_value)
                        elif isinstance(parsed_value, (list, tuple)):
                            # nargs secrets: wrap each element so a
                            # repr of the list cannot leak the values.
                            parsed_value = type(parsed_value)(
                                SecretString(v) if isinstance(v, str) else v
                                for v in parsed_value
                            )
                    if argument.converter is not None:
                        if argument.nargs and parsed_value is None:
                            parsed_value = []
                        try:
                            parsed_value = argument.converter(parsed_value)
                        except Exception as e:
                            raise TypeConversionError(
                                f"converter {argument.converter!r} failed: {e}",
                                field_name=name,
                                value=parsed_value,
                                hint="Check that the converter function "
                                "handles this value type",
                            ) from e

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

        By default, this calls the current_subparser's __call__ method if
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
