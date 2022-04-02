import logging
import os
import re
import uuid
from typing import List

import pytest

import argclass


class TestBasics:
    class Parser(argclass.Parser):
        integers: List[int] = argclass.Argument(
            "integers", type=int,
            nargs=argclass.Nargs.ONE_OR_MORE, metavar="N",
            help="an integer for the accumulator",
        )
        accumulate = argclass.Argument(
            "--sum", action=argclass.Actions.STORE_CONST, const=sum,
            default=max, help="sum the integers (default: find the max)",
        )

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
            title="HTTP host and port", prefix="api", defaults={
                "port": 80, "host": "0.0.0.0",
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

        parser.parse_args([
            "--foo=bar",
            "--api-host=127.0.0.1",
            "--api-port=8080",
            "--grpc-host=127.0.0.2",
            "--grpc-port=9000",
        ])
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
            nargs=argclass.Nargs.ZERO_OR_MORE, type=int,
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
        bar: int

    parser = Parser()
    parser.print_help()
    captured = capsys.readouterr()
    assert "--foo" in captured.out
    assert "--bar" in captured.out
    assert "--help" in captured.out
    assert "[--foo FOO]" in captured.out
    assert "[--bar BAR]" in captured.out


def test_print_log_level(capsys: pytest.CaptureFixture):
    class Parser(argclass.Parser):
        log_level: int = argclass.LogLevel

    parser = Parser()
    parser.parse_args(["--log-level", "info"])
    assert parser.log_level == logging.INFO

    parser.parse_args(["--log-level=warning"])
    assert parser.log_level == logging.WARNING
