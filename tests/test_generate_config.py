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
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Type

import pytest

import argclass
from argclass.emit import (
    ConfigGenerator,
    EnvConfigGenerator,
    GenerateConfigAction,
    HelpMap,
    INIConfigGenerator,
    JSONConfigGenerator,
    NonConfigAction,
    TOMLConfigGenerator,
    current_value,
    derive_env_var,
    should_emit,
)


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

            def render(
                self,
                data: Dict[str, Any],
                help_map: Optional[HelpMap] = None,
            ) -> str:
                lines: List[str] = []
                self.walk(data, (), lines)
                return "\n".join(lines) + "\n"

            def walk(
                self,
                data: Dict[str, Any],
                path: tuple,
                lines: List[str],
            ) -> None:
                for key, value in data.items():
                    if isinstance(value, dict):
                        self.walk(value, path + (key,), lines)
                    else:
                        full_key = ".".join(path + (key,))
                        lines.append(f"{full_key}={value}")

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
            ConfigGenerator().render({})

    def test_ini_none_value_renders_empty(self):
        gen = INIConfigGenerator()
        assert gen.render_scalar(None) == ""

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

    def test_render_raises_when_called_without_env_metadata(self):
        gen = EnvConfigGenerator()
        with pytest.raises(NotImplementedError):
            gen.render({})

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

    def test_build_env_map_with_prefix_override(self):
        """Group(prefix=...) overrides the env-var path segment."""

        class Inner(argclass.Group):
            value: str = "x"

        class App(argclass.Parser):
            inner: Inner = Inner(prefix="i")

        p = App(auto_env_var_prefix="APP_")
        env_map = EnvConfigGenerator().build_env_map(p)
        assert env_map[("inner", "value")] == "APP_I_VALUE"

    def test_build_env_map_with_empty_prefix(self):
        class Inner(argclass.Group):
            value: str = "x"

        class App(argclass.Parser):
            inner: Inner = Inner(prefix="")

        p = App(auto_env_var_prefix="APP_")
        env_map = EnvConfigGenerator().build_env_map(p)
        assert env_map[("inner", "value")] == "APP_VALUE"

    def test_nested_group_skips_non_config_action(self):
        """NonConfigAction marker on an arg inside a nested group
        keeps it out of the env_map too."""

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

        env_map = EnvConfigGenerator().build_env_map(
            App(auto_env_var_prefix="APP_"),
        )
        assert ("inner", "host") in env_map
        assert ("inner", "meta") not in env_map

    def test_nested_group_skips_arg_without_resolvable_env(self):
        """No auto_env_var_prefix AND no explicit env_var on an arg
        inside a group — that arg is absent from the env_map."""

        class Inner(argclass.Group):
            quiet: str = "yes"
            shouted: str = argclass.Argument(
                default="x",
                env_var="SHOUTED",
            )

        class App(argclass.Parser):
            inner: Inner = Inner()

        env_map = EnvConfigGenerator().build_env_map(App())
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
