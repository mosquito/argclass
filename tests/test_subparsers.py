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
