import json
import logging
import os
import re
import uuid
from enum import IntEnum
from typing import FrozenSet, List, Literal, Optional, Set, Tuple
from unittest.mock import patch

import pytest

import argclass


def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text."""
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


class TestBasics:
    class Parser(argclass.Parser):
        integers: List[int] = argclass.Argument(
            "integers",
            type=int,
            nargs=argclass.Nargs.ONE_OR_MORE,
            metavar="N",
            help="an integer for the accumulator",
        )
        accumulate = argclass.Argument(
            "--sum",
            action=argclass.Actions.STORE_CONST,
            const=sum,
            default=max,
            help="sum the integers (default: find the max)",
        )
        secret = argclass.Secret()

    def test_simple(self):
        parser = self.Parser()
        parser.parse_args(["1", "2", "3"])

        assert parser.integers
        assert parser.integers == [1, 2, 3]


class HostPortGroup(argclass.Group):
    host: str
    port: int


class TestFoo:
    class Parser(argclass.Parser):
        foo: str = argclass.Argument(help="foo")
        http: HostPortGroup = HostPortGroup(
            title="HTTP host and port",
            prefix="api",
            defaults={
                "port": 80,
                "host": "0.0.0.0",
            },
        )
        grpc: HostPortGroup = HostPortGroup(
            title="GRPC host and port",
            defaults={"port": 6000, "host": "::"},
        )

    def test_simple(self):
        parser = self.Parser()
        parser.parse_args(["--foo", "bar"])
        assert parser.foo == "bar"

        parser.parse_args(["--foo=bar"])
        assert parser.foo == "bar"

    def test_group(self):
        parser = self.Parser()
        parser.parse_args(["--foo", "bar"])
        assert parser.foo == "bar"

        parser.parse_args(
            [
                "--foo=bar",
                "--api-host=127.0.0.1",
                "--api-port=8080",
                "--grpc-host=127.0.0.2",
                "--grpc-port=9000",
            ]
        )
        assert parser.foo == "bar"
        assert parser.http.host == "127.0.0.1"
        assert parser.http.port == 8080
        assert parser.grpc.host == "127.0.0.2"
        assert parser.grpc.port == 9000

    def test_group_defaults(self):
        parser = self.Parser()
        parser.parse_args(["--foo=bar"])
        assert parser.foo == "bar"
        assert parser.http.host == "0.0.0.0"
        assert parser.http.port == 80
        assert parser.grpc.host == "::"
        assert parser.grpc.port == 6000

    def test_parser_repr(self):
        parser = self.Parser()
        r = repr(parser)
        assert r == "<Parser: 1 arguments, 2 groups, 0 subparsers>"

    def test_access_to_not_parsed_attrs(self):
        parser = self.Parser()
        with pytest.raises(AttributeError):
            _ = parser.foo

    def test_environment(self, request: pytest.FixtureRequest):
        prefix = re.sub(r"\d+", "", uuid.uuid4().hex + uuid.uuid4().hex).upper()
        expected = uuid.uuid4().hex
        os.environ[f"{prefix}_FOO"] = expected
        request.addfinalizer(lambda: os.environ.pop(f"{prefix}_FOO"))

        parser = self.Parser(auto_env_var_prefix=f"{prefix}_")
        parser.parse_args([])
        assert parser.foo == expected


def test_env_var(request: pytest.FixtureRequest):
    env_var = re.sub(r"\d+", "", uuid.uuid4().hex + uuid.uuid4().hex).upper()

    class Parser(argclass.Parser):
        foo: str = argclass.Argument(env_var=env_var)

    expected = uuid.uuid4().hex
    os.environ[env_var] = expected
    request.addfinalizer(lambda: os.environ.pop(env_var))

    parser = Parser()
    parser.parse_args([])
    assert parser.foo == expected


def test_nargs():
    class Parser(argclass.Parser):
        foo: List[int] = argclass.Argument(
            nargs=argclass.Nargs.ZERO_OR_MORE,
            type=int,
        )
        bar: int = argclass.Argument(nargs="*")
        spam: int = argclass.Argument(nargs=1)

    parser = Parser()
    parser.parse_args(["--foo", "1", "2", "--bar=3", "--spam=4"])
    assert parser.foo == [1, 2]
    assert parser.bar == [3]
    assert parser.spam == [4]


def test_group_aliases():
    class Group(argclass.Group):
        foo: str = argclass.Argument("-F")

    class Parser(argclass.Parser):
        group = Group()

    parser = Parser()
    parser.parse_args(["-F", "egg"])
    assert parser.group.foo == "egg"


def test_group_empty_prefix():
    """Test that prefix='' allows arguments without group prefix (issue #26)."""

    class AddressPort(argclass.Group):
        address: str
        port: int

    class Parser(argclass.Parser):
        api: AddressPort = AddressPort(
            prefix="",
            defaults=dict(address="localhost", port=80),
        )
        telemetry: AddressPort = AddressPort(
            defaults=dict(address="0.0.0.0", port=8082),
        )

    parser = Parser()

    # With prefix='', we get --address and --port (no prefix)
    # telemetry uses default prefix, so --telemetry-address and --telemetry-port
    parser.parse_args(
        [
            "--address",
            "192.168.1.1",
            "--port",
            "9000",
            "--telemetry-address",
            "10.0.0.1",
            "--telemetry-port",
            "9999",
        ]
    )
    assert parser.api.address == "192.168.1.1"
    assert parser.api.port == 9000
    assert parser.telemetry.address == "10.0.0.1"
    assert parser.telemetry.port == 9999


def test_group_empty_prefix_with_defaults():
    """Test empty prefix with default values (issue #27)."""

    class LearningOptions(argclass.Group):
        batch_size: int = 256
        learning_rate: float = 1e-1

    class Parser(argclass.Parser):
        learning_opts = LearningOptions(title="learning options", prefix="")

    parser = Parser()

    # Should use --batch-size, not --learning-opts-batch-size
    parser.parse_args(["--batch-size", "512", "--learning-rate", "0.01"])
    assert parser.learning_opts.batch_size == 512
    assert parser.learning_opts.learning_rate == 0.01

    # Test defaults work
    parser2 = Parser()
    parser2.parse_args([])
    assert parser2.learning_opts.batch_size == 256
    assert parser2.learning_opts.learning_rate == 0.1


def test_short_parser_definition():
    class Parser(argclass.Parser):
        foo: str
        bar: int

    parser = Parser()
    parser.parse_args(["--foo=spam", "--bar=1"])
    assert parser.foo == "spam"
    assert parser.bar == 1


def test_print_help(capsys: pytest.CaptureFixture):
    class Parser(argclass.Parser):
        foo: str
        bar: int = 0

    parser = Parser()
    parser.print_help()
    captured = capsys.readouterr()
    output = strip_ansi(captured.out)
    assert "--foo" in output
    assert "--bar" in output
    assert "--help" in output
    assert "--foo FOO" in output
    assert "[--bar BAR]" in output


def test_print_log_level(capsys: pytest.CaptureFixture):
    class Parser(argclass.Parser):
        log_level: int = argclass.LogLevel

    parser = Parser()
    parser.parse_args(["--log-level", "info"])
    assert parser.log_level == logging.INFO

    parser.parse_args(["--log-level=warning"])
    assert parser.log_level == logging.WARNING


def test_optional_type():
    class Parser(argclass.Parser):
        flag: bool
        optional: Optional[bool]

    parser = Parser()
    parser.parse_args([])
    assert parser.optional is None
    assert not parser.flag

    parser.parse_args(["--flag"])
    assert parser.flag

    for variant in ("yes", "Y", "yeS", "enable", "ENABLED", "1"):
        parser.parse_args([f"--optional={variant}"])
        assert parser.optional is True

    for variant in ("no", "crap", "false", "disabled", "MY_HANDS_TYPING_WORDS"):
        parser.parse_args([f"--optional={variant}"])
        assert parser.optional is False


def test_pep604_union_type():
    """Test PEP 604 union types (float | None syntax)."""

    class Parser(argclass.Parser):
        param: float | None
        count: int | None = None
        name: str | None = "default"

    parser = Parser()

    # Test with no arguments - optional fields should use defaults
    parser.parse_args([])
    assert parser.param is None
    assert parser.count is None
    assert parser.name == "default"

    # Test with values provided
    parser.parse_args(["--param", "3.14", "--count", "42", "--name", "test"])
    assert parser.param == 3.14
    assert parser.count == 42
    assert parser.name == "test"


def test_argument_defaults():
    class Parser(argclass.Parser):
        debug: bool = False
        confused_default: bool = True
        pool_size: int = 4
        forks: int = 2

    parser = Parser()

    parser.parse_args([])
    assert parser.debug is False
    assert parser.confused_default is True
    assert parser.pool_size == 4
    assert parser.forks == 2

    parser.parse_args(
        [
            "--debug",
            "--forks=8",
            "--pool-size=2",
            "--confused-default",
        ]
    )
    assert parser.debug is True
    assert parser.confused_default is False
    assert parser.pool_size == 2
    assert parser.forks == 8


def test_inheritance():
    class AddressPort(argclass.Group):
        address: str
        port: int

    class Parser(argclass.Parser, AddressPort):
        pass

    parser = Parser()
    parser.parse_args(["--address=0.0.0.0", "--port=9876"])
    assert parser.address == "0.0.0.0"
    assert parser.port == 9876


def test_inherited_required_arguments():
    """Test that required arguments stay required when inherited (issue #21)."""

    class BaseParser(argclass.Parser):
        argument1: str  # should be required
        argument2: str = argclass.Argument(required=True)

    class SuperParser(BaseParser):
        argument3: str  # should be required

    # All three should be required
    parser = SuperParser()
    with pytest.raises(SystemExit):
        parser.parse_args([])

    # Providing all arguments should work
    parser.parse_args(
        [
            "--argument1",
            "a",
            "--argument2",
            "b",
            "--argument3",
            "c",
        ]
    )
    assert parser.argument1 == "a"
    assert parser.argument2 == "b"
    assert parser.argument3 == "c"


def test_deep_inheritance():
    """Test that multi-level inheritance (3+ levels) works correctly."""

    class Level1(argclass.Parser):
        arg1: str
        debug: bool = False

    class Level2(Level1):
        arg2: str

    class Level3(Level2):
        arg3: str

    class Level4(Level3):
        arg4: str

    # All arguments from all levels should be available
    assert "arg1" in Level4.__arguments__
    assert "arg2" in Level4.__arguments__
    assert "arg3" in Level4.__arguments__
    assert "arg4" in Level4.__arguments__
    assert "debug" in Level4.__arguments__

    parser = Level4()
    parser.parse_args(
        [
            "--arg1",
            "a",
            "--arg2",
            "b",
            "--arg3",
            "c",
            "--arg4",
            "d",
            "--debug",
        ]
    )
    assert parser.arg1 == "a"
    assert parser.arg2 == "b"
    assert parser.arg3 == "c"
    assert parser.arg4 == "d"
    assert parser.debug is True


def test_config_for_required(tmp_path):
    class Parser(argclass.Parser):
        required: int = argclass.Argument(required=True)

    config_path = tmp_path / "config.ini"

    with open(config_path, "w") as fp:
        fp.write("[DEFAULT]\n")
        fp.write("required = 10\n")
        fp.write("\n")

    parser = Parser(config_files=[config_path])
    parser.parse_args([])

    assert parser.required == 10

    parser = Parser(config_files=[])

    with pytest.raises(SystemExit):
        parser.parse_args([])


def test_minimal_optional(tmp_path):
    class Parser(argclass.Parser):
        optional: Optional[int]

    parser = Parser()
    parser.parse_args([])

    assert parser.optional is None

    parser.parse_args(["--optional=10"])

    assert parser.optional == 10


def test_optional_is_not_required(tmp_path):
    class Parser(argclass.Parser):
        optional: Optional[int] = argclass.Argument(required=False)

    parser = Parser()

    parser.parse_args([])
    assert parser.optional is None

    parser.parse_args(["--optional=20"])
    assert parser.optional == 20


def test_minimal_required(tmp_path):
    class Parser(argclass.Parser):
        required: int

    parser = Parser()

    with pytest.raises(SystemExit):
        parser.parse_args([])

    parser.parse_args(["--required=20"])

    assert parser.required == 20


def test_log_group():
    class LogGroup(argclass.Group):
        level: int = argclass.LogLevel
        format = argclass.Argument(
            choices=("json", "stream"),
            default="stream",
        )

    class Parser(argclass.Parser):
        log = LogGroup()

    parser = Parser()
    parser.parse_args([])

    assert parser.log.level == logging.INFO
    assert parser.log.format == "stream"

    parser.parse_args(["--log-level=debug", "--log-format=json"])

    assert parser.log.level == logging.DEBUG
    assert parser.log.format == "json"


def test_log_group_defaults():
    class LogGroup(argclass.Group):
        level: int = argclass.LogLevel
        format: str = argclass.Argument(
            choices=("json", "stream"),
        )

    class Parser(argclass.Parser):
        log = LogGroup(defaults=dict(format="json", level="error"))

    parser = Parser()
    parser.parse_args([])

    assert parser.log.level == logging.ERROR
    assert parser.log.format == "json"


def test_environment_required():
    class Parser(argclass.Parser):
        required: int

    parser = Parser(auto_env_var_prefix="TEST_")

    os.environ["TEST_REQUIRED"] = "100"

    parser.parse_args([])
    assert parser.required == 100

    os.environ.pop("TEST_REQUIRED")

    with pytest.raises(SystemExit):
        parser.parse_args([])


def test_nargs_and_converter():
    class Parser(argclass.Parser):
        args_set: FrozenSet[int] = argclass.Argument(
            type=int,
            nargs="+",
            converter=frozenset,
        )

    parser = Parser()
    parser.parse_args(["--args-set", "1", "2", "3", "4", "5"])
    assert isinstance(parser.args_set, frozenset)
    assert parser.args_set == frozenset([1, 2, 3, 4, 5])


def test_nargs_and_converter_not_required():
    class Parser(argclass.Parser):
        args_set: FrozenSet[int] = argclass.Argument(
            type=int,
            nargs="*",
            converter=frozenset,
        )

    parser = Parser()
    parser.parse_args([])
    assert isinstance(parser.args_set, frozenset)
    assert parser.args_set == frozenset([])

    parser.parse_args(["--args-set", "1", "2", "3", "4", "5"])
    assert isinstance(parser.args_set, frozenset)
    assert parser.args_set == frozenset([1, 2, 3, 4, 5])


def test_nargs_1():
    class Parser(argclass.Parser):
        args_set: FrozenSet[int] = argclass.Argument(
            type=int,
            nargs=1,
            converter=frozenset,
        )

    parser = Parser()
    parser.parse_args([])
    assert isinstance(parser.args_set, frozenset)
    assert parser.args_set == frozenset([])

    parser.parse_args(["--args-set", "1"])
    assert isinstance(parser.args_set, frozenset)
    assert parser.args_set == frozenset([1])


def test_nargs_env_var():
    class Parser(argclass.Parser):
        nargs: FrozenSet[int] = argclass.Argument(
            type=int,
            nargs="*",
            converter=frozenset,
            env_var="NARGS",
        )

    os.environ["NARGS"] = "[1, 2, 3]"
    try:
        parser = Parser()
        parser.parse_args([])
    finally:
        del os.environ["NARGS"]

    assert parser.nargs == frozenset({1, 2, 3})


def test_nargs_env_var_str():
    class Parser(argclass.Parser):
        nargs: FrozenSet[int] = argclass.Argument(
            type=str,
            nargs="*",
            converter=frozenset,
            env_var="NARGS",
        )

    os.environ["NARGS"] = '["a", "b", "c"]'
    try:
        parser = Parser()
        parser.parse_args([])
    finally:
        del os.environ["NARGS"]

    assert parser.nargs == frozenset({"a", "b", "c"})


def test_nargs_config_list(tmp_path):
    class Parser(argclass.Parser):
        nargs: FrozenSet[int] = argclass.Argument(
            type=int,
            nargs="*",
            converter=frozenset,
            env_var="NARGS",
        )

    conf_file = tmp_path / "config.ini"

    with open(conf_file, "w") as fp:
        fp.write("[DEFAULT]\n")
        fp.write("nargs = [1, 2, 3, 4]\n")

    parser = Parser(config_files=[conf_file])
    parser.parse_args([])

    assert parser.nargs == frozenset({1, 2, 3, 4})


def test_nargs_config_set(tmp_path):
    class Parser(argclass.Parser):
        nargs: FrozenSet[int] = argclass.Argument(
            type=int,
            nargs="*",
            converter=frozenset,
            env_var="NARGS",
        )

    conf_file = tmp_path / "config.ini"

    with open(conf_file, "w") as fp:
        fp.write("[DEFAULT]\n")
        fp.write("nargs = {1, 2, 3, 4}\n")

    parser = Parser(config_files=[conf_file])
    parser.parse_args([])

    assert parser.nargs == frozenset({1, 2, 3, 4})


def test_secret_argument(tmp_path, capsys):
    class Parser(argclass.Parser):
        token: str = argclass.Argument(secret=True, default="TOP_SECRET")
        pubkey: str = argclass.Argument(secret=False, default="NO_SECRET")
        secret: str = argclass.Secret(default="FORBIDDEN")

    parser = Parser()
    parser.print_help()

    captured = capsys.readouterr()
    assert "TOP_SECRET" not in captured.out
    assert "NO_SECRET" in captured.out
    assert "FORBIDDEN" not in captured.out


def test_sanitize_env():
    class Parser(argclass.Parser):
        secret: str = argclass.Secret(default="SECRET")

    parser = Parser(auto_env_var_prefix="TEST_")

    with patch("os.environ", new={}):
        os.environ["TEST_SECRET"] = "foo"

        assert os.environ["TEST_SECRET"] == "foo"

        parser.parse_args([])
        parser.sanitize_env()

        assert "TEST_SECRET" not in dict(os.environ)


def test_sanitize_secrets_on_parse():
    """Test sanitize_secrets=True removes only secret env vars."""

    class Parser(argclass.Parser):
        secret: str = argclass.Secret(default="SECRET")
        public: str = argclass.Argument(default="PUBLIC")

    parser = Parser(auto_env_var_prefix="TEST_")

    with patch("os.environ", new={}):
        os.environ["TEST_SECRET"] = "secret_value"
        os.environ["TEST_PUBLIC"] = "public_value"

        assert os.environ["TEST_SECRET"] == "secret_value"
        assert os.environ["TEST_PUBLIC"] == "public_value"

        parser.parse_args([], sanitize_secrets=True)

        # Secret env var should be removed
        assert "TEST_SECRET" not in dict(os.environ)
        # Non-secret env var should remain
        assert os.environ["TEST_PUBLIC"] == "public_value"

        # Values should still be parsed correctly
        assert str.__str__(parser.secret) == "secret_value"
        assert parser.public == "public_value"


def test_sanitize_secrets_false_by_default():
    """Test that sanitize_secrets=False (default) keeps all env vars."""

    class Parser(argclass.Parser):
        secret: str = argclass.Secret(default="SECRET")

    parser = Parser(auto_env_var_prefix="TEST_")

    with patch("os.environ", new={}):
        os.environ["TEST_SECRET"] = "secret_value"

        parser.parse_args([])

        # Secret env var should NOT be removed (sanitize_secrets=False)
        assert os.environ["TEST_SECRET"] == "secret_value"


def test_sanitize_env_only_secrets():
    """Test sanitize_env(only_secrets=True) removes only secret env vars."""

    class Parser(argclass.Parser):
        secret: str = argclass.Secret(default="SECRET")
        public: str = argclass.Argument(default="PUBLIC")

    parser = Parser(auto_env_var_prefix="TEST_")

    with patch("os.environ", new={}):
        os.environ["TEST_SECRET"] = "secret_value"
        os.environ["TEST_PUBLIC"] = "public_value"

        parser.parse_args([])

        # Both env vars should exist before sanitize_env
        assert os.environ["TEST_SECRET"] == "secret_value"
        assert os.environ["TEST_PUBLIC"] == "public_value"

        parser.sanitize_env(only_secrets=True)

        # Secret env var should be removed
        assert "TEST_SECRET" not in dict(os.environ)
        # Non-secret env var should remain
        assert os.environ["TEST_PUBLIC"] == "public_value"


def test_sanitize_env_all():
    """Test sanitize_env() (default) removes all env vars."""

    class Parser(argclass.Parser):
        secret: str = argclass.Secret(default="SECRET")
        public: str = argclass.Argument(default="PUBLIC")

    parser = Parser(auto_env_var_prefix="TEST_")

    with patch("os.environ", new={}):
        os.environ["TEST_SECRET"] = "secret_value"
        os.environ["TEST_PUBLIC"] = "public_value"

        parser.parse_args([])

        parser.sanitize_env()

        # Both env vars should be removed
        assert "TEST_SECRET" not in dict(os.environ)
        assert "TEST_PUBLIC" not in dict(os.environ)


def test_enum():
    class Options(IntEnum):
        ONE = 1
        TWO = 2
        THREE = 3
        ZERO = 0

    class Parser(argclass.Parser):
        option: Options = argclass.EnumArgument(Options, default=Options.ZERO)

    parser = Parser()

    parser.parse_args([])
    assert parser.option is Options.ZERO

    parser.parse_args(["--option=ONE"])
    assert parser.option is Options.ONE

    parser.parse_args(["--option=TWO"])
    assert parser.option is Options.TWO

    with pytest.raises(SystemExit):
        parser.parse_args(["--option=3"])

    class Parser(argclass.Parser):
        option: Options

    parser = Parser()

    parser.parse_args(["--option=ONE"])
    assert parser.option is Options.ONE

    parser.parse_args(["--option=TWO"])
    assert parser.option is Options.TWO

    with pytest.raises(SystemExit):
        parser.parse_args(["--option=3"])


def test_group_required_inheritance():
    class BaseGroup(argclass.Group):
        bar: str = argclass.Argument(required=True)

    class SubGroup(BaseGroup):
        pass

    class Parser(argclass.Parser):
        group = SubGroup()

    parser = Parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])

    class ImplicitBaseGroup(argclass.Group):
        bar: str
        foo: int

    class ImplicitSubGroup(ImplicitBaseGroup):
        zoo: str

    class Parser2(argclass.Parser):
        group = ImplicitSubGroup()

    parser = Parser2()
    with pytest.raises(SystemExit):
        parser.parse_args([])


def test_json_action(tmp_path):
    class Parser(argclass.Parser):
        config = argclass.Config(
            required=True,
            config_class=argclass.JSONConfig,
        )

    with open(tmp_path / "config.json", "w") as fp:
        json.dump({"foo": "bar"}, fp)

    parser = Parser()
    parser.parse_args(["--config", str(tmp_path / "config.json")])

    assert parser.config["foo"] == "bar"


# ============================================================================
# Container Type Annotation Tests (PEP 585 and typing module)
# ============================================================================


def test_list_str_lowercase():
    """Test list[str] (PEP 585 style)."""

    class Parser(argclass.Parser):
        names: list[str]

    parser = Parser()
    parser.parse_args(["--names", "alice", "bob", "charlie"])
    assert parser.names == ["alice", "bob", "charlie"]
    assert isinstance(parser.names, list)


def test_list_str_typing():
    """Test List[str] (typing module style)."""

    class Parser(argclass.Parser):
        names: List[str]

    parser = Parser()
    parser.parse_args(["--names", "alice", "bob", "charlie"])
    assert parser.names == ["alice", "bob", "charlie"]
    assert isinstance(parser.names, list)


def test_list_int_lowercase():
    """Test list[int] with automatic type conversion."""

    class Parser(argclass.Parser):
        numbers: list[int]

    parser = Parser()
    parser.parse_args(["--numbers", "1", "2", "3"])
    assert parser.numbers == [1, 2, 3]
    assert all(isinstance(n, int) for n in parser.numbers)


def test_list_int_typing():
    """Test List[int] (typing module style)."""

    class Parser(argclass.Parser):
        numbers: List[int]

    parser = Parser()
    parser.parse_args(["--numbers", "1", "2", "3"])
    assert parser.numbers == [1, 2, 3]


def test_list_float_lowercase():
    """Test list[float] with automatic type conversion."""

    class Parser(argclass.Parser):
        values: list[float]

    parser = Parser()
    parser.parse_args(["--values", "1.5", "2.7", "3.14"])
    assert parser.values == [1.5, 2.7, 3.14]


def test_set_str_lowercase():
    """Test set[str] (PEP 585 style)."""

    class Parser(argclass.Parser):
        tags: set[str]

    parser = Parser()
    parser.parse_args(["--tags", "alpha", "beta", "alpha"])
    assert parser.tags == {"alpha", "beta"}
    assert isinstance(parser.tags, set)


def test_set_str_typing():
    """Test Set[str] (typing module style)."""

    class Parser(argclass.Parser):
        tags: Set[str]

    parser = Parser()
    parser.parse_args(["--tags", "alpha", "beta", "alpha"])
    assert parser.tags == {"alpha", "beta"}
    assert isinstance(parser.tags, set)


def test_set_int_lowercase():
    """Test set[int] with automatic type conversion and deduplication."""

    class Parser(argclass.Parser):
        nums: set[int]

    parser = Parser()
    parser.parse_args(["--nums", "1", "2", "2", "3", "1"])
    assert parser.nums == {1, 2, 3}


def test_frozenset_str_lowercase():
    """Test frozenset[str] (PEP 585 style)."""

    class Parser(argclass.Parser):
        immutable_tags: frozenset[str]

    parser = Parser()
    parser.parse_args(["--immutable-tags", "x", "y", "x"])
    assert parser.immutable_tags == frozenset({"x", "y"})
    assert isinstance(parser.immutable_tags, frozenset)


def test_frozenset_str_typing():
    """Test FrozenSet[str] (typing module style)."""

    class Parser(argclass.Parser):
        immutable_tags: FrozenSet[str]

    parser = Parser()
    parser.parse_args(["--immutable-tags", "x", "y", "x"])
    assert parser.immutable_tags == frozenset({"x", "y"})


def test_optional_list_str():
    """Test Optional[list[str]] - should be optional with nargs=*."""

    class Parser(argclass.Parser):
        files: Optional[list[str]]

    parser = Parser()
    # Without argument - should be None or empty list
    parser.parse_args([])
    assert parser.files is None or parser.files == []

    # With argument
    parser.parse_args(["--files", "a.txt", "b.txt"])
    assert parser.files == ["a.txt", "b.txt"]


def test_optional_list_int():
    """Test Optional[List[int]] - typing style."""

    class Parser(argclass.Parser):
        ids: Optional[List[int]]

    parser = Parser()
    parser.parse_args([])
    assert parser.ids is None or parser.ids == []

    parser.parse_args(["--ids", "100", "200"])
    assert parser.ids == [100, 200]


def test_list_required_without_args():
    """Test that required list[str] fails without arguments."""

    class Parser(argclass.Parser):
        files: list[str]  # Required by default

    parser = Parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])


def test_list_with_default():
    """Test list with default value."""

    class Parser(argclass.Parser):
        tags: list[str] = ["default"]

    parser = Parser()
    parser.parse_args([])
    assert parser.tags == ["default"]

    parser.parse_args(["--tags", "new"])
    assert parser.tags == ["new"]


def test_tuple_str_lowercase():
    """Test tuple[str] (PEP 585 style) - treated as variable length."""

    class Parser(argclass.Parser):
        args: tuple[str]

    parser = Parser()
    parser.parse_args(["--args", "a", "b", "c"])
    assert parser.args == ("a", "b", "c")
    assert isinstance(parser.args, tuple)


def test_tuple_int_typing():
    """Test Tuple[int] (typing module style)."""

    class Parser(argclass.Parser):
        coords: Tuple[int]

    parser = Parser()
    parser.parse_args(["--coords", "10", "20", "30"])
    assert parser.coords == (10, 20, 30)


def test_mixed_container_types():
    """Test multiple different container types in one parser."""

    class Parser(argclass.Parser):
        names: list[str]
        unique_ids: set[int]
        frozen_tags: frozenset[str]

    parser = Parser()
    parser.parse_args(
        [
            "--names",
            "alice",
            "bob",
            "--unique-ids",
            "1",
            "2",
            "2",
            "3",
            "--frozen-tags",
            "a",
            "b",
            "a",
        ]
    )
    assert parser.names == ["alice", "bob"]
    assert parser.unique_ids == {1, 2, 3}
    assert parser.frozen_tags == frozenset({"a", "b"})


def test_container_with_explicit_argument():
    """Test that explicit Argument still works with container types."""

    class Parser(argclass.Parser):
        items: list[str] = argclass.Argument(
            nargs="+",
            help="List of items",
            metavar="ITEM",
        )

    parser = Parser()
    parser.parse_args(["--items", "x", "y", "z"])
    assert parser.items == ["x", "y", "z"]


def test_list_in_group():
    """Test list type in argument group."""

    class HostsGroup(argclass.Group):
        addresses: list[str]

    class Parser(argclass.Parser):
        hosts = HostsGroup()

    parser = Parser()
    parser.parse_args(["--hosts-addresses", "192.168.1.1", "192.168.1.2"])
    assert parser.hosts.addresses == ["192.168.1.1", "192.168.1.2"]


def test_set_in_group():
    """Test set type in argument group."""

    class TagsGroup(argclass.Group):
        values: set[str]

    class Parser(argclass.Parser):
        tags = TagsGroup()

    parser = Parser()
    parser.parse_args(["--tags-values", "a", "b", "a"])
    assert parser.tags.values == {"a", "b"}


def test_set_int_with_explicit_type_and_converter():
    """Test set[int] using explicit type=int and converter=set.

    This demonstrates using Argument() with:
    - type=int: converts each CLI string to int
    - converter=set: converts the resulting list to a set
    - nargs="+": accepts one or more values
    """

    class Parser(argclass.Parser):
        numbers: set[int] = argclass.Argument(
            type=int,
            converter=set,
            nargs="+",
        )

    parser = Parser()
    parser.parse_args(["--numbers", "1", "2", "3", "2", "1"])

    assert isinstance(parser.numbers, set)
    assert parser.numbers == {1, 2, 3}
    # Verify duplicates are removed
    assert len(parser.numbers) == 3


def test_set_int_optional_with_explicit_type_and_converter():
    """Test Optional[set[int]] using explicit type and converter."""

    class Parser(argclass.Parser):
        numbers: Optional[set[int]] = argclass.Argument(
            type=int,
            converter=set,
            nargs="*",
        )

    parser = Parser()

    # Without argument - should get empty set
    parser.parse_args([])
    assert parser.numbers == set()

    # With argument - should get set of ints
    parser.parse_args(["--numbers", "10", "20", "10"])
    assert parser.numbers == {10, 20}


def test_set_int_with_single_converter_function():
    """Test set[int] using a single converter function.

    Alternative approach: use one converter that does both
    int conversion and set creation.
    """

    class Parser(argclass.Parser):
        numbers: set[int] = argclass.Argument(
            converter=lambda vals: set(map(int, vals)),
            nargs="+",
        )

    parser = Parser()
    parser.parse_args(["--numbers", "1", "2", "3", "2", "1"])

    assert isinstance(parser.numbers, set)
    assert parser.numbers == {1, 2, 3}


# ============================================================================
# Literal Type Tests
# ============================================================================


def test_literal_str():
    """Test Literal["a", "b", "c"] with string choices."""

    class Parser(argclass.Parser):
        mode: Literal["debug", "release", "test"]

    parser = Parser()
    parser.parse_args(["--mode", "debug"])
    assert parser.mode == "debug"

    parser.parse_args(["--mode", "release"])
    assert parser.mode == "release"

    parser.parse_args(["--mode", "test"])
    assert parser.mode == "test"


def test_literal_str_invalid_choice():
    """Test that invalid choice raises error."""

    class Parser(argclass.Parser):
        mode: Literal["debug", "release"]

    parser = Parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--mode", "invalid"])


def test_literal_int():
    """Test Literal[1, 2, 3] with int choices."""

    class Parser(argclass.Parser):
        level: Literal[1, 2, 3]

    parser = Parser()
    parser.parse_args(["--level", "1"])
    assert parser.level == 1

    parser.parse_args(["--level", "2"])
    assert parser.level == 2


def test_literal_with_default():
    """Test Literal type with default value."""

    class Parser(argclass.Parser):
        mode: Literal["debug", "release"] = "debug"

    parser = Parser()
    parser.parse_args([])
    assert parser.mode == "debug"

    parser.parse_args(["--mode", "release"])
    assert parser.mode == "release"


def test_literal_optional():
    """Test Optional[Literal[...]] - should be optional."""

    class Parser(argclass.Parser):
        mode: Optional[Literal["a", "b", "c"]]

    parser = Parser()
    parser.parse_args([])
    assert parser.mode is None

    parser.parse_args(["--mode", "a"])
    assert parser.mode == "a"


def test_literal_in_group():
    """Test Literal type in argument group."""

    class StorageGroup(argclass.Group):
        type: Literal["s3", "posix"]
        path: str = "/data"

    class Parser(argclass.Parser):
        storage = StorageGroup()

    parser = Parser()
    parser.parse_args(["--storage-type", "s3"])
    assert parser.storage.type == "s3"

    parser.parse_args(["--storage-type", "posix"])
    assert parser.storage.type == "posix"


def test_literal_with_explicit_argument():
    """Test Literal type with explicit Argument."""

    class Parser(argclass.Parser):
        env: Literal["dev", "staging", "prod"] = argclass.Argument(
            help="Deployment environment",
        )

    parser = Parser()
    parser.parse_args(["--env", "prod"])
    assert parser.env == "prod"


def test_literal_with_explicit_choices_override():
    """Test that explicit choices in Argument are preserved."""

    class Parser(argclass.Parser):
        # Explicit choices should not be overridden by Literal
        mode: Literal["a", "b"] = argclass.Argument(
            choices=("x", "y", "z"),
        )

    parser = Parser()
    parser.parse_args(["--mode", "x"])
    assert parser.mode == "x"

    # Original literal values should not work since choices were overridden
    with pytest.raises(SystemExit):
        parser.parse_args(["--mode", "a"])
