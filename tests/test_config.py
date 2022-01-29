import argclass


class TestBasics:
    class Parser(argclass.Parser):
        config: list[int] = argclass.Config(search_paths=["test.conf"])
        foo: str = argclass.Argument(help="foo")

    def test_simple(self):
        parser = self.Parser()
        parser.parse_args([])
