"""Tests for nested argument groups (Parser -> Group -> Group -> ...).

Covers CLI, environment variables, INI/JSON/TOML configs, help output,
priority order, secrets, list-typed fields, and same-instance reuse
detection.
"""

import os
from pathlib import Path
from typing import List
from unittest.mock import patch

import pytest

import argclass
from argclass.defaults import JSONDefaultsParser, TOMLDefaultsParser
from argclass.exceptions import ArgclassError


class Credentials(argclass.Group):
    username: str = "admin"
    password: str = "secret"


class Endpoint(argclass.Group):
    host: str = "localhost"
    port: int = 8080
    credentials: Credentials = Credentials()


class CLI(argclass.Parser):
    debug: bool = False
    endpoint: Endpoint = Endpoint()


class TestCLI:
    def test_defaults(self):
        parser = CLI()
        parser.parse_args([])
        assert parser.debug is False
        assert parser.endpoint.host == "localhost"
        assert parser.endpoint.port == 8080
        assert parser.endpoint.credentials.username == "admin"
        assert parser.endpoint.credentials.password == "secret"

    def test_override_all_levels(self):
        parser = CLI()
        parser.parse_args(
            [
                "--debug",
                "--endpoint-host=10.0.0.1",
                "--endpoint-port=9000",
                "--endpoint-credentials-username=root",
                "--endpoint-credentials-password=hunter2",
            ],
        )
        assert parser.debug is True
        assert parser.endpoint.host == "10.0.0.1"
        assert parser.endpoint.port == 9000
        assert parser.endpoint.credentials.username == "root"
        assert parser.endpoint.credentials.password == "hunter2"

    def test_three_level_nesting(self):
        class TLS(argclass.Group):
            cert: str = "/etc/cert"
            key: str = "/etc/key"

        class ConnectionSecurity(argclass.Group):
            tls: TLS = TLS()
            verify: bool = False

        class Connection(argclass.Group):
            host: str = "localhost"
            security: ConnectionSecurity = ConnectionSecurity()

        class App(argclass.Parser):
            conn: Connection = Connection()

        parser = App()
        parser.parse_args(
            [
                "--conn-host=db.example.com",
                "--conn-security-verify",
                "--conn-security-tls-cert=/new/cert",
            ],
        )
        assert parser.conn.host == "db.example.com"
        assert parser.conn.security.verify is True
        assert parser.conn.security.tls.cert == "/new/cert"
        assert parser.conn.security.tls.key == "/etc/key"

    def test_list_inside_nested_group(self):
        class Tags(argclass.Group):
            values: List[str] = argclass.Argument(
                nargs=argclass.Nargs.ONE_OR_MORE,
            )

        class Resource(argclass.Group):
            name: str = "thing"
            tags: Tags = Tags()

        class App(argclass.Parser):
            resource: Resource = Resource()

        parser = App()
        parser.parse_args(
            [
                "--resource-tags-values",
                "alpha",
                "beta",
                "gamma",
            ],
        )
        assert parser.resource.tags.values == ["alpha", "beta", "gamma"]


class TestPrefix:
    def test_prefix_on_nested_group_overrides_cli_name(self):
        class Inner(argclass.Group):
            value: str = "default"

        class Outer(argclass.Group):
            inner: Inner = Inner(prefix="i")

        class App(argclass.Parser):
            outer: Outer = Outer()

        parser = App()
        parser.parse_args(["--outer-i-value=set"])
        assert parser.outer.inner.value == "set"

    def test_empty_prefix_on_nested_group_drops_segment(self):
        class Inner(argclass.Group):
            value: str = "default"

        class Outer(argclass.Group):
            inner: Inner = Inner(prefix="")

        class App(argclass.Parser):
            outer: Outer = Outer()

        parser = App()
        parser.parse_args(["--outer-value=set"])
        assert parser.outer.inner.value == "set"


class TestEnv:
    def test_auto_env_var_prefix_nested(self):
        env = {"APP_ENDPOINT_CREDENTIALS_USERNAME": "root_from_env"}
        with patch.dict(os.environ, env, clear=False):
            parser = CLI(auto_env_var_prefix="APP_")
            parser.parse_args([])
        assert parser.endpoint.credentials.username == "root_from_env"
        assert parser.endpoint.credentials.password == "secret"

    def test_explicit_env_var_in_nested_group(self):
        class Inner(argclass.Group):
            token: str = argclass.Argument(env_var="MY_TOKEN", default="")

        class Outer(argclass.Group):
            inner: Inner = Inner()

        class App(argclass.Parser):
            outer: Outer = Outer()

        env = {"MY_TOKEN": "abc123"}
        with patch.dict(os.environ, env, clear=False):
            parser = App(auto_env_var_prefix="APP_")
            parser.parse_args([])
        assert parser.outer.inner.token == "abc123"


class TestINI:
    def test_nested_section(self, tmp_path: Path):
        cfg = tmp_path / "config.ini"
        cfg.write_text(
            "[endpoint]\nhost = ini-host\nport = 9999\n"
            "[endpoint.credentials]\nusername = ini-user\n"
            "password = ini-pass\n",
        )
        parser = CLI(config_files=[cfg])
        parser.parse_args([])
        assert parser.endpoint.host == "ini-host"
        assert parser.endpoint.port == 9999
        assert parser.endpoint.credentials.username == "ini-user"
        assert parser.endpoint.credentials.password == "ini-pass"

    def test_missing_nested_section_falls_back_to_default(
        self,
        tmp_path: Path,
    ):
        cfg = tmp_path / "config.ini"
        cfg.write_text("[endpoint]\nhost = only-host\n")
        parser = CLI(config_files=[cfg])
        parser.parse_args([])
        assert parser.endpoint.host == "only-host"
        assert parser.endpoint.credentials.username == "admin"

    def test_three_level_ini(self, tmp_path: Path):
        class TLS(argclass.Group):
            cert: str = "/etc/cert"

        class Sec(argclass.Group):
            tls: TLS = TLS()

        class Conn(argclass.Group):
            sec: Sec = Sec()

        class App(argclass.Parser):
            conn: Conn = Conn()

        cfg = tmp_path / "config.ini"
        cfg.write_text("[conn.sec.tls]\ncert = /custom/cert\n")
        parser = App(config_files=[cfg])
        parser.parse_args([])
        assert parser.conn.sec.tls.cert == "/custom/cert"


class TestJSON:
    def test_nested_dict(self, tmp_path: Path):
        cfg = tmp_path / "config.json"
        cfg.write_text(
            '{"endpoint": {"host": "json-host", '
            '"credentials": {"username": "json-user", '
            '"password": "json-pass"}}}',
        )
        parser = CLI(
            config_files=[cfg],
            config_parser_class=JSONDefaultsParser,
        )
        parser.parse_args([])
        assert parser.endpoint.host == "json-host"
        assert parser.endpoint.credentials.username == "json-user"
        assert parser.endpoint.credentials.password == "json-pass"


class TestTOML:
    def test_nested_table(self, tmp_path: Path):
        cfg = tmp_path / "config.toml"
        cfg.write_text(
            '[endpoint]\nhost = "toml-host"\n'
            '[endpoint.credentials]\nusername = "toml-user"\n'
            'password = "toml-pass"\n',
        )
        parser = CLI(
            config_files=[cfg],
            config_parser_class=TOMLDefaultsParser,
        )
        parser.parse_args([])
        assert parser.endpoint.host == "toml-host"
        assert parser.endpoint.credentials.username == "toml-user"
        assert parser.endpoint.credentials.password == "toml-pass"


class TestPriority:
    def test_cli_beats_env_beats_config_beats_default(
        self,
        tmp_path: Path,
    ):
        cfg = tmp_path / "config.ini"
        cfg.write_text(
            "[endpoint.credentials]\nusername = from-config\n"
            "password = from-config\n",
        )

        env = {
            "APP_ENDPOINT_CREDENTIALS_USERNAME": "from-env",
            "APP_ENDPOINT_CREDENTIALS_PASSWORD": "from-env",
        }
        with patch.dict(os.environ, env, clear=False):
            parser = CLI(
                config_files=[cfg],
                auto_env_var_prefix="APP_",
            )
            parser.parse_args(
                ["--endpoint-credentials-username=from-cli"],
            )
        # CLI wins for username, env wins for password
        assert parser.endpoint.credentials.username == "from-cli"
        assert parser.endpoint.credentials.password == "from-env"

    def test_config_beats_default_when_no_env_no_cli(
        self,
        tmp_path: Path,
    ):
        cfg = tmp_path / "config.ini"
        cfg.write_text(
            "[endpoint.credentials]\nusername = from-config\n",
        )
        parser = CLI(config_files=[cfg])
        parser.parse_args([])
        assert parser.endpoint.credentials.username == "from-config"
        assert parser.endpoint.credentials.password == "secret"


class TestSecret:
    def test_secret_inside_nested_group(self):
        class Auth(argclass.Group):
            token: str = argclass.Secret()

        class Outer(argclass.Group):
            auth: Auth = Auth()

        class App(argclass.Parser):
            outer: Outer = Outer()

        parser = App()
        parser.parse_args(["--outer-auth-token=topsecret"])
        # Stored value is the actual string under SecretString.
        assert parser.outer.auth.token == "topsecret"
        # SecretString masks itself in repr.
        assert "topsecret" not in repr(parser.outer.auth.token)


class TestHelp:
    def test_help_contains_nested_arg_and_section(self, capsys):
        parser = CLI()
        parser.print_help()
        out = capsys.readouterr().out
        assert "--endpoint-credentials-username" in out
        assert "endpoint.credentials" in out


class TestSameInstanceReuse:
    def test_reused_group_instance_raises(self):
        shared = Credentials()

        class Outer(argclass.Group):
            primary: Credentials = shared
            secondary: Credentials = shared

        class App(argclass.Parser):
            outer: Outer = Outer()

        parser = App()
        with pytest.raises(ArgclassError) as exc_info:
            parser.parse_args([])
        assert "referenced more than once" in str(exc_info.value)

    def test_two_distinct_instances_of_same_class_ok(self):
        class Outer(argclass.Group):
            primary: Credentials = Credentials()
            secondary: Credentials = Credentials()

        class App(argclass.Parser):
            outer: Outer = Outer()

        parser = App()
        parser.parse_args(
            [
                "--outer-primary-username=a",
                "--outer-secondary-username=b",
            ],
        )
        assert parser.outer.primary.username == "a"
        assert parser.outer.secondary.username == "b"
