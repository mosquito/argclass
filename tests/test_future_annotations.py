from __future__ import annotations

from enum import IntEnum
from typing import Literal, Optional

import argclass


class Color(IntEnum):
    RED = 1
    GREEN = 2
    BLUE = 3


class TestFutureAnnotations:
    """Test that `from __future__ import annotations` works correctly."""

    def test_basic_types(self):
        class CLI(argclass.Parser):
            host: str = "localhost"
            port: int = 8080
            verbose: bool = False

        parser = CLI()
        parser.parse_args(
            ["--host", "example.com", "--port", "9090", "--verbose"],
        )
        assert parser.host == "example.com"
        assert parser.port == 9090
        assert parser.verbose is True

    def test_optional(self):
        class CLI(argclass.Parser):
            name: Optional[str] = None

        parser = CLI()
        parser.parse_args([])
        assert parser.name is None
        parser.parse_args(["--name", "test"])
        assert parser.name == "test"

    def test_literal(self):
        class CLI(argclass.Parser):
            mode: Literal["fast", "slow"] = "fast"

        parser = CLI()
        parser.parse_args(["--mode", "slow"])
        assert parser.mode == "slow"

    def test_list(self):
        class CLI(argclass.Parser):
            tags: list[str] = argclass.Argument(
                nargs=argclass.Nargs.ONE_OR_MORE,
            )

        parser = CLI()
        parser.parse_args(["--tags", "a", "b", "c"])
        assert parser.tags == ["a", "b", "c"]

    def test_enum(self):
        class CLI(argclass.Parser):
            color: Color = Color.RED

        parser = CLI()
        parser.parse_args(["--color", "GREEN"])
        assert parser.color == Color.GREEN

    def test_group(self):
        class DB(argclass.Group):
            host: str = "localhost"
            port: int = 5432

        class CLI(argclass.Parser):
            db: DB = DB(title="Database")

        parser = CLI()
        parser.parse_args(
            ["--db-host", "dbhost", "--db-port", "3306"],
        )
        assert parser.db.host == "dbhost"
        assert parser.db.port == 3306

    def test_subparsers(self):
        class Serve(argclass.Parser):
            port: int = 8080

        class CLI(argclass.Parser):
            serve = Serve()

        parser = CLI()
        parser.parse_args(["serve", "--port", "9090"])

    def test_secret(self):
        class CLI(argclass.Parser):
            api_key: str = argclass.Secret()

        parser = CLI()
        parser.parse_args(["--api-key", "my-secret"])
        assert parser.api_key == "my-secret"
