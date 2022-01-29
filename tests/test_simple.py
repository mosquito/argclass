import argclass


class TestBasics:
    class Parser(argclass.Parser):
        integers: list[int] = argclass.Argument(
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


class TestFoo:
    class Parser(argclass.Parser):
        foo: str = argclass.Argument(help="foo")

    def test_simple(self):
        parser = self.Parser()
        parser.parse_args(["--foo", "bar"])
        assert parser.foo == "bar"

        parser.parse_args(["--foo=bar"])
        assert parser.foo == "bar"
