argclass
========

A wrapper around the standard ``argparse`` module that allows you to describe
argument parsers declaratively.

By default, the ``argparse`` module suggests creating parsers imperative,
which is not convenient from the point of view of type checking and
access to attributes, of course, IDE autocompletion and type hints not
applicable in this case.

This module allows you to declare command-line parsers with classes.

.. code-block:: python
    :name: test_example

    import argclass


    class Parser(argclass.Parser):
        integers: list[int] = argclass.Argument(
            aliases=["integers"], converter=int,
            nargs=argclass.Nargs.ONE_OR_MORE, metavar="N",
            help='an integer for the accumulator'
        )
        accumulate = argclass.Argument(
            aliases=["--sum"], action=argclass.Action.STORE_CONST, const=sum,
            default=max, help='sum the integers (default: find the max)'
        )

    parser = Parser()
    parser.parse_args([""])

    assert not parser.integers
