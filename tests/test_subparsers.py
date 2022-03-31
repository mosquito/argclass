import argclass


def test_subparsers():
    class Subparser(argclass.Parser):
        foo: str = argclass.Argument()

    class Parser(argclass.Parser):
        subparser = Subparser()

    parser = Parser()
    parser.parse_args(["subparser", "--foo=bar"])
    assert parser.subparser.foo == "bar"

