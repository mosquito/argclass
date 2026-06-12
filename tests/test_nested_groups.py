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
from argclass.exceptions import ArgclassError, ArgumentDefinitionError


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

    def test_non_dict_intermediate_in_dotted_path_returns_default(
        self,
        tmp_path: Path,
    ):
        """If an intermediate config value on the dotted descent path
        is not a dict (e.g. a string), get_value falls back to the
        argument's own default instead of crashing."""
        cfg = tmp_path / "config.json"
        # endpoint.credentials would descend into "not-a-dict", which
        # is not a dict — should return None and fall back to defaults.
        cfg.write_text('{"endpoint": "not-a-dict"}')
        parser = CLI(
            config_files=[cfg],
            config_parser_class=JSONDefaultsParser,
        )
        parser.parse_args([])
        assert parser.endpoint.credentials.username == "admin"
        assert parser.endpoint.credentials.password == "secret"

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


class TestGroupAnnotation:
    """Annotated Group fields: auto-instantiate, reject Optional/None/etc."""

    def test_annotation_only_auto_instantiates(self):
        class G(argclass.Group):
            foo: int = 0

        class P(argclass.Parser):
            g: G

        parser = P()
        parser.parse_args(["--g-foo=5"])
        assert parser.g.foo == 5

    def test_annotation_with_ellipsis_auto_instantiates(self):
        class G(argclass.Group):
            foo: int = 0

        class P(argclass.Parser):
            g: G = ...  # type: ignore[assignment]

        parser = P()
        parser.parse_args(["--g-foo=7"])
        assert parser.g.foo == 7

    def test_annotation_with_explicit_instance_works(self):
        class G(argclass.Group):
            foo: int = 0

        class P(argclass.Parser):
            g: G = G()

        parser = P()
        parser.parse_args(["--g-foo=3"])
        assert parser.g.foo == 3

    def test_optional_group_rejected(self):
        class G(argclass.Group):
            foo: int = 0

        with pytest.raises(ArgumentDefinitionError) as exc_info:

            class P(argclass.Parser):  # noqa: F841
                g: G | None = None

        assert "cannot be Optional" in str(exc_info.value)

    def test_none_default_with_group_annotation_rejected(self):
        class G(argclass.Group):
            foo: int = 0

        with pytest.raises(ArgumentDefinitionError) as exc_info:

            class P(argclass.Parser):  # noqa: F841
                g: G = None  # type: ignore[assignment]

        assert "non-Group default" in str(exc_info.value)

    def test_non_group_default_rejected(self):
        class G(argclass.Group):
            foo: int = 0

        with pytest.raises(ArgumentDefinitionError) as exc_info:

            class P(argclass.Parser):  # noqa: F841
                g: G = "weird"  # type: ignore[assignment]

        assert "non-Group default" in str(exc_info.value)

    def test_incompatible_group_instance_rejected(self):
        class G1(argclass.Group):
            foo: int = 0

        class G2(argclass.Group):
            bar: int = 0

        with pytest.raises(ArgumentDefinitionError) as exc_info:

            class P(argclass.Parser):  # noqa: F841
                g: G1 = G2()  # type: ignore[assignment]

        assert "incompatible instance" in str(exc_info.value)

    def test_annotated_nested_group_auto_instantiates(self):
        class Inner(argclass.Group):
            value: str = "default"

        class Outer(argclass.Group):
            inner: Inner

        class P(argclass.Parser):
            outer: Outer

        parser = P()
        parser.parse_args(["--outer-inner-value=set"])
        assert parser.outer.inner.value == "set"

    def test_group_in_complex_union_with_non_group_rejected(self):
        """G | int (non-Optional union mixing Group with a regular
        type) gets a Group-specific error message — not the generic
        "use argclass.Argument with converter" hint, which would not
        help the user understand the real problem."""

        class G(argclass.Group):
            foo: int = 0

        with pytest.raises(ArgumentDefinitionError) as exc_info:
            type(
                "P",
                (argclass.Parser,),
                {"__annotations__": {"g": G | int}, "g": ...},
            )

        msg = str(exc_info.value)
        assert "complex Union" in msg
        assert "G" in msg

    def test_union_of_two_group_classes_rejected(self):
        """G1 | G2 is also rejected — only one Group class is
        meaningful per attribute."""

        class G1(argclass.Group):
            foo: int = 0

        class G2(argclass.Group):
            bar: int = 0

        with pytest.raises(ArgumentDefinitionError) as exc_info:
            type(
                "P",
                (argclass.Parser,),
                {"__annotations__": {"g": G1 | G2}, "g": ...},
            )

        assert "complex Union" in str(exc_info.value)

    def test_three_member_union_with_group_and_none_rejected(self):
        """G | int | None — three-member union containing a Group
        also gets the Group-specific error."""

        class G(argclass.Group):
            foo: int = 0

        with pytest.raises(ArgumentDefinitionError) as exc_info:
            type(
                "P",
                (argclass.Parser,),
                {"__annotations__": {"g": G | int | None}, "g": None},
            )

        assert "complex Union" in str(exc_info.value)

    def test_non_group_complex_union_unaffected(self):
        """int | str without explicit Argument still raises
        ComplexTypeError (the pre-existing behaviour) — our new
        Group-aware detection must not interfere with unrelated
        Union annotations."""
        from argclass.exceptions import ComplexTypeError

        with pytest.raises(ComplexTypeError):
            type(
                "P",
                (argclass.Parser,),
                {"__annotations__": {"v": int | str}},
            )

    def test_complex_union_annotation_does_not_break_group_detection(self):
        """Fields with unsupported Union types (e.g. int | str) must
        not raise during class definition just because we probe for
        Group membership — they should still reach the regular
        argument path."""

        def coerce(v: str) -> object:
            try:
                return int(v)
            except ValueError:
                return v

        class P(argclass.Parser):
            value: int | str = argclass.Argument(
                type=coerce,
                default=0,
            )

        parser = P()
        parser.parse_args(["--value", "42"])
        assert parser.value == 42


class TestSameInstanceReuse:
    def test_reused_group_instance_cloned_independently(self):
        # Every binding gets its own per-parser-instance copy, so the
        # same Group instance may be assigned to several attributes —
        # each location keeps independent parsed state.
        shared = Credentials()

        class Outer(argclass.Group):
            primary: Credentials = shared
            secondary: Credentials = shared

        class App(argclass.Parser):
            outer: Outer = Outer()

        parser = App()
        assert parser.outer.primary is not parser.outer.secondary
        parser.parse_args(
            [
                "--outer-primary-username=alice",
                "--outer-secondary-username=bob",
            ],
        )
        assert parser.outer.primary.username == "alice"
        assert parser.outer.secondary.username == "bob"
        # The shared prototype itself is untouched.
        with pytest.raises(AttributeError):
            shared.username

    def test_reused_instance_at_parser_level(self):
        shared = Credentials()

        class App(argclass.Parser):
            primary: Credentials = shared
            secondary: Credentials = shared

        parser = App()
        parser.parse_args(
            [
                "--primary-username=alice",
                "--secondary-username=bob",
            ],
        )
        assert parser.primary.username == "alice"
        assert parser.secondary.username == "bob"

    def test_three_link_cycle_raises(self):
        """A → B → C → A. Synthetic — normal class syntax can't form
        this because forward refs don't resolve at metaclass time —
        but we manually wire __argument_groups__ to verify the
        visited-set detector catches arbitrary cycles, not just
        same-instance reuse on sibling attributes.
        """
        from types import MappingProxyType

        class A(argclass.Group):
            foo: int = 1

        class B(argclass.Group):
            foo: int = 2

        class C(argclass.Group):
            foo: int = 3

        a, b, c = A(), B(), C()
        A.__argument_groups__ = MappingProxyType({"b": b})
        B.__argument_groups__ = MappingProxyType({"c": c})
        C.__argument_groups__ = MappingProxyType({"a": a})

        try:

            class P(argclass.Parser):
                root: A = a

            with pytest.raises(ArgclassError) as exc_info:
                P()
            assert "referenced more than once" in str(exc_info.value)
            assert "root.b.c.a" in str(exc_info.value)
        finally:
            A.__argument_groups__ = MappingProxyType({})
            B.__argument_groups__ = MappingProxyType({})
            C.__argument_groups__ = MappingProxyType({})

    def test_self_loop_raises(self):
        """A group whose own __argument_groups__ contains itself."""
        from types import MappingProxyType

        class Loop(argclass.Group):
            foo: int = 0

        instance = Loop()
        Loop.__argument_groups__ = MappingProxyType({"self": instance})

        try:

            class P(argclass.Parser):
                root: Loop = instance

            with pytest.raises(ArgclassError) as exc_info:
                P()
            assert "referenced more than once" in str(exc_info.value)
        finally:
            Loop.__argument_groups__ = MappingProxyType({})

    def test_post_init_cycle_caught_at_parse(self):
        """Cycles wired into the per-instance mappings after
        construction are caught by the parse-time backstop."""
        from types import MappingProxyType

        class G(argclass.Group):
            foo: int = 1

        class P(argclass.Parser):
            root: G = G()

        parser = P()
        clone = parser.root
        clone.__argument_groups__ = MappingProxyType({"again": clone})
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

    def test_single_external_instance_bound_once_ok(self):
        """An externally-created Group instance assigned to a single
        attribute is fine; the parser works on its own copy."""
        shared = Credentials()

        class P(argclass.Parser):
            primary: Credentials = shared

        parser = P()
        parser.parse_args(["--primary-username=alice"])
        assert parser.primary.username == "alice"
        # The parser works on its own per-instance copy; the class
        # body prototype stays pristine.
        assert parser.primary is not shared
        with pytest.raises(AttributeError):
            shared.username
