"""Config-file generators: render an argclass Parser to INI/JSON/TOML/.env.

Symmetric counterpart to ``argclass/defaults.py`` (which READS configs).
The parser tree is walked once, yielding :class:`ConfigField` records;
generators consume that iterator and produce a format-specific string.

Subclass :class:`ConfigGenerator` and override :meth:`render` to add a
new format. The walking + Action wiring are shared — your subclass only
decides how to turn a stream of fields into text.

Usage::

    import argclass
    from argclass.emit import GenerateConfigAction, INIConfigGenerator

    class CLI(argclass.Parser):
        host: str = "localhost"
        generate_config = argclass.Argument(
            action=GenerateConfigAction,
            generator=INIConfigGenerator,
            metavar="FILE",
        )

The attribute name auto-derives the CLI flag, so end users run
``myapp --generate-config /etc/myapp.ini`` to write the file, or
``myapp --generate-config -`` to print to stdout.

Security note: secret values are emitted as-is by default. Pass
``mask_secrets=True`` to the generator (or to its
``GenerateConfigAction`` wrapping via an instance) to replace
``Secret()`` field values with :attr:`SecretString.PLACEHOLDER`,
so a generated file can be shared as a template without leaking
credentials. Treat any unmasked generated file like a
credential-bearing file.
"""

import argparse
import json
import os
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path, PurePath
from typing import (
    Any,
    IO,
    cast,
)
from collections.abc import Iterable, Iterator, Sequence

from .parser import get_argclass_parser
from .secret import SecretString
from .store import AbstractGroup, AbstractParser, TypedArgument
from .types import Actions
from .utils import coerce_env_default


class NonConfigAction(argparse.Action):
    """Base class for argparse Actions that should NOT appear in
    config dumps produced by :class:`ConfigGenerator` subclasses.

    Use this as a base for any "fire and exit" style action — like
    ``--version``, ``--check-updates``, or ``--generate-config``
    itself. ``ConfigGenerator`` checks ``__emit_config__`` on the
    action class; when it is ``False``, the argument is skipped.

    Stateful custom actions don't need to inherit anything — they're
    included by default. Only inherit from ``NonConfigAction`` (or
    set ``__emit_config__ = False`` manually) for actions whose
    presence in a dumped config makes no sense.
    """

    __emit_config__ = False


def should_emit(argument: TypedArgument) -> bool:
    """True if this argument should appear in a generated config.

    Action classes opt out via ``__emit_config__ = False`` (e.g. by
    inheriting :class:`NonConfigAction`). argparse's built-in
    ``--help`` / ``--version`` actions are recognised by enum value
    since we cannot annotate argparse internals.
    """
    action = argument.action
    if isinstance(action, type):
        return bool(getattr(action, "__emit_config__", True))
    if action in (Actions.VERSION, Actions.HELP):
        return False
    return True


def current_value(
    target: Any,
    name: str,
    argument: TypedArgument,
    *,
    namespace: argparse.Namespace | None = None,
    dest: str | None = None,
    env_var: str | None = None,
) -> Any:
    """Read the current value for ``name`` on a Parser/Group instance.

    Priority (highest first):

    1. An argparse ``Namespace`` under ``dest`` — when provided, it
       represents the active parse and wins over stale instance
       state. Used by :class:`GenerateConfigAction` so a reused
       parser doesn't dump values from an earlier ``parse_args``
       call.
    2. The instance ``__dict__`` (set when an earlier
       ``parse_args`` completed, or when the field is a Group whose
       attributes argclass populated after parsing).
    3. ``os.environ[env_var]`` — covers env vars when the dump
       runs before argclass has applied them to ``__dict__``.
    4. The argument's declared default.

    Env values arrive as strings; we apply ``argument.type`` when it
    is callable, so the dump reflects the same type argclass would
    bind at parse time.
    """
    if namespace is not None and dest is not None and hasattr(namespace, dest):
        value = getattr(namespace, dest)
        if value is not None:
            return value
    if name in target.__dict__:
        return target.__dict__[name]
    if env_var:
        raw = os.environ.get(env_var)
        if raw is not None:
            return coerce_env_default(raw, argument)
    return argument.default


def derive_env_var(
    auto_prefix: str | None,
    dest: str,
    argument: TypedArgument,
) -> str | None:
    """Compute the env-var name argclass would read for ``dest``.

    Mirrors :meth:`argclass.Parser.get_env_var`. Returns ``None`` when
    neither an explicit ``env_var`` on the argument nor an
    ``auto_env_var_prefix`` on the parser supplies one.
    """
    if argument.env_var is not None:
        return argument.env_var
    if auto_prefix is not None:
        return f"{auto_prefix}{dest}".upper()
    return None


def group_cli_segment(group: AbstractGroup, attr_name: str) -> str:
    """Return the CLI/env path segment for a group attribute, honoring
    the group's ``prefix=`` override."""
    prefix = getattr(group, "_prefix", None)
    return prefix if prefix is not None else attr_name


def escape_inline_string(value: str) -> str:
    """Escape a string for embedding inside double-quoted literals.

    Used by both TOML (always quoted) and the ``.env`` emitter
    (quoted on demand) so multi-line / tab / quote-bearing values
    stay on a single line and survive a shell parser.
    """
    return (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )


def normalize_value(value: Any) -> Any:
    """Convert non-config-native types to round-trippable forms.

    - ``Enum`` / ``IntEnum`` → ``.name`` (matches ``EnumArgument``
      which accepts member names).
    - ``set`` / ``frozenset`` → ``list`` (sorted when comparable, so
      output stays stable).
    - ``Path`` → ``str``.

    Already-native types (``str``/``int``/``float``/``bool``/``list``/
    ``tuple``/``None``) pass through. ``SecretString`` passes through
    too since it subclasses ``str``.
    """
    if isinstance(value, Enum):
        return value.name
    if isinstance(value, (set, frozenset)):
        try:
            return sorted(value)
        except TypeError:
            return list(value)
    if isinstance(value, PurePath):
        return str(value)
    return value


@dataclass(frozen=True)
class ConfigField:
    """A single leaf argument from the parser tree, ready to emit.

    A generator iterates these and writes them in the target format.
    Sections are derived from ``attr_path[:-1]``; the field key is
    ``attr_path[-1]``.

    Attributes
    ----------
    attr_path:
        Tuple of attribute names from the parser root down to the
        leaf (``("endpoint", "credentials", "username")``). The last
        element is the field name; everything before it forms the
        section path used by INI / TOML.
    cli_path:
        Same shape as ``attr_path`` but respecting per-group
        ``prefix=`` overrides — useful when reconstructing CLI flag
        names.
    dest:
        argparse ``dest`` for the field
        (``"endpoint_credentials_username"``). Joins ``cli_path``
        with underscores.
    argument:
        The owning :class:`TypedArgument`. Carries declared type,
        help, env_var, etc.
    target:
        The Parser or Group instance that owns this attribute. Lets
        renderers reach back into the source if needed.
    value:
        The resolved value, already :func:`normalize_value`-d so it
        round-trips through every supported format.
    env_var:
        Env var name argclass would read (explicit ``env_var=`` or
        derived from ``auto_env_var_prefix=``). ``None`` when no env
        var is configured.
    help:
        Help text declared on the argument, or ``None``.
    """

    attr_path: tuple[str, ...]
    cli_path: tuple[str, ...]
    dest: str
    argument: TypedArgument
    target: Any
    value: Any
    env_var: str | None
    help: str | None

    @property
    def section_path(self) -> tuple[str, ...]:
        """Path to the enclosing section, derived from ``attr_path``."""
        return self.attr_path[:-1]

    @property
    def key(self) -> str:
        """Bare leaf attribute name."""
        return self.attr_path[-1]


def iter_config_fields(
    parser: AbstractParser,
    *,
    namespace: argparse.Namespace | None = None,
    mask_secrets: bool = False,
) -> Iterator[ConfigField]:
    """Walk ``parser`` and yield one :class:`ConfigField` per leaf.

    Subparsers are skipped (they're runtime branches, not config
    state). Non-emittable arguments (``--help``, ``--version``, any
    :class:`NonConfigAction` subclass) are filtered out by
    :func:`should_emit`.

    ``namespace``, when provided, lets fields pick up CLI args that
    argparse has already parsed — used by
    :class:`GenerateConfigAction` mid-parse.

    When ``mask_secrets`` is true, any field whose argument was
    declared via :func:`argclass.Secret` (or carries
    ``secret=True``) gets its value replaced with
    :attr:`SecretString.PLACEHOLDER` so the dump can be shared as a
    template without leaking credentials.
    """
    auto_prefix = getattr(parser, "_auto_env_var_prefix", None)
    yield from iter_subtree_fields(
        parser,
        attr_path=(),
        cli_path=(),
        auto_prefix=auto_prefix,
        namespace=namespace,
        mask_secrets=mask_secrets,
    )


def iter_subtree_fields(
    target: Any,
    *,
    attr_path: tuple[str, ...] = (),
    cli_path: tuple[str, ...] = (),
    auto_prefix: str | None = None,
    namespace: argparse.Namespace | None = None,
    mask_secrets: bool = False,
) -> Iterator[ConfigField]:
    """Recursive walker used by :func:`iter_config_fields`.

    Power-users can call this directly to walk a sub-tree (for example
    to dump just one nested group). Pass the cumulative ``attr_path``
    and ``cli_path`` you want the yielded fields to carry.

    ``mask_secrets`` mirrors :func:`iter_config_fields` — see its
    docstring for the semantics.
    """
    node = cast(Any, target)
    cli_prefix = "_".join(cli_path)
    for name, argument in node.__arguments__.items():
        if not should_emit(argument):
            continue
        dest = f"{cli_prefix}_{name}" if cli_prefix else name
        env_var = derive_env_var(auto_prefix, dest, argument)
        raw = current_value(
            target,
            name,
            argument,
            namespace=namespace,
            dest=dest,
            env_var=env_var,
        )
        value = normalize_value(raw)
        if mask_secrets and argument.secret and value is not None:
            value = SecretString.PLACEHOLDER
        yield ConfigField(
            attr_path=attr_path + (name,),
            cli_path=cli_path + (name,),
            dest=dest,
            argument=argument,
            target=target,
            value=value,
            env_var=env_var,
            help=argument.help if argument.help else None,
        )
    for group_name, group in node.__argument_groups__.items():
        seg = group_cli_segment(group, group_name)
        child_cli = cli_path + ((seg,) if seg else ())
        yield from iter_subtree_fields(
            group,
            attr_path=attr_path + (group_name,),
            cli_path=child_cli,
            auto_prefix=auto_prefix,
            namespace=namespace,
            mask_secrets=mask_secrets,
        )


def fields_to_nested_dict(
    fields: Iterable[ConfigField],
    *,
    skip_none: bool = False,
) -> dict[str, Any]:
    """Build a nested dict from a stream of :class:`ConfigField`.

    Used by :class:`JSONConfigGenerator`. Each section path becomes a
    nested dict layer; the leaf attribute is set to ``field.value``.
    When ``skip_none`` is true, ``None`` values are omitted entirely
    so reloading falls back to the argument's own default.
    """
    out: dict[str, Any] = {}
    for field in fields:
        if skip_none and field.value is None:
            continue
        target = out
        for segment in field.section_path:
            sub = target.get(segment)
            if not isinstance(sub, dict):
                sub = {}
                target[segment] = sub
            target = sub
        target[field.key] = field.value
    return out


class ConfigGenerator:
    """Walks an argclass Parser and renders its state to a config
    string.

    Subclasses override :meth:`render`. The base
    :meth:`dump_to_string` and :meth:`dump` methods take care of
    walking the parser and writing to disk / stdout / a file object.

    Parameters
    ----------
    mask_secrets:
        When true, fields declared via :func:`argclass.Secret` (or
        otherwise carrying ``secret=True``) have their values
        replaced with :attr:`SecretString.PLACEHOLDER`. Use this to
        emit a credential-free template config; the resulting file
        is safe to commit / share. Default is ``False`` — the
        generator reproduces real credential values exactly so the
        file round-trips back into a working parser.
    """

    #: File extension hint. Subclasses set this.
    extension: str = ""

    def __init__(self, *, mask_secrets: bool = False) -> None:
        self.mask_secrets = mask_secrets

    def render(self, fields: Sequence[ConfigField]) -> str:
        """Render a sequence of :class:`ConfigField` records to text.

        Override this for a new format. ``fields`` is a materialised
        sequence — implementations may iterate it more than once
        (e.g. to split into header / sections) without burning
        through an exhausted iterator.

        Default implementation just raises — every format has to
        decide how to lay out fields.
        """
        raise NotImplementedError

    def dump_to_string(
        self,
        parser: AbstractParser,
        *,
        namespace: argparse.Namespace | None = None,
    ) -> str:
        """Walk ``parser`` and return the rendered config as a
        string."""
        # Materialise into a tuple so ``render`` (and any custom
        # subclass) can iterate the field stream multiple times.
        fields = tuple(
            iter_config_fields(
                parser,
                namespace=namespace,
                mask_secrets=self.mask_secrets,
            ),
        )
        return self.render(fields)

    def dump(
        self,
        parser: AbstractParser,
        dest: str | Path | IO[str],
        *,
        namespace: argparse.Namespace | None = None,
    ) -> None:
        """Write the rendered config to ``dest``.

        ``dest`` may be a filesystem path (as ``str`` or
        :class:`pathlib.Path`), a file-like object, or the string
        ``"-"`` for stdout.
        """
        content = self.dump_to_string(parser, namespace=namespace)
        if dest == "-":
            sys.stdout.write(content)
            return
        if isinstance(dest, (str, Path)):
            with open(dest, "w") as fp:
                fp.write(content)
            return
        dest.write(content)


def group_fields_by_section(
    fields: Iterable[ConfigField],
) -> "dict[tuple[str, ...], list[ConfigField]]":
    """Group a stream of fields by ``section_path``.

    Preserves the original order both for sections and for fields
    within each section.
    """
    sections: dict[tuple[str, ...], list[ConfigField]] = {}
    for field in fields:
        sections.setdefault(field.section_path, []).append(field)
    return sections


class INIConfigGenerator(ConfigGenerator):
    """Render a parser to INI.

    Top-level arguments go under ``[DEFAULT]`` (read by
    :class:`argclass.INIDefaultsParser`); nested groups become dotted
    sections (``[endpoint.credentials]``). Help text is emitted as
    ``; <text>`` comments above each key.

    Note: configparser's ``[DEFAULT]`` section would normally cascade
    into every other section, but
    :class:`argclass.INIDefaultsParser` strips that cascade on read so
    a top-level ``host`` cannot leak into a group's ``host`` attribute.
    """

    extension = ".ini"

    def render(self, fields: Sequence[ConfigField]) -> str:
        sections = group_fields_by_section(fields)
        lines: list[str] = []
        root_fields = sections.pop((), [])
        if root_fields:
            lines.append("[DEFAULT]")
            self._emit_fields(root_fields, lines)
            lines.append("")
        for path, items in sections.items():
            lines.append(f"[{'.'.join(path)}]")
            self._emit_fields(items, lines)
            lines.append("")
        return "\n".join(lines)

    def _emit_fields(
        self,
        fields: list[ConfigField],
        lines: list[str],
    ) -> None:
        for field in fields:
            if field.value is None:
                # configparser has no native None; dropping the key
                # lets the reloaded parser fall back to its default.
                continue
            if field.help:
                lines.append(f"; {field.help}")
            lines.append(f"{field.key} = {self.render_scalar(field.value)}")

    @staticmethod
    def render_scalar(value: Any) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (list, tuple)):
            return repr(list(value))
        return str(value)


class JSONConfigGenerator(ConfigGenerator):
    """Render a parser to JSON.

    Comments are not supported by JSON, so help text is dropped.
    Nested groups become nested objects.
    """

    extension = ".json"

    def render(self, fields: Sequence[ConfigField]) -> str:
        data = fields_to_nested_dict(fields)
        return json.dumps(self.coerce_value(data), indent=2) + "\n"

    def coerce_value(self, value: Any) -> Any:
        """Convert non-JSON-native types to serialisable equivalents."""
        if isinstance(value, dict):
            return {k: self.coerce_value(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [self.coerce_value(v) for v in value]
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        return str(value)


class TOMLConfigGenerator(ConfigGenerator):
    """Render a parser to TOML.

    Help text is emitted as ``# <text>`` comments above each key.
    Nested groups use dotted table headers (``[parent.child]``).

    Minimal hand-rolled emitter — covers ``str``/``int``/``float``/
    ``bool``/``list``/``None``. Other types are coerced via ``str()``.
    """

    extension = ".toml"

    def render(self, fields: Sequence[ConfigField]) -> str:
        sections = group_fields_by_section(fields)
        lines: list[str] = []
        root_fields = sections.pop((), [])
        for field in root_fields:
            if field.value is None:
                continue
            if field.help:
                lines.append(f"# {field.help}")
            lines.append(f"{field.key} = {self.render_value(field.value)}")
        if root_fields and sections:
            lines.append("")
        for path, items in sections.items():
            lines.append(f"[{'.'.join(path)}]")
            for field in items:
                if field.value is None:
                    continue
                if field.help:
                    lines.append(f"# {field.help}")
                lines.append(
                    f"{field.key} = {self.render_value(field.value)}",
                )
            lines.append("")
        return "\n".join(lines)

    def render_value(self, value: Any) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (int, float)):
            return repr(value)
        if isinstance(value, (list, tuple)):
            inner = ", ".join(self.render_value(v) for v in value)
            return f"[{inner}]"
        return self.render_string(value)

    @staticmethod
    def render_string(value: Any) -> str:
        return f'"{escape_inline_string(str(value))}"'


class EnvConfigGenerator(ConfigGenerator):
    """Render a parser to a ``.env``-style listing.

    Emits one ``KEY=value`` line per argument that has a resolvable
    env var (explicit ``env_var=`` on the argument or computed from
    the parser's ``auto_env_var_prefix=``). Arguments without an env
    var are skipped.

    Help text appears as ``# <text>`` comments above each key.
    ``None`` values are dropped. Lists serialise to Python literal
    syntax so argclass can ``ast.literal_eval`` them on read.

    Strings are quoted only when they contain whitespace, ``=``,
    ``#``, or other characters that would confuse a typical ``.env``
    parser.
    """

    extension = ".env"
    QUOTE_CHARS = frozenset(' \t\n\r"\\#=')

    def render(self, fields: Sequence[ConfigField]) -> str:
        lines: list[str] = []
        for field in fields:
            if field.env_var is None:
                continue
            if field.value is None:
                continue
            if field.help:
                lines.append(f"# {field.help}")
            lines.append(f"{field.env_var}={self.render_value(field.value)}")
        return "\n".join(lines) + ("\n" if lines else "")

    def render_value(self, value: Any) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (int, float)):
            return repr(value)
        if isinstance(value, (list, tuple)):
            return repr(list(value))
        return self.quote_string(str(value))

    def quote_string(self, value: str) -> str:
        if not value:
            return ""
        if any(c in self.QUOTE_CHARS for c in value):
            return f'"{escape_inline_string(value)}"'
        return value


class GenerateConfigAction(NonConfigAction):
    """Argparse Action that writes a parser's state as a config file.

    Declare an attribute on your Parser and let argclass derive the
    flag from its name::

        class CLI(argclass.Parser):
            generate_config = argclass.Argument(
                action=GenerateConfigAction,
                generator=INIConfigGenerator,
                metavar="FILE",
            )

    End users then run ``myapp --generate-config /etc/myapp.ini``
    (or ``-`` for stdout). The action walks the parser, renders the
    config via the supplied ``generator=`` (class or instance), writes
    to the destination, and exits with status 0.
    """

    def __init__(
        self,
        option_strings: list[str],
        dest: str,
        generator: type | ConfigGenerator,
        **kwargs: Any,
    ):
        kwargs.setdefault("nargs", 1)
        kwargs.setdefault("metavar", "FILE")
        kwargs.setdefault("default", argparse.SUPPRESS)
        if isinstance(generator, type):
            self.generator: ConfigGenerator = generator()
        else:
            self.generator = generator
        super().__init__(option_strings, dest, **kwargs)

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: Any,
        option_string: str | None = None,
    ) -> None:
        # Out-of-band back-reference avoids touching argparse_parser.
        argclass_parser = get_argclass_parser(parser)
        if argclass_parser is None:
            parser.error(
                "argclass parser back-reference missing — "
                "GenerateConfigAction requires the parser to be built "
                "through argclass.Parser.parse_args",
            )
        path = values[0] if isinstance(values, list) else values
        self.generator.dump(argclass_parser, path, namespace=namespace)
        parser.exit(0)
