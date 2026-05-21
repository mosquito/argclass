"""Config-file generators: render an argclass Parser to INI/JSON/TOML.

Symmetric counterpart to ``argclass/defaults.py`` (which READS configs).
Generators walk the parser tree (mirroring the recursion used by
``Parser._fill_group``), produce a nested dict, and render it.

Subclass ``ConfigGenerator`` and override ``render`` to add a new
format. The walking + Action wiring are shared.

Usage::

    import argclass
    from argclass.emit import GenerateConfigAction, INIConfigGenerator

    class CLI(argclass.Parser):
        host: str = "localhost"
        generate = argclass.Argument(
            "--generate-config",
            action=GenerateConfigAction,
            generator=INIConfigGenerator,
            metavar="FILE",
        )

Run ``myapp --generate-config /etc/myapp.ini`` to write the file, or
``myapp --generate-config -`` to print to stdout.

Security note: secret values are emitted as-is. Treat generated files
like any credential-bearing file.
"""

import argparse
import json
import os
import sys
from typing import Any, Dict, IO, List, Optional, Tuple, Union, cast

from .parser import get_argclass_parser
from .store import AbstractGroup, AbstractParser, TypedArgument
from .types import Actions


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
    # Actions enum members compare equal to their string values, so
    # one membership test covers both Actions.HELP / Actions.VERSION
    # and the raw "help" / "version" strings argparse accepts.
    if action in (Actions.VERSION, Actions.HELP):
        return False
    return True


def current_value(
    target: Any,
    name: str,
    argument: TypedArgument,
    *,
    namespace: Optional[argparse.Namespace] = None,
    dest: Optional[str] = None,
    env_var: Optional[str] = None,
) -> Any:
    """Read the current value for ``name`` on a Parser/Group instance.

    Priority (highest first):

    1. The instance ``__dict__`` (set when ``parse_args`` has
       completed).
    2. An argparse ``Namespace`` under ``dest`` — used when called
       mid-parse from :class:`GenerateConfigAction`, so CLI flags
       already processed by argparse land in the dump.
    3. ``os.environ[env_var]`` — covers env vars when the dump runs
       before argclass has applied them to ``__dict__``.
    4. The argument's declared default.

    Env values arrive as strings; we apply ``argument.type`` when it
    is callable, so the dump reflects the same type argclass would
    bind at parse time.
    """
    if name in target.__dict__:
        return target.__dict__[name]
    if namespace is not None and dest is not None and hasattr(namespace, dest):
        value = getattr(namespace, dest)
        if value is not None:
            return value
    if env_var:
        raw = os.environ.get(env_var)
        if raw is not None:
            type_func = argument.type
            if type_func is not None and not isinstance(raw, type_func):
                try:
                    return type_func(raw)
                except Exception:
                    return raw
            return raw
    return argument.default


HelpMap = Dict[Tuple[str, ...], str]
EnvMap = Dict[Tuple[str, ...], str]


def derive_env_var(
    auto_prefix: Optional[str],
    dest: str,
    argument: TypedArgument,
) -> Optional[str]:
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


class ConfigGenerator:
    """Walks an argclass Parser and renders its state to a config
    string. Subclass and override :meth:`render` for a new format.

    The walking + Action wiring live here; subclasses only need to
    implement ``render(data, help_map) -> str``.
    """

    #: File extension hint. Subclasses set this.
    extension: str = ""

    def build_dict(
        self,
        parser: AbstractParser,
        *,
        namespace: Optional[argparse.Namespace] = None,
    ) -> Dict[str, Any]:
        """Walk the parser, return a nested dict mirroring its tree.

        Top-level arguments become root keys; each group becomes a
        nested dict under its attribute name. Subparsers are skipped
        (they represent runtime branches, not config-time state).

        When ``namespace`` is provided, values are read from it (and
        from ``os.environ`` for args with env vars) — used by
        :class:`GenerateConfigAction` so the dump reflects CLI flags
        and env vars even when triggered mid-parse.
        """
        node = cast(Any, parser)
        auto_prefix = getattr(parser, "_auto_env_var_prefix", None)
        result: Dict[str, Any] = {}
        for name, argument in node.__arguments__.items():
            if not should_emit(argument):
                continue
            env = derive_env_var(auto_prefix, name, argument)
            result[name] = current_value(
                parser,
                name,
                argument,
                namespace=namespace,
                dest=name,
                env_var=env,
            )
        for group_name, group in node.__argument_groups__.items():
            seg = group_cli_segment(group, group_name)
            cli_path = (seg,) if seg else ()
            result[group_name] = self.build_group_dict(
                group,
                cli_path=cli_path,
                auto_prefix=auto_prefix,
                namespace=namespace,
            )
        return result

    def build_group_dict(
        self,
        group: AbstractGroup,
        *,
        cli_path: Tuple[str, ...] = (),
        auto_prefix: Optional[str] = None,
        namespace: Optional[argparse.Namespace] = None,
    ) -> Dict[str, Any]:
        node = cast(Any, group)
        cli_prefix = "_".join(cli_path)
        out: Dict[str, Any] = {}
        for name, argument in node.__arguments__.items():
            if not should_emit(argument):
                continue
            dest = f"{cli_prefix}_{name}" if cli_prefix else name
            env = derive_env_var(auto_prefix, dest, argument)
            out[name] = current_value(
                group,
                name,
                argument,
                namespace=namespace,
                dest=dest,
                env_var=env,
            )
        for child_name, child_group in node.__argument_groups__.items():
            seg = group_cli_segment(child_group, child_name)
            child_cli = cli_path + ((seg,) if seg else ())
            out[child_name] = self.build_group_dict(
                child_group,
                cli_path=child_cli,
                auto_prefix=auto_prefix,
                namespace=namespace,
            )
        return out

    def build_help_map(self, parser: AbstractParser) -> HelpMap:
        """Return ``{path: help_text}`` for every leaf argument with
        a help string. ``path`` is the tuple of attribute names from
        the parser root down to the leaf."""
        node = cast(Any, parser)
        out: HelpMap = {}
        for name, argument in node.__arguments__.items():
            if argument.help and should_emit(argument):
                out[(name,)] = argument.help
        for group_name, group in node.__argument_groups__.items():
            self.collect_group_help(group, (group_name,), out)
        return out

    def collect_group_help(
        self,
        group: AbstractGroup,
        prefix: Tuple[str, ...],
        out: HelpMap,
    ) -> None:
        node = cast(Any, group)
        for name, argument in node.__arguments__.items():
            if argument.help and should_emit(argument):
                out[prefix + (name,)] = argument.help
        for child_name, child in node.__argument_groups__.items():
            self.collect_group_help(child, prefix + (child_name,), out)

    def build_env_map(self, parser: AbstractParser) -> EnvMap:
        """Return ``{path: env_var_name}`` for every leaf argument
        that has an env var — either an explicit one on the argument
        or one derived from the parser's ``auto_env_var_prefix``.

        Arguments without a resolvable env var are omitted.
        """
        node = cast(Any, parser)
        auto_prefix = getattr(parser, "_auto_env_var_prefix", None)
        out: EnvMap = {}
        for name, argument in node.__arguments__.items():
            if not should_emit(argument):
                continue
            env = derive_env_var(auto_prefix, name, argument)
            if env:
                out[(name,)] = env
        for group_name, group in node.__argument_groups__.items():
            seg = group_cli_segment(group, group_name)
            cli_path = (seg,) if seg else ()
            self.collect_group_env(
                group,
                (group_name,),
                cli_path,
                auto_prefix,
                out,
            )
        return out

    def collect_group_env(
        self,
        group: AbstractGroup,
        attr_path: Tuple[str, ...],
        cli_path: Tuple[str, ...],
        auto_prefix: Optional[str],
        out: EnvMap,
    ) -> None:
        node = cast(Any, group)
        cli_prefix = "_".join(cli_path)
        for name, argument in node.__arguments__.items():
            if not should_emit(argument):
                continue
            dest = f"{cli_prefix}_{name}" if cli_prefix else name
            env = derive_env_var(auto_prefix, dest, argument)
            if env:
                out[attr_path + (name,)] = env
        for child_name, child in node.__argument_groups__.items():
            seg = group_cli_segment(child, child_name)
            child_cli = cli_path + ((seg,) if seg else ())
            self.collect_group_env(
                child,
                attr_path + (child_name,),
                child_cli,
                auto_prefix,
                out,
            )

    def render(
        self,
        data: Dict[str, Any],
        help_map: Optional[HelpMap] = None,
    ) -> str:
        """Render the dict to a config-format string. Override me."""
        raise NotImplementedError

    def dump_to_string(
        self,
        parser: AbstractParser,
        *,
        namespace: Optional[argparse.Namespace] = None,
    ) -> str:
        """Convenience: build_dict + render in one call."""
        return self.render(
            self.build_dict(parser, namespace=namespace),
            self.build_help_map(parser),
        )

    def dump(
        self,
        parser: AbstractParser,
        dest: Union[str, IO[str]],
        *,
        namespace: Optional[argparse.Namespace] = None,
    ) -> None:
        """Write the rendered config to ``dest``.

        ``dest`` may be a path, a file-like object, or the string
        ``"-"`` (writes to stdout).
        """
        content = self.dump_to_string(parser, namespace=namespace)
        if dest == "-":
            sys.stdout.write(content)
        elif isinstance(dest, str):
            with open(dest, "w") as fp:
                fp.write(content)
        else:
            dest.write(content)


def flatten_sections(
    path: Tuple[str, ...],
    value: Dict[str, Any],
    sections: Dict[str, Dict[str, Any]],
) -> None:
    """Recursively flatten nested-dict groups into dotted section names.

    Shared helper for INI and TOML emitters, which both use
    ``[parent.child]`` style section headers.
    """
    section_name = ".".join(path)
    scalars: Dict[str, Any] = {}
    for k, v in value.items():
        if isinstance(v, dict):
            flatten_sections(path + (k,), v, sections)
        else:
            scalars[k] = v
    sections[section_name] = scalars


class INIConfigGenerator(ConfigGenerator):
    """Render a parser to INI. Help text is emitted as ``; <text>``
    comments above each key. Nested groups use dotted section names
    (``[parent.child]``)."""

    extension = ".ini"

    def render(
        self,
        data: Dict[str, Any],
        help_map: Optional[HelpMap] = None,
    ) -> str:
        help_map = help_map or {}
        root: Dict[str, Any] = {}
        sections: Dict[str, Dict[str, Any]] = {}
        for key, value in data.items():
            if isinstance(value, dict):
                flatten_sections((key,), value, sections)
            else:
                root[key] = value

        lines: List[str] = []
        if root:
            lines.append("[DEFAULT]")
            for key, value in root.items():
                if value is None:
                    continue
                if text := help_map.get((key,)):
                    lines.append(f"; {text}")
                lines.append(f"{key} = {self.render_scalar(value)}")
            lines.append("")
        for section_name, items in sections.items():
            section_path = tuple(section_name.split("."))
            lines.append(f"[{section_name}]")
            for key, value in items.items():
                if value is None:
                    continue
                if text := help_map.get(section_path + (key,)):
                    lines.append(f"; {text}")
                lines.append(f"{key} = {self.render_scalar(value)}")
            lines.append("")
        return "\n".join(lines)

    @staticmethod
    def render_scalar(value: Any) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (list, tuple)):
            return repr(list(value))
        return str(value)


class JSONConfigGenerator(ConfigGenerator):
    """Render a parser to JSON. Comments are not supported by JSON,
    so help text is dropped. Nested groups become nested objects."""

    extension = ".json"

    def render(
        self,
        data: Dict[str, Any],
        help_map: Optional[HelpMap] = None,
    ) -> str:
        return (
            json.dumps(self.coerce_value(data), indent=2, sort_keys=False)
            + "\n"
        )

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
    """Render a parser to TOML. Help text is emitted as ``# <text>``
    comments above each key. Nested groups use dotted table headers
    (``[parent.child]``).

    Minimal hand-rolled emitter — covers str, int, float, bool, list,
    None. Other types are coerced via ``str()``.
    """

    extension = ".toml"

    def render(
        self,
        data: Dict[str, Any],
        help_map: Optional[HelpMap] = None,
    ) -> str:
        help_map = help_map or {}
        root: Dict[str, Any] = {}
        sections: Dict[str, Dict[str, Any]] = {}
        for key, value in data.items():
            if isinstance(value, dict):
                flatten_sections((key,), value, sections)
            else:
                root[key] = value

        lines: List[str] = []
        for key, value in root.items():
            if value is None:
                continue
            if text := help_map.get((key,)):
                lines.append(f"# {text}")
            lines.append(f"{key} = {self.render_value(value)}")
        if root and sections:
            lines.append("")
        for section_name, items in sections.items():
            section_path = tuple(section_name.split("."))
            lines.append(f"[{section_name}]")
            for key, value in items.items():
                if value is None:
                    continue
                if text := help_map.get(section_path + (key,)):
                    lines.append(f"# {text}")
                lines.append(f"{key} = {self.render_value(value)}")
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
        s = str(value)
        escaped = (
            s.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\n", "\\n")
            .replace("\r", "\\r")
            .replace("\t", "\\t")
        )
        return f'"{escaped}"'


class EnvConfigGenerator(ConfigGenerator):
    """Render a parser to a ``.env``-style listing.

    Emits one ``KEY=value`` line per argument, where ``KEY`` is the
    env var name argclass would read (explicit ``env_var=`` on the
    argument, or computed from the parser's ``auto_env_var_prefix``).
    Arguments without a resolvable env var are skipped — set
    ``auto_env_var_prefix=`` on the parser to get full coverage.

    Help text is emitted as ``# <text>`` comments above each key.
    Lists are serialised as Python literal syntax (e.g. ``['a','b']``)
    so argclass can ``ast.literal_eval`` them when reading back.

    Strings are quoted only when they contain whitespace or special
    characters — most ``.env`` parsers accept either form, but quoting
    when needed avoids accidental tokenisation.
    """

    extension = ".env"
    QUOTE_CHARS = frozenset(' \t\n"\\#=')

    def dump_to_string(
        self,
        parser: AbstractParser,
        *,
        namespace: Optional[argparse.Namespace] = None,
    ) -> str:
        data = self.build_dict(parser, namespace=namespace)
        help_map = self.build_help_map(parser)
        env_map = self.build_env_map(parser)
        lines: List[str] = []
        self.walk_env(data, (), env_map, help_map, lines)
        return "\n".join(lines) + ("\n" if lines else "")

    def render(
        self,
        data: Dict[str, Any],
        help_map: Optional[HelpMap] = None,
    ) -> str:
        # ``render`` cannot supply env names from the dict alone;
        # the .env emitter overrides ``dump_to_string`` to compose
        # data + help + env maps. Direct ``render`` calls would lose
        # env_var info, so we explicitly forbid that path.
        raise NotImplementedError(
            "EnvConfigGenerator.render needs env metadata; use "
            "dump_to_string(parser) or dump(parser, dest) instead.",
        )

    def walk_env(
        self,
        data: Dict[str, Any],
        path: Tuple[str, ...],
        env_map: EnvMap,
        help_map: HelpMap,
        lines: List[str],
    ) -> None:
        for key, value in data.items():
            full_path = path + (key,)
            if isinstance(value, dict):
                self.walk_env(value, full_path, env_map, help_map, lines)
                continue
            env_name = env_map.get(full_path)
            if env_name is None:
                continue
            if value is None:
                continue
            help_text = help_map.get(full_path)
            if help_text:
                lines.append(f"# {help_text}")
            lines.append(f"{env_name}={self.render_value(value)}")

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
            escaped = value.replace("\\", "\\\\").replace('"', '\\"')
            return f'"{escaped}"'
        return value


class GenerateConfigAction(NonConfigAction):
    """Argparse Action: ``--generate-config FILE``.

    ``FILE`` may be a filesystem path or ``-`` for stdout. Pass the
    generator class (or instance) via the ``generator=`` passthrough
    kwarg::

        argclass.Argument(
            "--generate-config",
            action=GenerateConfigAction,
            generator=INIConfigGenerator,
        )

    On invocation, walks the parser, renders the config, writes to the
    destination, and exits the process with status 0.
    """

    def __init__(
        self,
        option_strings: List[str],
        dest: str,
        generator: Union[type, ConfigGenerator],
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
        option_string: Optional[str] = None,
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
