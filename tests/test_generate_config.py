"""Tests for the config-file generator (argclass.emit).

Covers:
- Round-trip for INI/JSON/TOML across all argument shapes.
- Nested groups (2- and 3-level) emit correct dotted sections.
- list/tuple values survive the round-trip.
- GenerateConfigAction writes to file and to stdout ('-').
- Help text appears as comments in INI/TOML, dropped in JSON.
- NonConfigAction-based actions (and --help / --version) are
  skipped from dumps.
- Custom ConfigGenerator subclass works (user-defined format).
"""

import argparse
import io
import json
from enum import Enum
from pathlib import Path
from typing import Any, Callable, List, Optional, Type

import pytest

import argclass
from argclass.emit import (
    ConfigField,
    ConfigGenerator,
    EnvConfigGenerator,
    GenerateConfigAction,
    INIConfigGenerator,
    JSONConfigGenerator,
    NonConfigAction,
    TOMLConfigGenerator,
    current_value,
    derive_env_var,
    iter_config_fields,
    normalize_value,
    should_emit,
)
from argclass.utils import coerce_env_default


@pytest.fixture
def make_cli() -> Callable[[], Type[argclass.Parser]]:
    """Factory that builds a fresh parser class per test.

    Group instances live on the class; sharing them across tests
    leaks parsed state. Each test gets its own class graph.
    """

    def factory() -> Type[argclass.Parser]:
        class Credentials(argclass.Group):
            username: str = "admin"
            password: str = "secret"

        class Endpoint(argclass.Group):
            host: str = "localhost"
            port: int = 8080
            credentials: Credentials = Credentials()

        class CLI(argclass.Parser):
            debug: bool = False
            name: str = argclass.Argument(
                default="app",
                help="Application name",
            )
            endpoint: Endpoint = Endpoint()

        return CLI

    return factory


class TestINIRoundTrip:
    def test_basic_roundtrip(self, tmp_path: Path, make_cli):
        CLI = make_cli()
        out = tmp_path / "cfg.ini"
        INIConfigGenerator().dump(CLI(), str(out))

        loaded = CLI(config_files=[out])
        loaded.parse_args([])
        assert loaded.name == "app"
        assert loaded.endpoint.host == "localhost"
        assert loaded.endpoint.port == 8080
        assert loaded.endpoint.credentials.username == "admin"
        assert loaded.endpoint.credentials.password == "secret"

    def test_after_parse_snapshot(self, tmp_path: Path, make_cli):
        CLI = make_cli()
        p = CLI()
        p.parse_args(
            ["--debug", "--name=hello", "--endpoint-host=10.0.0.1"],
        )
        out = tmp_path / "cfg.ini"
        INIConfigGenerator().dump(p, str(out))

        loaded = CLI(config_files=[out])
        loaded.parse_args([])
        assert loaded.debug is True
        assert loaded.name == "hello"
        assert loaded.endpoint.host == "10.0.0.1"

    def test_help_text_in_comments(self, tmp_path: Path, make_cli):
        CLI = make_cli()
        out = tmp_path / "cfg.ini"
        INIConfigGenerator().dump(CLI(), str(out))
        text = out.read_text()
        assert "; Application name" in text


class TestJSONRoundTrip:
    def test_basic_roundtrip(self, tmp_path: Path, make_cli):
        CLI = make_cli()
        out = tmp_path / "cfg.json"
        JSONConfigGenerator().dump(CLI(), str(out))

        loaded = CLI(
            config_files=[out],
            config_parser_class=argclass.JSONDefaultsParser,
        )
        loaded.parse_args([])
        assert loaded.endpoint.host == "localhost"
        assert loaded.endpoint.credentials.username == "admin"

    def test_no_comments_in_json(self, tmp_path: Path, make_cli):
        CLI = make_cli()
        out = tmp_path / "cfg.json"
        JSONConfigGenerator().dump(CLI(), str(out))
        text = out.read_text()
        assert "Application name" not in text
        data = json.loads(text)
        assert data["name"] == "app"
        assert data["endpoint"]["credentials"]["username"] == "admin"


class TestTOMLRoundTrip:
    def test_basic_roundtrip(self, tmp_path: Path, make_cli):
        CLI = make_cli()
        out = tmp_path / "cfg.toml"
        TOMLConfigGenerator().dump(CLI(), str(out))

        loaded = CLI(
            config_files=[out],
            config_parser_class=argclass.TOMLDefaultsParser,
        )
        loaded.parse_args([])
        assert loaded.endpoint.host == "localhost"
        assert loaded.endpoint.credentials.username == "admin"

    def test_help_text_in_comments(self, tmp_path: Path, make_cli):
        CLI = make_cli()
        out = tmp_path / "cfg.toml"
        TOMLConfigGenerator().dump(CLI(), str(out))
        text = out.read_text()
        assert "# Application name" in text

    def test_string_escaping(self):
        gen = TOMLConfigGenerator()
        assert gen.render_value('hello "world"') == r'"hello \"world\""'
        assert gen.render_value("a\nb") == r'"a\nb"'
        assert gen.render_value("c\\d") == r'"c\\d"'

    def test_three_level_nesting(self, tmp_path: Path):
        class TLS(argclass.Group):
            cert: str = "/etc/cert"

        class Sec(argclass.Group):
            tls: TLS = TLS()

        class Conn(argclass.Group):
            sec: Sec = Sec()

        class App(argclass.Parser):
            conn: Conn = Conn()

        out = tmp_path / "cfg.toml"
        TOMLConfigGenerator().dump(App(), str(out))
        text = out.read_text()
        assert "[conn.sec.tls]" in text

        loaded = App(
            config_files=[out],
            config_parser_class=argclass.TOMLDefaultsParser,
        )
        loaded.parse_args([])
        assert loaded.conn.sec.tls.cert == "/etc/cert"


class TestListRoundTrip:
    def test_list_round_trips(self, tmp_path: Path):
        class App(argclass.Parser):
            tags: list[str] = argclass.Argument(
                nargs=argclass.Nargs.ZERO_OR_MORE,
                default=["one", "two"],
            )

        cases: List[Any] = [
            ("ini", INIConfigGenerator(), argclass.INIDefaultsParser),
            ("json", JSONConfigGenerator(), argclass.JSONDefaultsParser),
            ("toml", TOMLConfigGenerator(), argclass.TOMLDefaultsParser),
        ]
        for ext, gen, parser_cls in cases:
            out = tmp_path / f"cfg.{ext}"
            gen.dump(App(), str(out))
            loaded = App(
                config_files=[out],
                config_parser_class=parser_cls,
            )
            loaded.parse_args([])
            assert loaded.tags == ["one", "two"], f"failed for {ext}"


class TestAction:
    def make_cli(self, generator_cls: type) -> Type[argclass.Parser]:
        class App(argclass.Parser):
            host: str = "localhost"
            gen = argclass.Argument(
                "--generate-config",
                action=GenerateConfigAction,
                generator=generator_cls,
            )

        return App

    def test_action_writes_file_and_exits(self, tmp_path: Path):
        App = self.make_cli(INIConfigGenerator)
        out = tmp_path / "cfg.ini"
        with pytest.raises(SystemExit) as exc:
            App().parse_args(["--generate-config", str(out)])
        assert exc.value.code == 0
        assert out.exists()
        assert "host = localhost" in out.read_text()

    def test_action_stdout(self, capsys):
        App = self.make_cli(INIConfigGenerator)
        with pytest.raises(SystemExit) as exc:
            App().parse_args(["--generate-config", "-"])
        assert exc.value.code == 0
        captured = capsys.readouterr()
        assert "host = localhost" in captured.out

    def test_action_with_instance_generator(self, tmp_path: Path):
        """Passing a generator INSTANCE (not class) also works."""

        class App(argclass.Parser):
            host: str = "localhost"
            gen = argclass.Argument(
                "--generate-config",
                action=GenerateConfigAction,
                generator=JSONConfigGenerator(),
            )

        out = tmp_path / "cfg.json"
        with pytest.raises(SystemExit):
            App().parse_args(["--generate-config", str(out)])
        data = json.loads(out.read_text())
        assert data["host"] == "localhost"


class TestSkipNonConfig:
    def test_generate_config_arg_self_skipped(self, tmp_path: Path):
        App = TestAction().make_cli(INIConfigGenerator)
        out = tmp_path / "cfg.ini"
        with pytest.raises(SystemExit):
            App().parse_args(["--generate-config", str(out)])
        text = out.read_text()
        # The --generate-config flag itself must not appear in its
        # own output.
        assert "\ngen " not in text
        assert "generate" not in text.lower()

    def test_version_action_skipped(self, tmp_path: Path):
        class App(argclass.Parser):
            host: str = "localhost"
            ver = argclass.Argument(
                "-V",
                "--version",
                action=argclass.Actions.VERSION,
                version="1.0",
            )

        out = tmp_path / "cfg.ini"
        INIConfigGenerator().dump(App(), str(out))
        text = out.read_text()
        assert "ver" not in text
        assert "host" in text

    def test_version_and_generate_config_coexist(
        self,
        tmp_path: Path,
        capsys,
    ):
        """A parser carrying both ``--version`` and
        ``--generate-config`` must keep both flags working
        independently — neither should appear in the dump, and each
        must still print + exit when invoked."""

        class App(argclass.Parser):
            host: str = "localhost"
            port: int = 8080
            ver = argclass.Argument(
                "-V",
                "--version",
                action=argclass.Actions.VERSION,
                version="myapp/1.2.3",
            )
            generate = argclass.Argument(
                "--generate-config",
                action=GenerateConfigAction,
                generator=INIConfigGenerator,
            )

        # --version still prints + exits 0; namespace stays clean.
        with pytest.raises(SystemExit) as exc:
            App().parse_args(["--version"])
        assert exc.value.code == 0
        version_out = capsys.readouterr().out + capsys.readouterr().err
        assert "1.2.3" in version_out

        # --generate-config still writes the dump; neither version
        # nor generate-config itself leaks into it.
        out = tmp_path / "cfg.ini"
        with pytest.raises(SystemExit) as exc:
            App().parse_args(["--generate-config", str(out)])
        assert exc.value.code == 0
        text = out.read_text()
        assert "host = localhost" in text
        assert "port = 8080" in text
        assert "ver" not in text
        assert "generate" not in text

    def test_custom_non_config_action_skipped(self, tmp_path: Path):
        class MyAction(NonConfigAction):
            def __init__(self, option_strings, dest, **kw):
                kw.setdefault("nargs", 0)
                kw.setdefault("default", None)
                super().__init__(option_strings, dest, **kw)

            def __call__(self, p, ns, v, opt=None):
                p.exit(0)

        class App(argclass.Parser):
            host: str = "localhost"
            meta = argclass.Argument(action=MyAction)

        out = tmp_path / "cfg.ini"
        INIConfigGenerator().dump(App(), str(out))
        text = out.read_text()
        assert "meta" not in text

    def test_stateful_custom_action_included(self):
        """A custom Action that does NOT inherit NonConfigAction is
        treated as stateful and appears in the dump."""

        class Counter(argparse.Action):
            def __init__(self, option_strings, dest, **kw):
                kw.setdefault("nargs", 0)
                kw.setdefault("default", 0)
                super().__init__(option_strings, dest, **kw)

            def __call__(self, p, ns, v, opt=None):
                setattr(ns, self.dest, (getattr(ns, self.dest) or 0) + 1)

        class App(argclass.Parser):
            host: str = "localhost"
            counter = argclass.Argument("-v", action=Counter, default=0)

        text = INIConfigGenerator().dump_to_string(App())
        assert "counter" in text


class TestCustomGenerator:
    def test_user_subclass_renders_custom_format(
        self,
        tmp_path: Path,
        make_cli,
    ):
        """A user can subclass ConfigGenerator and override render to
        produce any text format."""

        class KeyValueGenerator(ConfigGenerator):
            extension = ".kv"

            def render(self, fields) -> str:
                lines: List[str] = []
                for field in fields:
                    if field.value is None:
                        continue
                    lines.append(
                        f"{'.'.join(field.attr_path)}={field.value}",
                    )
                return "\n".join(lines) + "\n"

        CLI = make_cli()
        out = tmp_path / "cfg.kv"
        KeyValueGenerator().dump(CLI(), str(out))
        text = out.read_text()
        assert "name=app" in text
        assert "endpoint.host=localhost" in text
        assert "endpoint.credentials.username=admin" in text


class TestHelpers:
    def test_should_emit_stateful(self):
        arg = argclass.TypedArgument(action=argclass.Actions.STORE)
        assert should_emit(arg) is True

    def test_should_emit_skips_version_enum(self):
        arg = argclass.TypedArgument(action=argclass.Actions.VERSION)
        assert should_emit(arg) is False

    def test_should_emit_skips_help_enum(self):
        arg = argclass.TypedArgument(action=argclass.Actions.HELP)
        assert should_emit(arg) is False

    def test_should_emit_skips_action_class_with_marker(self):
        arg = argclass.TypedArgument(action=NonConfigAction)
        assert should_emit(arg) is False

    def test_should_emit_includes_unmarked_action_class(self):
        class StatefulAction(argparse.Action):
            def __call__(self, *a, **k):
                pass

        arg = argclass.TypedArgument(action=StatefulAction)
        assert should_emit(arg) is True

    def test_should_emit_skips_help_string(self):
        arg = argclass.TypedArgument(action="help")
        assert should_emit(arg) is False

    def test_should_emit_skips_version_string(self):
        arg = argclass.TypedArgument(action="version")
        assert should_emit(arg) is False

    def test_current_value_falls_back_to_default(self, make_cli):
        CLI = make_cli()
        p = CLI()
        arg = p.__arguments__["name"]
        assert current_value(p, "name", arg) == "app"

    def test_current_value_reads_parsed(self, make_cli):
        CLI = make_cli()
        p = CLI()
        p.parse_args(["--name=hello"])
        arg = p.__arguments__["name"]
        assert current_value(p, "name", arg) == "hello"

    def test_current_value_reads_env_var_with_type_conversion(
        self,
        make_cli,
        monkeypatch,
    ):
        """Env values arrive as strings; ``current_value`` applies
        ``argument.type`` so the dump reflects the same value
        argclass would bind."""
        CLI = make_cli()
        p = CLI()
        monkeypatch.setenv("APP_ENDPOINT_PORT", "9999")
        arg = p.endpoint.__arguments__["port"]
        result = current_value(
            p.endpoint,
            "port",
            arg,
            env_var="APP_ENDPOINT_PORT",
        )
        assert result == 9999
        assert isinstance(result, int)

    def test_current_value_env_type_conversion_failure_returns_raw(
        self,
        monkeypatch,
    ):
        """If env value cannot be coerced, fall back to the raw
        string rather than crashing the dump."""
        monkeypatch.setenv("PORT_BAD", "not-a-number")
        arg = argclass.TypedArgument(type=int, default=8080)
        result = current_value(
            type("Stub", (), {"__dict__": {}})(),
            "port",
            arg,
            env_var="PORT_BAD",
        )
        assert result == "not-a-number"

    def test_current_value_env_callable_type_conversion(self, monkeypatch):
        """Callable ``type=`` values are converters, not isinstance
        targets, so env fallback must call them without crashing."""
        monkeypatch.setenv("APP_X", "5")
        arg = argclass.TypedArgument(
            type=lambda raw: int(raw) + 1,
            default=0,
        )
        result = current_value(
            type("Stub", (), {"__dict__": {}})(),
            "x",
            arg,
            env_var="APP_X",
        )
        assert result == 6

    def test_current_value_reads_namespace_when_provided(self):
        ns = argparse.Namespace(host="from-cli")
        arg = argclass.TypedArgument(default="localhost")
        result = current_value(
            type("Stub", (), {"__dict__": {}})(),
            "host",
            arg,
            namespace=ns,
            dest="host",
        )
        assert result == "from-cli"

    def test_current_value_namespace_none_falls_through(self):
        """A namespace dest with value None means argparse hasn't
        recorded that arg yet (e.g. SUPPRESS default) — fall back
        to env / default."""
        ns = argparse.Namespace(host=None)
        arg = argclass.TypedArgument(default="localhost")
        result = current_value(
            type("Stub", (), {"__dict__": {}})(),
            "host",
            arg,
            namespace=ns,
            dest="host",
        )
        assert result == "localhost"

    def test_current_value_namespace_already_correct_type(
        self,
        monkeypatch,
    ):
        """``isinstance(raw, type_func)`` guard avoids redundant
        coercion when env value comes back as the right type."""
        monkeypatch.setenv("FOO", "abc")
        arg = argclass.TypedArgument(type=str, default="x")
        result = current_value(
            type("Stub", (), {"__dict__": {}})(),
            "foo",
            arg,
            env_var="FOO",
        )
        assert result == "abc"


class TestSourcesInfluenceDump:
    """The dumped config must reflect whichever source argclass
    resolved the value from: defaults, config files, env vars, or
    CLI. The generator reads the parser's CURRENT state, so this is
    really a property of the value-resolution pipeline — these tests
    pin it down end-to-end."""

    def test_cli_value_appears_in_dump(self, tmp_path: Path, make_cli):
        CLI = make_cli()
        p = CLI()
        p.parse_args(
            [
                "--name=from-cli",
                "--endpoint-host=cli-host",
                "--endpoint-credentials-username=cli-user",
            ],
        )
        out = tmp_path / "cfg.ini"
        INIConfigGenerator().dump(p, str(out))
        text = out.read_text()
        assert "name = from-cli" in text
        assert "host = cli-host" in text
        assert "username = cli-user" in text

    def test_env_value_appears_in_dump(
        self,
        tmp_path: Path,
        make_cli,
        monkeypatch,
    ):
        CLI = make_cli()
        monkeypatch.setenv("APP_NAME", "from-env")
        monkeypatch.setenv("APP_ENDPOINT_HOST", "env-host")
        monkeypatch.setenv(
            "APP_ENDPOINT_CREDENTIALS_USERNAME",
            "env-user",
        )
        p = CLI(auto_env_var_prefix="APP_")
        p.parse_args([])
        out = tmp_path / "cfg.toml"
        TOMLConfigGenerator().dump(p, str(out))
        text = out.read_text()
        assert 'name = "from-env"' in text
        assert 'host = "env-host"' in text
        assert 'username = "env-user"' in text

    def test_cli_overrides_env_in_dump(
        self,
        tmp_path: Path,
        make_cli,
        monkeypatch,
    ):
        CLI = make_cli()
        monkeypatch.setenv("APP_NAME", "from-env")
        p = CLI(auto_env_var_prefix="APP_")
        p.parse_args(["--name=from-cli"])
        text = INIConfigGenerator().dump_to_string(p)
        assert "name = from-cli" in text
        assert "from-env" not in text

    def test_config_file_value_appears_in_dump(
        self,
        tmp_path: Path,
        make_cli,
    ):
        CLI = make_cli()
        initial = tmp_path / "initial.ini"
        initial.write_text(
            "[DEFAULT]\nname = from-config\n[endpoint]\nhost = config-host\n",
        )
        p = CLI(config_files=[initial])
        p.parse_args([])
        text = INIConfigGenerator().dump_to_string(p)
        assert "name = from-config" in text
        assert "host = config-host" in text

    def test_full_roundtrip_with_cli_overrides(
        self,
        tmp_path: Path,
        make_cli,
    ):
        """Generate a config from a parser that received CLI args,
        then load that config into a fresh parser — the CLI-set
        values must be preserved."""
        CLI = make_cli()
        p = CLI()
        p.parse_args(
            [
                "--debug",
                "--endpoint-port=9999",
                "--endpoint-credentials-password=hunter2",
            ],
        )
        out = tmp_path / "cfg.json"
        JSONConfigGenerator().dump(p, str(out))

        fresh_cls = make_cli()
        loaded = fresh_cls(
            config_files=[out],
            config_parser_class=argclass.JSONDefaultsParser,
        )
        loaded.parse_args([])
        assert loaded.debug is True
        assert loaded.endpoint.port == 9999
        assert loaded.endpoint.credentials.password == "hunter2"


class TestGroupReuseAndNesting:
    def test_two_distinct_group_instances_dump_independently(
        self,
        tmp_path: Path,
    ):
        """Two attributes of the same Group class each carry their
        own state. The dump must reflect both, in their own
        sections."""

        class Conn(argclass.Group):
            host: str = "localhost"
            port: int = 8080

        class App(argclass.Parser):
            primary: Conn = Conn()
            secondary: Conn = Conn()

        p = App()
        p.parse_args(
            [
                "--primary-host=primary.example.com",
                "--secondary-host=secondary.example.com",
                "--secondary-port=9090",
            ],
        )
        out = tmp_path / "cfg.ini"
        INIConfigGenerator().dump(p, str(out))
        text = out.read_text()
        assert "[primary]" in text
        assert "[secondary]" in text
        assert "host = primary.example.com" in text
        assert "host = secondary.example.com" in text
        assert "port = 9090" in text

        loaded = App(config_files=[out])
        loaded.parse_args([])
        assert loaded.primary.host == "primary.example.com"
        assert loaded.primary.port == 8080
        assert loaded.secondary.host == "secondary.example.com"
        assert loaded.secondary.port == 9090

    def test_nested_groups_three_levels_with_cli_overrides(
        self,
        tmp_path: Path,
    ):
        """End-to-end: 3-level nesting, CLI overrides at every level,
        round-trip through INI/JSON/TOML preserves everything."""

        class TLS(argclass.Group):
            cert: str = "/etc/cert"
            key: str = "/etc/key"

        class Sec(argclass.Group):
            tls: TLS = TLS()
            verify: bool = False

        class Conn(argclass.Group):
            host: str = "localhost"
            sec: Sec = Sec()

        class App(argclass.Parser):
            conn: Conn = Conn()

        cases: List[Any] = [
            ("ini", INIConfigGenerator, argclass.INIDefaultsParser),
            ("json", JSONConfigGenerator, argclass.JSONDefaultsParser),
            ("toml", TOMLConfigGenerator, argclass.TOMLDefaultsParser),
        ]
        for ext, gen_cls, parser_cls in cases:
            p = App()
            p.parse_args(
                [
                    "--conn-host=db.example.com",
                    "--conn-sec-verify",
                    "--conn-sec-tls-cert=/new/cert",
                ],
            )
            out = tmp_path / f"cfg.{ext}"
            gen_cls().dump(p, str(out))

            loaded = App(
                config_files=[out],
                config_parser_class=parser_cls,
            )
            loaded.parse_args([])
            assert loaded.conn.host == "db.example.com", ext
            assert loaded.conn.sec.verify is True, ext
            assert loaded.conn.sec.tls.cert == "/new/cert", ext
            assert loaded.conn.sec.tls.key == "/etc/key", ext


class TestEdgeCases:
    def test_base_generator_render_not_implemented(self):
        with pytest.raises(NotImplementedError):
            ConfigGenerator().render(())

    def test_ini_skips_none_in_root_and_sections(self):
        """INI cannot natively express None; the renderer drops
        such keys entirely so the reloaded parser falls back to its
        own default instead of seeing an empty string."""

        class Inner(argclass.Group):
            ghost: Optional[str] = None
            present: str = "yes"

        class App(argclass.Parser):
            ghost: Optional[str] = None
            present: str = "yes"
            inner: Inner = Inner()

        text = INIConfigGenerator().dump_to_string(App())
        assert "ghost" not in text
        assert "present = yes" in text

    def test_ini_default_section_does_not_leak_into_group_none_value(
        self,
        tmp_path: Path,
    ):
        """Round-trip with an INI [DEFAULT] / [inner] name collision.

        The generated file omits ``inner.host`` because it is ``None``.
        configparser would normally cascade the top-level ``host``
        from [DEFAULT] into [inner], but
        :class:`argclass.INIDefaultsParser` strips DEFAULT cascade so
        each group's own None default survives.
        """

        class Inner(argclass.Group):
            host: Optional[str] = None

        class App(argclass.Parser):
            host: str = "root"
            inner: Inner = Inner()

        out = tmp_path / "cfg.ini"
        INIConfigGenerator().dump(App(), out)

        loaded = App(config_files=[out])
        loaded.parse_args([])

        assert loaded.host == "root"
        assert loaded.inner.host is None

    def test_ini_bool_value(self):
        gen = INIConfigGenerator()
        assert gen.render_scalar(True) == "true"
        assert gen.render_scalar(False) == "false"

    def test_toml_skips_none_root_and_section(self):
        class Inner(argclass.Group):
            ghost: Optional[str] = None

        class App(argclass.Parser):
            ghost: Optional[str] = None
            host: str = "localhost"
            inner: Inner = Inner()

        text = TOMLConfigGenerator().dump_to_string(App())
        assert "ghost" not in text
        assert 'host = "localhost"' in text

    def test_json_coerces_non_native_value(self):
        from datetime import date

        gen = JSONConfigGenerator()
        result = gen.coerce_value(date(2026, 1, 1))
        assert result == "2026-01-01"

    def test_action_back_ref_missing_raises(self):
        """When GenerateConfigAction is attached to a bare argparse
        ArgumentParser (no argclass back-ref), invocation raises."""
        ap = argparse.ArgumentParser()
        ap.add_argument(
            "--dump",
            action=GenerateConfigAction,
            generator=INIConfigGenerator,
        )
        with pytest.raises(SystemExit):
            ap.parse_args(["--dump", "-"])

    def test_help_in_ini_nested_section(self, tmp_path: Path):
        """INI help comments must also be emitted inside dotted
        sections, not only [DEFAULT]."""

        class Inner(argclass.Group):
            value: str = argclass.Argument(
                default="x",
                help="Inner help text",
            )

        class App(argclass.Parser):
            inner: Inner = Inner()

        text = INIConfigGenerator().dump_to_string(App())
        assert "; Inner help text" in text
        assert "[inner]" in text

    def test_help_in_toml_nested_section(self):
        class Inner(argclass.Group):
            value: str = argclass.Argument(
                default="x",
                help="Inner help text",
            )

        class App(argclass.Parser):
            inner: Inner = Inner()

        text = TOMLConfigGenerator().dump_to_string(App())
        assert "# Inner help text" in text
        assert "[inner]" in text

    def test_non_config_arg_skipped_in_nested_group(self):
        """A NonConfigAction-marked argument inside a nested group
        is skipped from the dump."""

        class MyAction(NonConfigAction):
            def __init__(self, option_strings, dest, **kw):
                kw.setdefault("nargs", 0)
                kw.setdefault("default", None)
                super().__init__(option_strings, dest, **kw)

            def __call__(self, p, ns, v, opt=None):
                p.exit(0)

        class Inner(argclass.Group):
            host: str = "localhost"
            meta = argclass.Argument(action=MyAction)

        class App(argclass.Parser):
            inner: Inner = Inner()

        text = INIConfigGenerator().dump_to_string(App())
        assert "host = localhost" in text
        assert "meta" not in text


class TestEnvConfigGenerator:
    def test_auto_prefix_emits_all(self, make_cli):
        CLI = make_cli()
        p = CLI(auto_env_var_prefix="APP_")
        text = EnvConfigGenerator().dump_to_string(p)
        assert "APP_NAME=app" in text
        assert "APP_DEBUG=false" in text
        assert "APP_ENDPOINT_HOST=localhost" in text
        assert "APP_ENDPOINT_PORT=8080" in text
        assert "APP_ENDPOINT_CREDENTIALS_USERNAME=admin" in text
        assert "APP_ENDPOINT_CREDENTIALS_PASSWORD=secret" in text

    def test_no_prefix_emits_only_explicit_env_vars(self, make_cli):
        """Without auto_env_var_prefix, only args carrying an
        explicit env_var= survive."""

        class App(argclass.Parser):
            host: str = argclass.Argument(default="localhost")
            api_key: str = argclass.Argument(
                default="xxx",
                env_var="MY_KEY",
            )

        text = EnvConfigGenerator().dump_to_string(App())
        assert "MY_KEY=xxx" in text
        assert "host" not in text.lower()

    def test_help_text_in_comments(self, make_cli):
        CLI = make_cli()
        p = CLI(auto_env_var_prefix="APP_")
        text = EnvConfigGenerator().dump_to_string(p)
        assert "# Application name" in text

    def test_cli_value_reflects_in_env_dump(self, make_cli):
        CLI = make_cli()
        p = CLI(auto_env_var_prefix="APP_")
        p.parse_args(["--name=from-cli", "--endpoint-host=cli-host"])
        text = EnvConfigGenerator().dump_to_string(p)
        assert "APP_NAME=from-cli" in text
        assert "APP_ENDPOINT_HOST=cli-host" in text

    def test_env_value_reflects_in_env_dump(self, make_cli, monkeypatch):
        CLI = make_cli()
        monkeypatch.setenv("APP_NAME", "from-env")
        p = CLI(auto_env_var_prefix="APP_")
        p.parse_args([])
        text = EnvConfigGenerator().dump_to_string(p)
        assert "APP_NAME=from-env" in text

    def test_list_uses_python_literal(self):
        class App(argclass.Parser):
            tags: list[str] = argclass.Argument(
                nargs=argclass.Nargs.ZERO_OR_MORE,
                default=["one", "two"],
            )

        p = App(auto_env_var_prefix="APP_")
        text = EnvConfigGenerator().dump_to_string(p)
        # Must be ast.literal_eval-able so env reading round-trips.
        assert "APP_TAGS=['one', 'two']" in text

    def test_string_with_spaces_is_quoted(self):
        gen = EnvConfigGenerator()
        assert gen.render_value("simple") == "simple"
        assert gen.render_value("has spaces") == '"has spaces"'
        assert gen.render_value('has "quote"') == r'"has \"quote\""'

    def test_render_empty_fields_returns_empty(self):
        """``render([])`` is a valid call now — every subclass
        honours the same ``Iterable[ConfigField]`` contract."""
        assert EnvConfigGenerator().render([]) == ""

    def test_action_wires_env_generator(self, tmp_path: Path):
        class App(argclass.Parser):
            host: str = "localhost"
            gen = argclass.Argument(
                "--generate-env",
                action=GenerateConfigAction,
                generator=EnvConfigGenerator,
            )

        out = tmp_path / ".env"
        with pytest.raises(SystemExit):
            App(auto_env_var_prefix="APP_").parse_args(
                ["--generate-env", str(out)],
            )
        text = out.read_text()
        assert "APP_HOST=localhost" in text

    def test_env_round_trip(self, make_cli, monkeypatch):
        """Dump env-style listing, then set those env vars and parse
        — values come back equal."""
        CLI = make_cli()
        p = CLI(auto_env_var_prefix="APP_")
        p.parse_args(
            [
                "--name=hello",
                "--endpoint-host=prod.example.com",
                "--endpoint-credentials-username=root",
            ],
        )
        text = EnvConfigGenerator().dump_to_string(p)

        # Parse the dump back into env vars.
        for line in text.splitlines():
            if not line or line.startswith("#"):
                continue
            key, _, value = line.partition("=")
            monkeypatch.setenv(key, value)

        loaded = CLI(auto_env_var_prefix="APP_")
        loaded.parse_args([])
        assert loaded.name == "hello"
        assert loaded.endpoint.host == "prod.example.com"
        assert loaded.endpoint.credentials.username == "root"


class TestEnvIntrospection:
    def test_derive_env_var_explicit_wins(self):
        arg = argclass.TypedArgument(env_var="EXPLICIT")
        assert derive_env_var("APP_", "anything", arg) == "EXPLICIT"

    def test_derive_env_var_uses_prefix(self):
        arg = argclass.TypedArgument()
        assert derive_env_var("APP_", "host", arg) == "APP_HOST"

    def test_derive_env_var_returns_none_without_prefix(self):
        arg = argclass.TypedArgument()
        assert derive_env_var(None, "host", arg) is None

    def env_map_from_fields(self, parser: argclass.Parser) -> dict:
        """Build {attr_path: env_var} by walking ConfigField stream
        — exercises the new single-walk introspection contract."""
        return {
            f.attr_path: f.env_var
            for f in iter_config_fields(parser)
            if f.env_var
        }

    def test_iter_fields_with_prefix_override(self):
        """Group(prefix=...) overrides the env-var path segment."""

        class Inner(argclass.Group):
            value: str = "x"

        class App(argclass.Parser):
            inner: Inner = Inner(prefix="i")

        p = App(auto_env_var_prefix="APP_")
        env_map = self.env_map_from_fields(p)
        assert env_map[("inner", "value")] == "APP_I_VALUE"

    def test_iter_fields_with_empty_prefix(self):
        class Inner(argclass.Group):
            value: str = "x"

        class App(argclass.Parser):
            inner: Inner = Inner(prefix="")

        p = App(auto_env_var_prefix="APP_")
        env_map = self.env_map_from_fields(p)
        assert env_map[("inner", "value")] == "APP_VALUE"

    def test_nested_group_skips_non_config_action(self):
        """NonConfigAction marker on an arg inside a nested group
        keeps it out of the field stream too."""

        class MetaAction(NonConfigAction):
            def __init__(self, option_strings, dest, **kw):
                kw.setdefault("nargs", 0)
                kw.setdefault("default", None)
                super().__init__(option_strings, dest, **kw)

            def __call__(self, p, ns, v, opt=None):
                p.exit(0)

        class Inner(argclass.Group):
            host: str = "localhost"
            meta = argclass.Argument(action=MetaAction)

        class App(argclass.Parser):
            inner: Inner = Inner()

        paths = {
            f.attr_path
            for f in iter_config_fields(
                App(auto_env_var_prefix="APP_"),
            )
        }
        assert ("inner", "host") in paths
        assert ("inner", "meta") not in paths

    def test_nested_group_skips_arg_without_resolvable_env(self):
        """No auto_env_var_prefix AND no explicit env_var on an arg
        inside a group — that arg has no env_var in the field stream."""

        class Inner(argclass.Group):
            quiet: str = "yes"
            shouted: str = argclass.Argument(
                default="x",
                env_var="SHOUTED",
            )

        class App(argclass.Parser):
            inner: Inner = Inner()

        env_map = self.env_map_from_fields(App())
        assert env_map.get(("inner", "shouted")) == "SHOUTED"
        assert ("inner", "quiet") not in env_map

    def test_none_value_skipped_in_env_dump(self):
        """A None value (e.g. Optional with no resolved value) is
        skipped from the env dump even when an env var is configured.
        """

        class App(argclass.Parser):
            maybe: Optional[str] = argclass.Argument(
                default=None,
                env_var="MAYBE",
            )

        text = EnvConfigGenerator().dump_to_string(App())
        assert "MAYBE" not in text

    def test_quote_empty_string(self):
        assert EnvConfigGenerator().quote_string("") == ""


class TestNormalizeValue:
    """``normalize_value`` is the single round-trip-fix point used by
    every generator — Enum/set/frozenset/Path all flow through it."""

    def test_enum_member_returns_name(self):
        from enum import Enum

        class Color(Enum):
            RED = "red"
            GREEN = "green"

        assert normalize_value(Color.RED) == "RED"

    def test_int_enum_returns_name(self):
        from enum import IntEnum

        class Level(IntEnum):
            INFO = 10
            DEBUG = 20

        assert normalize_value(Level.DEBUG) == "DEBUG"

    def test_set_returns_sorted_list(self):
        assert normalize_value({3, 1, 2}) == [1, 2, 3]

    def test_frozenset_returns_sorted_list(self):
        assert normalize_value(frozenset({"b", "a"})) == ["a", "b"]

    def test_set_of_unorderable_returns_list(self):
        """Mixed types fall back to unordered ``list``."""

        class Opaque:
            pass

        items = {Opaque(), Opaque()}
        out = normalize_value(items)
        assert isinstance(out, list)
        assert len(out) == 2

    def test_path_returns_string(self):
        from pathlib import PurePosixPath

        assert normalize_value(PurePosixPath("/etc/app")) == "/etc/app"

    def test_native_values_pass_through(self):
        for value in ("s", 1, 1.5, True, False, None, [1, 2], (3, 4)):
            assert normalize_value(value) == value


class TestEnumAndCollectionRoundTrip:
    """Round-trip Enum / set / frozenset through each format. These
    used to silently break: ``Color.RED`` would be written as
    ``"Color.RED"`` and ``frozenset({1, 2})`` as a non-sequence
    string."""

    @staticmethod
    def make_parser() -> type:
        from enum import Enum

        class Color(Enum):
            RED = "red"
            GREEN = "green"
            BLUE = "blue"

        class App(argclass.Parser):
            color: Color = argclass.EnumArgument(Color, default="GREEN")
            unique: frozenset = argclass.Argument(  # type: ignore[type-arg]
                type=int,
                nargs=argclass.Nargs.ONE_OR_MORE,
                converter=frozenset,
                default=frozenset({1, 2, 3}),
            )

        App._Color = Color  # type: ignore[attr-defined]
        return App

    def test_enum_in_ini_roundtrip(self, tmp_path: Path):
        App = self.make_parser()
        out = tmp_path / "cfg.ini"
        INIConfigGenerator().dump(App(), str(out))
        loaded = App(config_files=[out])
        loaded.parse_args([])
        assert loaded.color.name == "GREEN"

    def test_enum_in_toml_roundtrip(self, tmp_path: Path):
        App = self.make_parser()
        out = tmp_path / "cfg.toml"
        TOMLConfigGenerator().dump(App(), str(out))
        loaded = App(
            config_files=[out],
            config_parser_class=argclass.TOMLDefaultsParser,
        )
        loaded.parse_args([])
        assert loaded.color.name == "GREEN"

    def test_enum_in_json_roundtrip(self, tmp_path: Path):
        App = self.make_parser()
        out = tmp_path / "cfg.json"
        JSONConfigGenerator().dump(App(), str(out))
        loaded = App(
            config_files=[out],
            config_parser_class=argclass.JSONDefaultsParser,
        )
        loaded.parse_args([])
        assert loaded.color.name == "GREEN"

    def test_frozenset_dumps_as_sorted_list(self):
        App = self.make_parser()
        text = TOMLConfigGenerator().dump_to_string(App())
        # Sorted list, not "frozenset({...})".
        assert "unique = [1, 2, 3]" in text


class TestGeneratorNormalisesIterablesToLists:
    """The generators must convert set/frozenset/tuple to plain
    ``list`` in every format. Otherwise the output is either invalid
    syntax (TOML cannot represent ``frozenset(...)``) or unreadable
    on round-trip (INI ``literal_eval`` rejects ``frozenset({1, 2})``,
    JSON outright refuses sets).
    """

    @staticmethod
    def make_parser_with_collections(default: Any) -> Type[argclass.Parser]:
        class App(argclass.Parser):
            tags: Any = argclass.Argument(
                type=str,
                nargs=argclass.Nargs.ONE_OR_MORE,
                converter=type(default),
                default=default,
            )

        return App

    def test_set_dumps_as_list_in_all_formats(self, tmp_path: Path):
        App = self.make_parser_with_collections({"c", "a", "b"})
        for gen_cls in (
            INIConfigGenerator,
            JSONConfigGenerator,
            TOMLConfigGenerator,
        ):
            text = gen_cls().dump_to_string(App())
            assert "set(" not in text
            assert "frozenset" not in text

    def test_frozenset_dumps_as_list_in_all_formats(self, tmp_path: Path):
        App = self.make_parser_with_collections(frozenset({3, 1, 2}))
        for gen_cls in (
            INIConfigGenerator,
            JSONConfigGenerator,
            TOMLConfigGenerator,
        ):
            text = gen_cls().dump_to_string(App())
            assert "frozenset" not in text

    def test_tuple_dumps_as_list_in_all_formats(self, tmp_path: Path):
        """Tuples don't need normalisation per se — every emitter
        already treats ``(list, tuple)`` uniformly — but pin the
        observable behaviour so it can't regress."""

        class App(argclass.Parser):
            tags: tuple = argclass.Argument(  # type: ignore[type-arg]
                type=str,
                nargs=argclass.Nargs.ONE_OR_MORE,
                converter=tuple,
                default=("alpha", "beta"),
            )

        # JSON: list literal.
        text = JSONConfigGenerator().dump_to_string(App())
        assert '[\n    "alpha",\n    "beta"\n  ]' in text
        # TOML: square-bracket array.
        text = TOMLConfigGenerator().dump_to_string(App())
        assert 'tags = ["alpha", "beta"]' in text
        # INI: ast.literal_eval-able list.
        text = INIConfigGenerator().dump_to_string(App())
        assert "tags = ['alpha', 'beta']" in text


class TestCrossFormatIterableRoundTrip:
    """Per-format dump-and-reload for set / frozenset / tuple. Each
    case loads through the parser class itself, so the dumped form
    must be syntactically and semantically right for every format.
    """

    @staticmethod
    def reload(
        parser_cls: Type[argclass.Parser],
        gen_cls: type,
        defaults_cls: type,
        tmp_path: Path,
        ext: str,
    ) -> argclass.Parser:
        out = tmp_path / f"cfg.{ext}"
        gen_cls().dump(parser_cls(), str(out))
        loaded = parser_cls(
            config_files=[out],
            config_parser_class=defaults_cls,
        )
        loaded.parse_args([])
        return loaded

    @pytest.mark.parametrize(
        "gen_cls,defaults_cls,ext",
        [
            (INIConfigGenerator, argclass.INIDefaultsParser, "ini"),
            (JSONConfigGenerator, argclass.JSONDefaultsParser, "json"),
            (TOMLConfigGenerator, argclass.TOMLDefaultsParser, "toml"),
        ],
    )
    def test_set_round_trip(
        self,
        tmp_path: Path,
        gen_cls: type,
        defaults_cls: type,
        ext: str,
    ) -> None:
        class App(argclass.Parser):
            tags: Any = argclass.Argument(
                type=str,
                nargs=argclass.Nargs.ONE_OR_MORE,
                converter=set,
                default={"alpha", "beta", "gamma"},
            )

        loaded = self.reload(App, gen_cls, defaults_cls, tmp_path, ext)
        assert loaded.tags == {"alpha", "beta", "gamma"}

    @pytest.mark.parametrize(
        "gen_cls,defaults_cls,ext",
        [
            (INIConfigGenerator, argclass.INIDefaultsParser, "ini"),
            (JSONConfigGenerator, argclass.JSONDefaultsParser, "json"),
            (TOMLConfigGenerator, argclass.TOMLDefaultsParser, "toml"),
        ],
    )
    def test_frozenset_round_trip(
        self,
        tmp_path: Path,
        gen_cls: type,
        defaults_cls: type,
        ext: str,
    ) -> None:
        class App(argclass.Parser):
            tags: Any = argclass.Argument(
                type=int,
                nargs=argclass.Nargs.ONE_OR_MORE,
                converter=frozenset,
                default=frozenset({1, 2, 3}),
            )

        loaded = self.reload(App, gen_cls, defaults_cls, tmp_path, ext)
        assert loaded.tags == frozenset({1, 2, 3})

    @pytest.mark.parametrize(
        "gen_cls,defaults_cls,ext",
        [
            (INIConfigGenerator, argclass.INIDefaultsParser, "ini"),
            (JSONConfigGenerator, argclass.JSONDefaultsParser, "json"),
            (TOMLConfigGenerator, argclass.TOMLDefaultsParser, "toml"),
        ],
    )
    def test_enum_round_trip(
        self,
        tmp_path: Path,
        gen_cls: type,
        defaults_cls: type,
        ext: str,
    ) -> None:
        class Color(Enum):
            RED = "red"
            GREEN = "green"
            BLUE = "blue"

        class App(argclass.Parser):
            color: Color = argclass.EnumArgument(Color, default="GREEN")

        loaded = self.reload(App, gen_cls, defaults_cls, tmp_path, ext)
        assert loaded.color is Color.GREEN

    @pytest.mark.parametrize(
        "gen_cls,defaults_cls,ext",
        [
            (INIConfigGenerator, argclass.INIDefaultsParser, "ini"),
            (JSONConfigGenerator, argclass.JSONDefaultsParser, "json"),
            (TOMLConfigGenerator, argclass.TOMLDefaultsParser, "toml"),
        ],
    )
    def test_enum_lowercase_round_trip(
        self,
        tmp_path: Path,
        gen_cls: type,
        defaults_cls: type,
        ext: str,
    ) -> None:
        """``EnumArgument(lowercase=True)`` accepts both cases on
        read; the dump emits canonical ``.name`` and the lenient
        converter rehydrates it."""

        class Color(Enum):
            RED = "red"
            BLUE = "blue"

        class App(argclass.Parser):
            color: Color = argclass.EnumArgument(
                Color,
                default="BLUE",
                lowercase=True,
            )

        loaded = self.reload(App, gen_cls, defaults_cls, tmp_path, ext)
        assert loaded.color is Color.BLUE

    @pytest.mark.parametrize(
        "gen_cls,defaults_cls,ext",
        [
            (INIConfigGenerator, argclass.INIDefaultsParser, "ini"),
            (JSONConfigGenerator, argclass.JSONDefaultsParser, "json"),
            (TOMLConfigGenerator, argclass.TOMLDefaultsParser, "toml"),
        ],
    )
    def test_int_enum_round_trip(
        self,
        tmp_path: Path,
        gen_cls: type,
        defaults_cls: type,
        ext: str,
    ) -> None:
        from enum import IntEnum

        class Priority(IntEnum):
            LOW = 1
            MEDIUM = 5
            HIGH = 10

        class App(argclass.Parser):
            level: Priority = argclass.EnumArgument(
                Priority,
                default="MEDIUM",
            )

        loaded = self.reload(App, gen_cls, defaults_cls, tmp_path, ext)
        assert loaded.level is Priority.MEDIUM


class TestFieldsToNestedDict:
    """Direct tests on the field→dict helper used by JSON."""

    @staticmethod
    def make_field(attr_path: tuple, value: object) -> ConfigField:
        return ConfigField(
            attr_path=attr_path,
            cli_path=attr_path,
            dest="_".join(attr_path),
            argument=argclass.TypedArgument(),
            target=None,
            value=value,
            env_var=None,
            help=None,
        )

    def test_skip_none_drops_keys(self):
        from argclass.emit import fields_to_nested_dict

        fields = [
            self.make_field(("a",), 1),
            self.make_field(("b",), None),
            self.make_field(("g", "x"), None),
            self.make_field(("g", "y"), 2),
        ]
        out = fields_to_nested_dict(fields, skip_none=True)
        assert out == {"a": 1, "g": {"y": 2}}

    def test_intermediate_non_dict_is_overwritten(self):
        """Edge case: a field collides with a section name. The
        helper recovers by replacing the leaf with a dict."""
        from argclass.emit import fields_to_nested_dict

        fields = [
            self.make_field(("g",), "scalar"),
            self.make_field(("g", "child"), 1),
        ]
        out = fields_to_nested_dict(fields)
        assert out == {"g": {"child": 1}}


class TestCoerceEnvValue:
    """``coerce_env_default`` mirrors argparse's env coercions so the
    dump-mid-parse path sees parsed-style values instead of raw
    strings. Each branch covered once."""

    def test_list_via_literal_eval(self):
        arg = argclass.TypedArgument(
            type=int,
            nargs=argclass.Nargs.ONE_OR_MORE,
        )
        assert coerce_env_default("[1, 2, 3]", arg) == [1, 2, 3]

    def test_list_with_bad_literal_returns_raw(self):
        arg = argclass.TypedArgument(
            type=int,
            nargs=argclass.Nargs.ONE_OR_MORE,
        )
        # Not parseable as a literal — return the raw string.
        assert coerce_env_default("not-a-list", arg) == "not-a-list"

    def test_bool_store_true_action(self):
        arg = argclass.TypedArgument(action=argclass.Actions.STORE_TRUE)
        assert coerce_env_default("true", arg) is True
        assert coerce_env_default("0", arg) is False

    def test_bool_store_false_string_action(self):
        arg = argclass.TypedArgument(action="store_false")
        assert coerce_env_default("yes", arg) is True

    def test_no_type_returns_raw(self):
        """Plain string-valued argument without ``type=`` passes the
        env value through untouched."""
        arg = argclass.TypedArgument()
        assert coerce_env_default("hello", arg) == "hello"

    def test_type_already_correct_returns_raw(self):
        """``type=str`` plus a str env value short-circuits the
        coercion (no redundant ``str("hello")`` call)."""
        arg = argclass.TypedArgument(type=str)
        assert coerce_env_default("hello", arg) == "hello"

    def test_type_conversion_failure_returns_raw(self):
        arg = argclass.TypedArgument(type=int)
        assert coerce_env_default("not-an-int", arg) == "not-an-int"

    def test_type_callable_not_a_class(self):
        """A ``type=`` callable that is not itself a class (e.g.
        a function) takes the ``isinstance(raw, type_func)`` path
        through TypeError and falls back to calling it."""

        def double(value: str) -> str:
            return value + value

        arg = argclass.TypedArgument(type=double)
        assert coerce_env_default("ab", arg) == "abab"

    def test_non_string_input_passes_through(self):
        """Callers may stash non-string values in kwargs[default]
        (e.g. a Path or int) before env handling runs. The helper
        must pass them through untouched."""
        arg = argclass.TypedArgument(type=int)
        assert coerce_env_default(42, arg) == 42
        assert coerce_env_default(None, arg) is None


class TestCurrentValueNamespacePriority:
    """``current_value`` must prefer the supplied argparse namespace
    over the instance ``__dict__``. Otherwise a parser that was
    already parsed once would dump stale values when
    ``GenerateConfigAction`` runs during a later parse."""

    def test_namespace_overrides_stale_instance_dict(self):
        """Simulate: parse once with host=old; reuse the parser and
        parse again with host=new + --generate-config. The dump must
        reflect 'new', not the stale 'old' on the instance."""
        arg = argclass.TypedArgument(default="x")
        target = type("Stub", (), {"__dict__": {"host": "old"}})()
        ns = argparse.Namespace(host="new")
        result = current_value(
            target,
            "host",
            arg,
            namespace=ns,
            dest="host",
        )
        assert result == "new"

    def test_namespace_absent_falls_back_to_instance_dict(self):
        """Programmatic post-parse dump (no namespace) reads from
        the instance state — that's the only place the parsed
        values live."""
        arg = argclass.TypedArgument(default="x")
        target = type("Stub", (), {"__dict__": {"host": "parsed"}})()
        assert current_value(target, "host", arg) == "parsed"


class TestEnvStringEscaping:
    """``.env`` files are line-oriented; any value with a literal
    newline / CR / tab must be escaped, not emitted raw."""

    def test_newline_escaped(self):
        gen = EnvConfigGenerator()
        assert gen.quote_string("a\nb") == r'"a\nb"'

    def test_carriage_return_escaped(self):
        gen = EnvConfigGenerator()
        assert gen.quote_string("a\rb") == r'"a\rb"'

    def test_tab_escaped(self):
        gen = EnvConfigGenerator()
        assert gen.quote_string("a\tb") == r'"a\tb"'

    def test_dump_with_multiline_value_stays_one_line(self):
        """End-to-end: env dump of a multi-line value must still
        produce a single KEY=value line."""

        class App(argclass.Parser):
            banner: str = argclass.Argument(
                default="line1\nline2",
                env_var="BANNER",
            )

        text = EnvConfigGenerator().dump_to_string(App())
        body_lines = [
            line
            for line in text.splitlines()
            if line and not line.startswith("#")
        ]
        assert len(body_lines) == 1
        assert body_lines[0] == r'BANNER="line1\nline2"'


class TestDumpAcceptsPath:
    def test_dump_to_path_object(self, tmp_path: Path):
        """``dump(parser, Path(...))`` must work, not just ``str``."""

        class App(argclass.Parser):
            host: str = "localhost"

        path_obj = tmp_path / "cfg.ini"
        INIConfigGenerator().dump(App(), path_obj)
        assert path_obj.read_text().startswith("[DEFAULT]")


class TestCrossFormatRoundTrip:
    """End-to-end: take a richly-shaped parser, drive CLI/env values
    through it, dump to every format, then load each dump back into a
    FRESH parser of the same shape — every value must come back equal.

    Covers all the features users actually compose in one shot:
    top-level args of several types, a 2-level + 3-level nested
    group hierarchy, a `list[T]` field, a `bool` flag, an arg with
    explicit `env_var=`, and a Secret field.
    """

    @staticmethod
    def make_complex_parser() -> Type[argclass.Parser]:
        class TLS(argclass.Group):
            cert: str = argclass.Argument(
                default="/etc/tls/cert",
                help="TLS certificate path",
            )
            key: str = "/etc/tls/key"

        class Security(argclass.Group):
            tls: TLS = TLS()
            verify: bool = False

        class Database(argclass.Group):
            host: str = argclass.Argument(
                default="db.local",
                help="Database host",
            )
            port: int = 5432
            security: Security = Security()

        class Logging(argclass.Group):
            level: str = "info"
            file: Optional[str] = None

        class App(argclass.Parser):
            name: str = argclass.Argument(
                default="myapp",
                help="App name",
            )
            workers: int = 4
            debug: bool = False
            tags: list[str] = argclass.Argument(
                nargs=argclass.Nargs.ZERO_OR_MORE,
                default=["alpha", "beta"],
            )
            token: str = argclass.Argument(
                default="default-token",
                env_var="MY_TOKEN",
                help="API token",
            )
            api_key: str = argclass.Secret(default="default-key")
            db: Database = Database()
            log: Logging = Logging()

        return App

    @pytest.fixture
    def populated_parser(
        self,
        monkeypatch,
    ) -> argclass.Parser:
        """Build a parser, drive CLI args, env vars, and an explicit
        env_var-bound field through it. The returned instance carries
        a mixture of values from each source."""
        App = self.make_complex_parser()
        # explicit-env_var-bound field
        monkeypatch.setenv("MY_TOKEN", "secret-from-env")
        # auto-prefix env vars at every level of the group tree
        monkeypatch.setenv("APP_WORKERS", "8")
        monkeypatch.setenv("APP_DB_HOST", "prod.example.com")
        monkeypatch.setenv("APP_DB_SECURITY_VERIFY", "true")

        parser = App(auto_env_var_prefix="APP_")
        parser.parse_args(
            [
                "--name",
                "from-cli",
                "--debug",
                "--tags",
                "x",
                "y",
                "z",
                "--api-key",
                "sk-cli-123",
                "--db-security-tls-cert",
                "/cli/cert",
                "--log-level",
                "debug",
            ],
        )
        return parser

    @staticmethod
    def assert_state(parser: argclass.Parser) -> None:
        """Pin down the exact resolved state after parse_args. Used
        for both the source parser and every reloaded copy so any
        format that drops a value gets caught."""
        assert parser.name == "from-cli"
        assert parser.workers == 8
        assert parser.debug is True
        assert parser.tags == ["x", "y", "z"]
        assert parser.token == "secret-from-env"
        # Secret() — value survives round-trip; SecretString masks
        # its repr but compares equal as a plain string.
        assert parser.api_key == "sk-cli-123"
        assert isinstance(parser.api_key, argclass.SecretString)
        assert parser.db.host == "prod.example.com"
        assert parser.db.port == 5432
        assert parser.db.security.verify is True
        assert parser.db.security.tls.cert == "/cli/cert"
        assert parser.db.security.tls.key == "/etc/tls/key"
        assert parser.log.level == "debug"
        assert parser.log.file is None

    def test_populated_parser_baseline(
        self,
        populated_parser: argclass.Parser,
    ) -> None:
        """Sanity-check the fixture itself before round-tripping."""
        self.assert_state(populated_parser)

    @pytest.mark.parametrize(
        "fmt,generator,parser_cls",
        [
            (
                "ini",
                INIConfigGenerator,
                argclass.INIDefaultsParser,
            ),
            (
                "json",
                JSONConfigGenerator,
                argclass.JSONDefaultsParser,
            ),
            (
                "toml",
                TOMLConfigGenerator,
                argclass.TOMLDefaultsParser,
            ),
        ],
    )
    def test_file_format_roundtrip(
        self,
        tmp_path: Path,
        populated_parser: argclass.Parser,
        fmt: str,
        generator: type,
        parser_cls: type,
    ) -> None:
        out = tmp_path / f"app.{fmt}"
        generator().dump(populated_parser, str(out))

        # Brand-new parser class graph — no leaked state from the
        # source parser. Same shape, same defaults.
        App = self.make_complex_parser()
        loaded = App(
            config_files=[out],
            config_parser_class=parser_cls,
        )
        loaded.parse_args([])
        self.assert_state(loaded)

    def test_env_format_roundtrip(
        self,
        populated_parser: argclass.Parser,
        monkeypatch,
    ) -> None:
        """Env round-trip is special: we dump KEY=VALUE lines, then
        set those env vars and parse a fresh parser with the same
        auto_env_var_prefix. The reloaded state must match."""
        text = EnvConfigGenerator().dump_to_string(populated_parser)

        # Wipe the env vars from the source fixture so the env-only
        # reload exercises ONLY what the dump produced.
        for key in (
            "MY_TOKEN",
            "APP_WORKERS",
            "APP_DB_HOST",
            "APP_DB_SECURITY_VERIFY",
        ):
            monkeypatch.delenv(key, raising=False)

        # Replay the dumped lines as env vars.
        for line in text.splitlines():
            if not line or line.startswith("#"):
                continue
            key, _, raw_value = line.partition("=")
            # Strip surrounding quotes (matches what shell would do).
            value = raw_value
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            monkeypatch.setenv(key, value)

        App = self.make_complex_parser()
        loaded = App(auto_env_var_prefix="APP_")
        loaded.parse_args([])
        self.assert_state(loaded)


class TestDumpDestinations:
    def test_dump_to_file_like(self, make_cli):
        CLI = make_cli()
        buf = io.StringIO()
        INIConfigGenerator().dump(CLI(), buf)
        text = buf.getvalue()
        assert "host = localhost" in text

    def test_dump_to_string_returns_text(self, make_cli):
        CLI = make_cli()
        text = INIConfigGenerator().dump_to_string(CLI())
        assert "host = localhost" in text
