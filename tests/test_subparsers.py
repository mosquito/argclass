from functools import singledispatch
from typing import Optional, Any

import pytest

import argclass


def test_subparsers():
    class Subparser(argclass.Parser):
        foo: str = argclass.Argument()

    class Parser(argclass.Parser):
        subparser = Subparser()

    parser = Parser()
    parser.parse_args(["subparser", "--foo=bar"])
    assert parser.subparser.foo == "bar"


def test_two_subparsers():
    class Subparser(argclass.Parser):
        spam: str = argclass.Argument()

    class Parser(argclass.Parser):
        foo = Subparser()
        bar = Subparser()

    parser = Parser()
    parser.parse_args(["bar", "--spam=egg"])
    assert parser.bar.spam == "egg"

    with pytest.raises(AttributeError):
        _ = parser.foo.spam


def test_two_simple_subparsers():
    class Subparser(argclass.Parser):
        spam: str

    class Parser(argclass.Parser):
        foo = Subparser()
        bar = Subparser()

    parser = Parser()
    parser.parse_args(["foo", "--spam=egg"])
    assert parser.foo.spam == "egg"

    with pytest.raises(AttributeError):
        _ = parser.bar.spam


def test_current_subparsers():
    class AddressPortGroup(argclass.Group):
        address: str = argclass.Argument(default="127.0.0.1")
        port: int

    class CommitCommand(argclass.Parser):
        comment: str = argclass.Argument()

    class PushCommand(argclass.Parser):
        comment: str = argclass.Argument()

    class Parser(argclass.Parser):
        log_level: int = argclass.LogLevel
        endpoint = AddressPortGroup(
            title="Endpoint options",
            defaults=dict(port=8080)
        )
        commit: Optional[CommitCommand] = CommitCommand()
        push: Optional[PushCommand] = PushCommand()

    state = {}

    @singledispatch
    def handle_subparser(subparser: Any) -> None:
        raise NotImplementedError(
            f"Unexpected subparser type {subparser.__class__!r}"
        )

    @handle_subparser.register(type(None))
    def handle_none(_: None) -> None:
        Parser().print_help()
        exit(12)

    @handle_subparser.register(CommitCommand)
    def handle_commit(subparser: CommitCommand) -> None:
        state['commit'] = subparser

    @handle_subparser.register(PushCommand)
    def handle_push(subparser: PushCommand) -> None:
        state['push'] = subparser

    parser = Parser()
    parser.parse_args([])

    with pytest.raises(SystemExit) as e:
        handle_subparser(parser.current_subparser)

    assert e.value.code == 12

    parser.parse_args(['commit'])
    handle_subparser(parser.current_subparser)
    assert 'commit' in state
    assert 'push' not in state

    parser.parse_args(['push'])
    handle_subparser(parser.current_subparser)
    assert 'push' in state
