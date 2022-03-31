import os
import re
import uuid
from typing import List

import pytest

import argclass


class TestBasics:
    class Parser(argclass.Parser):
        integers: List[int] = argclass.Argument(
            aliases=["integers"], type=int,
            nargs=argclass.Nargs.ONE_OR_MORE, metavar="N",
            help="an integer for the accumulator",
        )
        accumulate = argclass.Argument(
            aliases=["--sum"], action=argclass.Actions.STORE_CONST, const=sum,
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

    def test_environment(self):
        prefix = re.sub(r"\d+", "", uuid.uuid4().hex + uuid.uuid4().hex).upper()
        expected = uuid.uuid4().hex
        os.environ[f"{prefix}_FOO"] = expected

        parser = self.Parser(auto_env_var_prefix=f"{prefix}_")
        parser.parse_args([])
        assert parser.foo == expected
