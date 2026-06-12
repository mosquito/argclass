"""Regression tests for the source-audit fixes.

Each test class covers one finding:

1.  A single ``Argument()`` instance shared by several fields/classes
    must not be mutated in place by the metaclass.
2.  Arguments may not shadow methods/properties of the Parser API or
    of user base classes.
3.  ``serve: Serve`` (annotation without an instance) must raise
    instead of silently becoming a CLI argument.
4.  ``strict=False`` defaults parsers skip malformed files for every
    format (INI/JSON/TOML); ``strict=True`` propagates the error.
5.  ``Secret(nargs=...)`` wraps every list element in SecretString.
8.  ``EnumArgument(lowercase=True)`` works for enums whose member
    names are not fully uppercase; enum aliases stay accepted.
9.  ``Optional[T]`` + bare ``Argument()`` still unwraps properly
    (guards the dead-code removal around the optional unwrap).
10. ``INIDefaultsParser.BOOL_TRUE_VALUES`` is the shared constant.
11. ``ConfigAction`` caches an empty parse result (None sentinel).
12. Unannotated arguments/groups/subparsers survive subclassing.
"""

import argparse
import configparser
import enum
from pathlib import Path

import pytest

import argclass
from argclass import SecretString
from argclass.types import TEXT_TRUE_VALUES


class SharedDB(argclass.Group):
    host: str = "localhost"


class SharedServe(argclass.Parser):
    port: int = 8080


class TestSharedArgumentInstance:
    """Fix 1: copy-on-write before the metaclass infers type/nargs."""

    def test_two_fields_same_class(self):
        arg = argclass.Argument()

        class P(argclass.Parser):
            a: int = arg
            b: str = arg

        p = P()
        p.parse_args(["--a", "5", "--b", "hello"])
        assert p.a == 5
        assert p.b == "hello"

    def test_two_classes(self):
        arg = argclass.Argument(help="shared")

        class A(argclass.Parser):
            x: int = arg

        class B(argclass.Parser):
            y: str = arg

        b = B()
        b.parse_args(["--y", "world"])
        assert b.y == "world"

        a = A()
        a.parse_args(["--x", "3"])
        assert a.x == 3

    def test_user_instance_not_mutated(self):
        arg = argclass.Argument()

        class P(argclass.Parser):
            a: int = arg

        assert arg.type is None
        assert arg.nargs is None
        assert P.__arguments__["a"].type is int


class TestApiShadowGuard:
    """Fix 2: arguments may not clobber methods/properties."""

    @pytest.mark.parametrize(
        "name",
        ["parse_args", "print_help", "sanitize_env", "create_parser"],
    )
    def test_annotated_field_rejected(self, name):
        with pytest.raises(argclass.ArgumentDefinitionError) as exc_info:
            type(
                "Bad",
                (argclass.Parser,),
                {"__annotations__": {name: str}, name: "oops"},
            )
        assert "shadow" in str(exc_info.value)

    def test_unannotated_argument_rejected(self):
        with pytest.raises(argclass.ArgumentDefinitionError):

            class Bad(argclass.Parser):
                print_help = argclass.Argument()  # type: ignore[assignment]

    def test_user_helper_method_protected(self):
        class A(argclass.Parser):
            def helper(self) -> int:
                return 1

        with pytest.raises(argclass.ArgumentDefinitionError):

            class B(A):
                helper: str = "x"  # type: ignore[assignment]

    def test_own_body_method_and_annotation_rejected(self):
        with pytest.raises(argclass.ArgumentDefinitionError):

            class Bad(argclass.Parser):
                handler: str = "x"

                def handler(self) -> None:  # type: ignore[no-redef] # noqa: F811,E501
                    pass

    def test_overriding_inherited_argument_still_works(self):
        class A(argclass.Parser):
            x: int = 1

        class B(A):
            x: int = 2

        b = B()
        b.parse_args([])
        assert b.x == 2

    def test_overriding_inherited_group_still_works(self):
        class A(argclass.Parser):
            db = SharedDB()

        class B(A):
            db = SharedDB(title="other")

        assert B.__argument_groups__["db"] is not A.__argument_groups__["db"]


class TestAnnotationOnlySubparser:
    """Fix 3: a Parser-class annotation without an instance raises."""

    def test_bare_annotation_rejected(self):
        with pytest.raises(argclass.ArgumentDefinitionError) as exc_info:

            class CLI(argclass.Parser):
                serve: SharedServe

        message = str(exc_info.value)
        assert "SharedServe" in message
        assert "instance" in message

    def test_optional_annotation_rejected(self):
        with pytest.raises(argclass.ArgumentDefinitionError):

            class CLI(argclass.Parser):
                serve: SharedServe | None = None

    def test_annotated_with_instance_works(self):
        class CLI(argclass.Parser):
            serve: SharedServe = SharedServe()

        assert "serve" in CLI.__subparsers__
        cli = CLI()
        cli.parse_args(["serve", "--port", "9000"])
        assert cli.serve.port == 9000


class TestDefaultsParserStrictness:
    """Fix 4: consistent strict/non-strict across INI/JSON/TOML."""

    def test_malformed_toml_non_strict_skipped(self, tmp_path):
        bad = tmp_path / "bad.toml"
        bad.write_text("this is [[[ not toml")
        parser = argclass.TOMLDefaultsParser([bad], strict=False)
        assert dict(parser.parse()) == {}
        assert parser.loaded_files == ()

    def test_malformed_toml_strict_raises(self, tmp_path):
        bad = tmp_path / "bad.toml"
        bad.write_text("this is [[[ not toml")
        parser = argclass.TOMLDefaultsParser([bad], strict=True)
        with pytest.raises(ValueError):
            parser.parse()

    def test_malformed_ini_non_strict_skipped(self, tmp_path):
        bad = tmp_path / "bad.ini"
        bad.write_text("no section header\n")
        good = tmp_path / "good.ini"
        good.write_text("[sec]\nkey = value\n")
        parser = argclass.INIDefaultsParser([bad, good], strict=False)
        result = dict(parser.parse())
        assert result["sec"] == {"key": "value"}
        assert parser.loaded_files == (good,)

    def test_malformed_ini_strict_raises(self, tmp_path):
        bad = tmp_path / "bad.ini"
        bad.write_text("no section header\n")
        parser = argclass.INIDefaultsParser([bad], strict=True)
        with pytest.raises(configparser.Error):
            parser.parse()

    def test_malformed_json_non_strict_skipped(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text("{not json")
        parser = argclass.JSONDefaultsParser([bad], strict=False)
        assert dict(parser.parse()) == {}


class TestSecretSequences:
    """Fix 5: nargs secrets are wrapped element-wise."""

    def test_list_elements_masked(self):
        class P(argclass.Parser):
            keys: list[str] = argclass.Secret(nargs="+")

        p = P()
        p.parse_args(["--keys", "s3cret1", "s3cret2"])
        assert all(isinstance(k, SecretString) for k in p.keys)
        assert repr(p.keys) == "['******', '******']"
        # The actual values stay accessible via str()
        assert [str(k) for k in p.keys] == ["s3cret1", "s3cret2"]

    def test_single_secret_still_masked(self):
        class P(argclass.Parser):
            token: str = argclass.Secret()

        p = P()
        p.parse_args(["--token", "t0ken"])
        assert isinstance(p.token, SecretString)
        assert repr(p.token) == "'******'"


class TestEnumArgumentMixedCase:
    """Fix 8: lowercase=True works for non-UPPERCASE member names."""

    class Mode(enum.Enum):
        Fast = 1
        Slow = 2

    def test_mixed_case_member_parses(self):
        class P(argclass.Parser):
            mode = argclass.EnumArgument(self.Mode, lowercase=True)

        p = P()
        p.parse_args(["--mode", "fast"])
        assert p.mode is self.Mode.Fast

    def test_mixed_case_string_default(self):
        class P(argclass.Parser):
            mode = argclass.EnumArgument(
                self.Mode, lowercase=True, default="fast"
            )

        p = P()
        p.parse_args([])
        assert p.mode is self.Mode.Fast

    def test_invalid_default_still_rejected(self):
        with pytest.raises(argclass.EnumValueError):
            argclass.EnumArgument(self.Mode, lowercase=True, default="warp")

    def test_invalid_env_value_raises_conversion_error(self, monkeypatch):
        # Env values bypass argparse ``choices`` validation, so the
        # converter is the last line of defense for bad spellings.
        monkeypatch.setenv("AUDIT_MODE", "warp")

        class P(argclass.Parser):
            mode = argclass.EnumArgument(
                self.Mode, lowercase=True, env_var="AUDIT_MODE"
            )

        with pytest.raises(argclass.TypeConversionError):
            P().parse_args([])

    def test_enum_aliases_still_accepted(self):
        # LogLevelEnum.WARN is an alias of WARNING; aliases are valid
        # inputs even though choices list canonical names only.
        class P(argclass.Parser):
            log_level: int = argclass.LogLevel

        p = P()
        p.parse_args(["--log-level", "warning"])
        assert p.log_level == 30


class TestOptionalArgumentUnwrap:
    """Fix 9 regression guard: Optional[T] + bare Argument() still
    unwraps to T and stays optional after the dead-code removal."""

    def test_optional_int_argument(self):
        class P(argclass.Parser):
            x: int | None = argclass.Argument()

        p = P()
        p.parse_args([])
        assert p.x is None
        p.parse_args(["--x", "5"])
        assert p.x == 5
        assert isinstance(p.x, int)


class TestBoolValuesShared:
    """Fix 10: the INI bool set is the shared TEXT_TRUE_VALUES."""

    def test_alias(self):
        assert argclass.INIDefaultsParser.BOOL_TRUE_VALUES is TEXT_TRUE_VALUES


class TestConfigActionCache:
    """Fix 11: empty parse results are cached via the None sentinel."""

    class CountingAction(argclass.INIConfigAction):
        def __init__(self, *args: object, **kwargs: object) -> None:
            super().__init__(*args, **kwargs)  # type: ignore[arg-type]
            self.parse_calls = 0

        def parse(self, *files: Path) -> dict:
            self.parse_calls += 1
            return {}

    def test_empty_result_not_reparsed(self, tmp_path):
        config = tmp_path / "app.ini"
        config.write_text("[DEFAULT]\n")
        action = self.CountingAction(
            option_strings=["--config"],
            dest="config",
        )
        parser = argparse.ArgumentParser()
        namespace = argparse.Namespace()

        action(parser, namespace, str(config))
        # Second invocation passes the already-set mapping back in, as
        # Parser.parse_args does; the cached empty result must be used.
        action(parser, namespace, getattr(namespace, "config"))
        assert action.parse_calls == 1
        assert dict(namespace.config) == {}


class TestUnannotatedInheritance:
    """Fix 12: unannotated members survive subclassing."""

    def test_subclass_inherits_everything(self):
        class A(argclass.Parser):
            tags = argclass.Argument(nargs="+", type=str)
            db = SharedDB()
            serve = SharedServe()
            name: str = "x"

        class B(A):
            extra: int = 1

        assert set(B.__arguments__) == {"tags", "name", "extra"}
        assert set(B.__argument_groups__) == {"db"}
        assert set(B.__subparsers__) == {"serve"}

        b = B()
        b.parse_args(
            [
                "--tags",
                "t1",
                "t2",
                "--db-host",
                "example.com",
                "--extra",
                "7",
                "serve",
                "--port",
                "9000",
            ],
        )
        assert b.tags == ["t1", "t2"]
        assert b.db.host == "example.com"
        assert b.extra == 7
        assert b.serve.port == 9000

    def test_subclass_overrides_unannotated_argument(self):
        class A(argclass.Parser):
            tags = argclass.Argument(nargs="+", type=str)

        class B(A):
            tags = argclass.Argument(nargs="+", type=int)

        b = B()
        b.parse_args(["--tags", "1", "2"])
        assert b.tags == [1, 2]

    def test_grandchild_inherits_through_chain(self):
        class A(argclass.Parser):
            serve = SharedServe()

        class B(A):
            pass

        class C(B):
            flag: bool = False

        assert "serve" in C.__subparsers__

    def test_category_change_drops_stale_entry(self):
        class A(argclass.Parser):
            item = argclass.Argument(type=str)

        class B(A):
            item = SharedDB()  # type: ignore[assignment]

        assert "item" not in B.__arguments__
        assert "item" in B.__argument_groups__


class TestInheritedDefaultsPreserved:
    """Fix 13: plain annotated defaults survive subclassing.

    The metaclass replaces processed class attributes with ``...``
    placeholders, so rebuilding an inherited field from its annotation
    used to turn ``name: str = "x"`` into a *required* argument in
    every subclass.
    """

    def test_inherited_default_kept(self):
        class A(argclass.Parser):
            name: str = "x"

        class B(A):
            extra: int = 1

        b = B()
        b.parse_args([])
        assert b.name == "x"
        assert b.extra == 1

    def test_subclass_can_still_override_default(self):
        class A(argclass.Parser):
            name: str = "x"

        class B(A):
            name: str = "y"

        b = B()
        b.parse_args([])
        assert b.name == "y"

    def test_subclass_value_only_override(self):
        # Re-assigning without re-annotating must also re-apply.
        class A(argclass.Parser):
            name: str = "x"

        class B(A):
            name = "z"

        b = B()
        b.parse_args([])
        assert b.name == "z"

    def test_inherited_required_field_stays_required(self):
        class A(argclass.Parser):
            name: str

        class B(A):
            extra: int = 1

        with pytest.raises(SystemExit):
            B().parse_args(["--extra", "2"])
        b = B()
        b.parse_args(["--name", "n"])
        assert b.name == "n"

    def test_reannotation_without_value_resets_default(self):
        # Re-declaring the annotation (without assigning a value)
        # rebuilds the field from scratch: the base class attribute is
        # an ``...`` placeholder, so the field becomes required again.
        class A(argclass.Parser):
            name: str = "x"

        class B(A):
            name: str

        with pytest.raises(SystemExit):
            B().parse_args([])
        b = B()
        b.parse_args(["--name", "n"])
        assert b.name == "n"

    def test_reannotated_bool_reuses_inherited_argument(self):
        class A(argclass.Parser):
            flag: bool = False

        class B(A):
            flag: bool

        b = B()
        b.parse_args([])
        assert b.flag is False
        b.parse_args(["--flag"])
        assert b.flag is True

    def test_annotating_plain_base_constant(self):
        # A plain (non-callable) class attribute on the base is a
        # legitimate source for an annotated field's default.
        class A(argclass.Parser):
            LIMIT = 5

        class B(A):
            LIMIT: int

        b = B()
        b.parse_args([])
        assert b.LIMIT == 5


class TestPerInstanceState:
    """Fix 6: groups and subparsers are copied per Parser instance,
    so parsing one instance never mutates another (or the class-level
    prototypes)."""

    def test_groups_independent_across_instances(self):
        class CLI(argclass.Parser):
            db = SharedDB()

        first = CLI()
        second = CLI()
        assert first.db is not second.db

        first.parse_args(["--db-host", "from-first"])
        second.parse_args(["--db-host", "from-second"])
        assert first.db.host == "from-first"
        assert second.db.host == "from-second"

    def test_class_prototype_stays_pristine(self):
        class CLI(argclass.Parser):
            db = SharedDB()

        prototype = CLI.__argument_groups__["db"]
        cli = CLI()
        cli.parse_args(["--db-host", "parsed"])
        assert cli.db is not prototype
        with pytest.raises(AttributeError):
            prototype.host

    def test_nested_groups_independent(self):
        class Credentials(argclass.Group):
            username: str = "admin"

        class Endpoint(argclass.Group):
            credentials: Credentials = Credentials()

        class CLI(argclass.Parser):
            endpoint: Endpoint = Endpoint()

        first = CLI()
        second = CLI()
        first.parse_args(["--endpoint-credentials-username", "alice"])
        second.parse_args(["--endpoint-credentials-username", "bob"])
        assert first.endpoint.credentials.username == "alice"
        assert second.endpoint.credentials.username == "bob"

    def test_subparsers_independent_across_instances(self):
        class CLI(argclass.Parser):
            serve = SharedServe()

        first = CLI()
        second = CLI()
        assert first.serve is not second.serve

        first.parse_args(["serve", "--port", "1111"])
        second.parse_args(["serve", "--port", "2222"])
        assert first.serve.port == 1111
        assert second.serve.port == 2222
        assert first.current_subparser is first.serve
        assert second.current_subparser is second.serve

    def test_subparser_groups_independent(self):
        class Sub(argclass.Parser):
            db = SharedDB()

        class CLI(argclass.Parser):
            sub = Sub()

        first = CLI()
        second = CLI()
        first.parse_args(["sub", "--db-host", "h1"])
        second.parse_args(["sub", "--db-host", "h2"])
        assert first.sub.db.host == "h1"
        assert second.sub.db.host == "h2"

    def test_reparse_same_instance_overwrites(self):
        class CLI(argclass.Parser):
            db = SharedDB()

        cli = CLI()
        cli.parse_args(["--db-host", "one"])
        cli.parse_args(["--db-host", "two"])
        assert cli.db.host == "two"

    def test_group_options_preserved_on_copy(self):
        class CLI(argclass.Parser):
            db = SharedDB(prefix="dbx", defaults={"host": "preset"})

        cli = CLI()
        cli.parse_args([])
        assert cli.db.host == "preset"
        cli.parse_args(["--dbx-host", "cli-value"])
        assert cli.db.host == "cli-value"


class TestPathTypeUnchanged:
    """Sanity: Path defaults and types keep working end to end."""

    def test_path_argument(self):
        class P(argclass.Parser):
            target: Path = argclass.Argument(type=Path, default=Path("/tmp"))

        p = P()
        p.parse_args(["--target", "/var"])
        assert p.target == Path("/var")
