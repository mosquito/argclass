from configparser import ConfigParser
from pathlib import Path

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

        assert parser.config["foo"] == "bar"


def test_config_type_not_exists():
    class Parser(argclass.Parser):
        config = argclass.Config()

    parser = Parser()
    parser.parse_args(["--config=test.ini"])
    assert parser.config == {}


def test_config_required():
    class Parser(argclass.Parser):
        config = argclass.Config(required=True)

    parser = Parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--config=test.ini"])


def test_config_defaults(tmp_path: Path):
    config = ConfigParser()
    config[config.default_section]["foo"] = "bar"

    config_file = tmp_path / "config.ini"
    with open(config_file, "w") as fp:
        config.write(fp)

    class Parser(argclass.Parser):
        foo = argclass.Argument(default="spam")

    parser = Parser(config_files=[config_file])
    parser.parse_args([])
    assert parser.foo == "bar"


def test_unreadable_config(tmp_path: Path):
    config_file = tmp_path / "config.ini"
    with open(config_file, "w") as fp:
        fp.write("TOP SECRET")

    # Make the config file not read just writeable
    config_file.chmod(0o200)

    class Parser(argclass.Parser):
        pass

    parser = Parser(config_files=[config_file])
    parser.parse_args([])
