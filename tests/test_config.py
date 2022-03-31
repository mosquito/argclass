from configparser import ConfigParser

import pytest

import argclass


class TestBasics:
    class Parser(argclass.Parser):
        config = argclass.Config(search_paths=["test.conf"])
        foo: str = argclass.Argument(help="foo")

    def test_simple(self):
        parser = self.Parser()
        parser.parse_args([])

    def test_example_config(self, tmp_path):
        config = ConfigParser()
        config[config.default_section]["foo"] = "bar"
        config.add_section("test_section")
        config["test_section"]["spam"] = "egg"

        config_file = tmp_path / "config.ini"
        with open(config_file, "w") as fp:
            config.write(fp)

        parser = self.Parser()
        parser.parse_args(["--config", str(config_file)])

        assert parser.config['foo'] == "bar"


def test_config_type():
    class Parser(argclass.Parser):
        config = argclass.Config(type=str)

    parser = Parser()

    with pytest.raises(ValueError):
        parser.parse_args(['--config=test.ini'])
