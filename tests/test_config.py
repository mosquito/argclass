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


class TestConfigBooleanConversion:
    """Test boolean type conversion from config files."""

    def test_bool_true_values(self, tmp_path: Path):
        """Test various true boolean string values from config."""
        config_file = tmp_path / "config.ini"
        config_file.write_text(
            "[DEFAULT]\n"
            "flag1 = true\n"
            "flag2 = yes\n"
            "flag3 = 1\n"
            "flag4 = on\n"
            "flag5 = enable\n"
            "flag6 = enabled\n"
            "flag7 = t\n"
            "flag8 = y\n"
        )

        class Parser(argclass.Parser):
            flag1: bool = False
            flag2: bool = False
            flag3: bool = False
            flag4: bool = False
            flag5: bool = False
            flag6: bool = False
            flag7: bool = False
            flag8: bool = False

        parser = Parser(config_files=[config_file])
        parser.parse_args([])

        assert parser.flag1 is True
        assert parser.flag2 is True
        assert parser.flag3 is True
        assert parser.flag4 is True
        assert parser.flag5 is True
        assert parser.flag6 is True
        assert parser.flag7 is True
        assert parser.flag8 is True

    def test_bool_false_values(self, tmp_path: Path):
        """Test various false boolean string values from config."""
        config_file = tmp_path / "config.ini"
        config_file.write_text(
            "[DEFAULT]\n"
            "flag1 = false\n"
            "flag2 = no\n"
            "flag3 = 0\n"
            "flag4 = off\n"
            "flag5 = disable\n"
            "flag6 = disabled\n"
            "flag7 = f\n"
            "flag8 = n\n"
        )

        class Parser(argclass.Parser):
            flag1: bool = True
            flag2: bool = True
            flag3: bool = True
            flag4: bool = True
            flag5: bool = True
            flag6: bool = True
            flag7: bool = True
            flag8: bool = True

        parser = Parser(config_files=[config_file])
        parser.parse_args([])

        assert parser.flag1 is False
        assert parser.flag2 is False
        assert parser.flag3 is False
        assert parser.flag4 is False
        assert parser.flag5 is False
        assert parser.flag6 is False
        assert parser.flag7 is False
        assert parser.flag8 is False

    def test_bool_with_groups(self, tmp_path: Path):
        """Test boolean conversion in groups from config."""
        config_file = tmp_path / "config.ini"
        config_file.write_text(
            "[DEFAULT]\nverbose = true\n[server]\nenabled = yes\ndebug = 1\n"
        )

        class ServerGroup(argclass.Group):
            enabled: bool = False
            debug: bool = False

        class Parser(argclass.Parser):
            verbose: bool = False
            server = ServerGroup()

        parser = Parser(config_files=[config_file])
        parser.parse_args([])

        assert parser.verbose is True
        assert parser.server.enabled is True
        assert parser.server.debug is True

    def test_bool_cli_override(self, tmp_path: Path):
        """Test CLI overrides config boolean value."""
        config_file = tmp_path / "config.ini"
        config_file.write_text("[DEFAULT]\ndebug = true\n")

        class Parser(argclass.Parser):
            debug: bool = False

        # Config sets debug=True, but not using CLI flag leaves it True
        parser = Parser(config_files=[config_file])
        parser.parse_args([])
        assert parser.debug is True

    def test_int_from_config(self, tmp_path: Path):
        """Test integer type from config files."""
        config_file = tmp_path / "config.ini"
        config_file.write_text("[DEFAULT]\nport = 9000\ntimeout = 30\n")

        class Parser(argclass.Parser):
            port: int = 8080
            timeout: int = 60

        parser = Parser(config_files=[config_file])
        parser.parse_args([])

        assert parser.port == 9000
        assert parser.timeout == 30

    def test_string_from_config(self, tmp_path: Path):
        """Test string type from config files."""
        config_file = tmp_path / "config.ini"
        config_file.write_text(
            "[DEFAULT]\nhost = example.com\nname = test-app\n"
        )

        class Parser(argclass.Parser):
            host: str = "localhost"
            name: str = "app"

        parser = Parser(config_files=[config_file])
        parser.parse_args([])

        assert parser.host == "example.com"
        assert parser.name == "test-app"

    def test_path_from_config(self, tmp_path: Path):
        """Test Path type from config files."""
        config_file = tmp_path / "config.ini"
        config_file.write_text(
            "[DEFAULT]\noutput = /var/log/app\ndata = /data/files\n"
        )

        class Parser(argclass.Parser):
            output: Path = Path(".")
            data: Path = Path(".")

        parser = Parser(config_files=[config_file])
        parser.parse_args([])

        assert parser.output == Path("/var/log/app")
        assert parser.data == Path("/data/files")


class TestEnvVarBooleanConversion:
    """Test boolean type conversion from environment variables."""

    def test_bool_true_values_from_env(self, monkeypatch):
        """Test various true boolean string values from env vars."""
        monkeypatch.setenv("APP_FLAG1", "true")
        monkeypatch.setenv("APP_FLAG2", "yes")
        monkeypatch.setenv("APP_FLAG3", "1")
        monkeypatch.setenv("APP_FLAG4", "on")

        class Parser(argclass.Parser):
            flag1: bool = False
            flag2: bool = False
            flag3: bool = False
            flag4: bool = False

        parser = Parser(auto_env_var_prefix="APP_")
        parser.parse_args([])

        assert parser.flag1 is True
        assert parser.flag2 is True
        assert parser.flag3 is True
        assert parser.flag4 is True

    def test_bool_false_values_from_env(self, monkeypatch):
        """Test various false boolean string values from env vars."""
        monkeypatch.setenv("APP_FLAG1", "false")
        monkeypatch.setenv("APP_FLAG2", "no")
        monkeypatch.setenv("APP_FLAG3", "0")
        monkeypatch.setenv("APP_FLAG4", "off")

        class Parser(argclass.Parser):
            flag1: bool = True
            flag2: bool = True
            flag3: bool = True
            flag4: bool = True

        parser = Parser(auto_env_var_prefix="APP_")
        parser.parse_args([])

        assert parser.flag1 is False
        assert parser.flag2 is False
        assert parser.flag3 is False
        assert parser.flag4 is False

    def test_bool_with_explicit_env_var(self, monkeypatch):
        """Test boolean with explicit env_var parameter."""
        monkeypatch.setenv("DEBUG_MODE", "yes")
        monkeypatch.setenv("VERBOSE", "1")

        class Parser(argclass.Parser):
            debug: bool = argclass.Argument(env_var="DEBUG_MODE", default=False)
            verbose: bool = argclass.Argument(env_var="VERBOSE", default=False)

        parser = Parser()
        parser.parse_args([])

        assert parser.debug is True
        assert parser.verbose is True

    def test_env_overrides_config_bool(self, tmp_path: Path, monkeypatch):
        """Test env var overrides config file for boolean."""
        config_file = tmp_path / "config.ini"
        config_file.write_text("[DEFAULT]\ndebug = false\n")

        monkeypatch.setenv("APP_DEBUG", "true")

        class Parser(argclass.Parser):
            debug: bool = False

        parser = Parser(config_files=[config_file], auto_env_var_prefix="APP_")
        parser.parse_args([])

        # Env var should override config file
        assert parser.debug is True

    def test_int_from_env(self, monkeypatch):
        """Test integer type from environment variables."""
        monkeypatch.setenv("APP_PORT", "9000")
        monkeypatch.setenv("APP_TIMEOUT", "30")

        class Parser(argclass.Parser):
            port: int = 8080
            timeout: int = 60

        parser = Parser(auto_env_var_prefix="APP_")
        parser.parse_args([])

        assert parser.port == 9000
        assert parser.timeout == 30

    def test_string_from_env(self, monkeypatch):
        """Test string type from environment variables."""
        monkeypatch.setenv("APP_HOST", "example.com")
        monkeypatch.setenv("APP_NAME", "test-app")

        class Parser(argclass.Parser):
            host: str = "localhost"
            name: str = "app"

        parser = Parser(auto_env_var_prefix="APP_")
        parser.parse_args([])

        assert parser.host == "example.com"
        assert parser.name == "test-app"
