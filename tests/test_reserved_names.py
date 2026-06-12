"""Reserved internal attribute names cannot be used as arguments.

argclass stores parser state under a few attribute names
(``current_subparsers``, ``current_subparser``, ``__parent__``).
Declaring an argument/group/subparser with one of these names would
silently clobber that state, so the metaclass rejects it at class
definition time.
"""

import pytest

import argclass
from argclass.parser import RESERVED_ATTRIBUTES


def test_reserved_names_set():
    assert RESERVED_ATTRIBUTES == frozenset(
        {"current_subparsers", "current_subparser", "__parent__"}
    )


@pytest.mark.parametrize("name", sorted(RESERVED_ATTRIBUTES))
def test_reserved_annotation_rejected(name):
    with pytest.raises(argclass.ArgumentDefinitionError) as exc_info:
        type(
            "Bad",
            (argclass.Parser,),
            {"__annotations__": {name: str}, name: "x"},
        )
    message = str(exc_info.value)
    assert name in message
    assert "reserved" in message


def test_reserved_argument_value_rejected():
    with pytest.raises(argclass.ArgumentDefinitionError):

        class Bad(argclass.Parser):
            current_subparsers = argclass.Argument(  # type: ignore[assignment]
                type=int
            )


def test_reserved_subparser_value_rejected():
    class Serve(argclass.Parser):
        port: int = 8080

    with pytest.raises(argclass.ArgumentDefinitionError):

        class Bad(argclass.Parser):
            current_subparser = Serve()  # type: ignore[assignment]


def test_reserved_group_value_rejected():
    class Sub(argclass.Group):
        value: int = 1

    with pytest.raises(argclass.ArgumentDefinitionError):

        class Bad(argclass.Parser):
            current_subparsers = Sub()  # type: ignore[assignment]


def test_reserved_name_rejected_on_group():
    with pytest.raises(argclass.ArgumentDefinitionError):

        class Bad(argclass.Group):
            current_subparsers: str = "x"


def test_internal_attributes_still_work():
    """Guard must not break the framework's own use of these names."""

    class Serve(argclass.Parser):
        port: int = 8080

    class CLI(argclass.Parser):
        serve = Serve()

    # The reserved names are not exposed as CLI arguments.
    assert "current_subparsers" not in CLI.__arguments__
    assert "current_subparser" not in CLI.__arguments__

    parser = CLI()
    parser.parse_args(["serve", "--port", "9000"])

    assert parser.serve.port == 9000
    assert isinstance(parser.current_subparser, Serve)
    assert parser.current_subparsers == (parser.current_subparser,)


def test_ordinary_argument_named_similarly_is_allowed():
    """Only the exact reserved names are blocked, not lookalikes."""

    class CLI(argclass.Parser):
        subparser_count: int = 3
        parent: str = "root"

    parser = CLI()
    parser.parse_args(["--subparser-count", "5", "--parent", "leaf"])
    assert parser.subparser_count == 5
    assert parser.parent == "leaf"
