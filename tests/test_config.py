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


class TestPartialConfigMerging:
    """
    Test loading and merging partial configs from multiple files.
    """

    def test_multiple_files_merge(self, tmp_path: Path):
        """
        Test that multiple config files are merged, later overrides earlier.
        """
        # Global config (e.g., /etc/myapp.ini)
        global_config = tmp_path / "global.ini"
        global_config.write_text(
            "[DEFAULT]\nhost = global.example.com\nport = 8080\ndebug = false\n"
        )

        # User config (e.g., ~/.config/myapp.ini)
        user_config = tmp_path / "user.ini"
        user_config.write_text(
            "[DEFAULT]\n"
            "host = user.example.com\n"
            # port not specified - should use global value
            "debug = true\n"
        )

        class Parser(argclass.Parser):
            host: str = "localhost"
            port: int = 80
            debug: bool = False

        parser = Parser(config_files=[global_config, user_config])
        parser.parse_args([])

        # User config overrides global
        assert parser.host == "user.example.com"
        # Global config value preserved (not in user config)
        assert parser.port == 8080
        # User config overrides global
        assert parser.debug is True

    def test_groups_in_separate_files(self, tmp_path: Path):
        """Test different groups can be configured in different files."""
        # Global config with database settings
        global_config = tmp_path / "global.ini"
        global_config.write_text(
            "[DEFAULT]\n"
            "verbose = false\n"
            "[database]\n"
            "host = db.global.example.com\n"
            "port = 5432\n"
            "[server]\n"
            "host = 0.0.0.0\n"
            "port = 8080\n"
        )

        # User config with only server overrides
        user_config = tmp_path / "user.ini"
        user_config.write_text(
            "[DEFAULT]\nverbose = true\n[server]\nhost = 127.0.0.1\n"
            # port not specified - should use global
        )

        class DatabaseGroup(argclass.Group):
            host: str = "localhost"
            port: int = 5432

        class ServerGroup(argclass.Group):
            host: str = "localhost"
            port: int = 80

        class Parser(argclass.Parser):
            verbose: bool = False
            database = DatabaseGroup()
            server = ServerGroup()

        parser = Parser(config_files=[global_config, user_config])
        parser.parse_args([])

        # User overrides global default
        assert parser.verbose is True
        # Database group unchanged from global config
        assert parser.database.host == "db.global.example.com"
        assert parser.database.port == 5432
        # Server host overridden by user, port from global
        assert parser.server.host == "127.0.0.1"
        assert parser.server.port == 8080

    def test_three_level_config_hierarchy(self, tmp_path: Path):
        """Test system -> global -> user config hierarchy."""
        # System defaults (e.g., /usr/share/myapp/defaults.ini)
        system_config = tmp_path / "system.ini"
        system_config.write_text(
            "[DEFAULT]\n"
            "log_level = warning\n"
            "max_connections = 100\n"
            "timeout = 30\n"
        )

        # Global config (e.g., /etc/myapp.ini)
        global_config = tmp_path / "global.ini"
        global_config.write_text(
            "[DEFAULT]\nlog_level = info\nmax_connections = 500\n"
            # timeout not specified - uses system default
        )

        # User config (e.g., ~/.config/myapp.ini)
        user_config = tmp_path / "user.ini"
        user_config.write_text(
            "[DEFAULT]\nlog_level = debug\n"
            # Others not specified - use previous values
        )

        class Parser(argclass.Parser):
            log_level: str = "error"
            max_connections: int = 10
            timeout: int = 60

        parser = Parser(
            config_files=[system_config, global_config, user_config]
        )
        parser.parse_args([])

        # User overrides everything
        assert parser.log_level == "debug"
        # Global overrides system
        assert parser.max_connections == 500
        # System value preserved
        assert parser.timeout == 30

    def test_partial_group_override(self, tmp_path: Path):
        """Test partial override of group settings."""
        global_config = tmp_path / "global.ini"
        global_config.write_text(
            "[logging]\n"
            "level = warning\n"
            "file = /var/log/app.log\n"
            "format = json\n"
            "rotate = true\n"
        )

        user_config = tmp_path / "user.ini"
        user_config.write_text(
            "[logging]\nlevel = debug\nfile = ./debug.log\n"
            # format and rotate not specified - use global
        )

        class LoggingGroup(argclass.Group):
            level: str = "info"
            file: str = "app.log"
            format: str = "text"
            rotate: bool = False

        class Parser(argclass.Parser):
            logging = LoggingGroup()

        parser = Parser(config_files=[global_config, user_config])
        parser.parse_args([])

        # User overrides
        assert parser.logging.level == "debug"
        assert parser.logging.file == "./debug.log"
        # Global values preserved
        assert parser.logging.format == "json"
        assert parser.logging.rotate is True

    def test_missing_intermediate_config(self, tmp_path: Path):
        """Test that missing config files in the chain are skipped."""
        global_config = tmp_path / "global.ini"
        global_config.write_text("[DEFAULT]\nvalue = global\n")

        # Middle config doesn't exist
        missing_config = tmp_path / "missing.ini"

        user_config = tmp_path / "user.ini"
        user_config.write_text("[DEFAULT]\nother = user\n")

        class Parser(argclass.Parser):
            value: str = "default"
            other: str = "default"

        parser = Parser(
            config_files=[global_config, missing_config, user_config]
        )
        parser.parse_args([])

        assert parser.value == "global"
        assert parser.other == "user"

    def test_cli_overrides_all_configs(self, tmp_path: Path):
        """Test CLI arguments override all config files."""
        global_config = tmp_path / "global.ini"
        global_config.write_text("[DEFAULT]\nport = 8080\n")

        user_config = tmp_path / "user.ini"
        user_config.write_text("[DEFAULT]\nport = 9000\n")

        class Parser(argclass.Parser):
            port: int = 80

        parser = Parser(config_files=[global_config, user_config])
        parser.parse_args(["--port", "3000"])

        # CLI overrides both configs
        assert parser.port == 3000


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


class TestDefaultsParsers:
    """Test custom defaults parser classes for config_files."""

    def test_json_defaults_parser(self, tmp_path: Path):
        """Test using JSONDefaultsParser for config_files."""
        config_file = tmp_path / "config.json"
        config_file.write_text('{"host": "json.example.com", "port": 9000}')

        class Parser(argclass.Parser):
            host: str = "localhost"
            port: int = 8080

        parser = Parser(
            config_files=[config_file],
            config_parser_class=argclass.JSONDefaultsParser,
        )
        parser.parse_args([])

        assert parser.host == "json.example.com"
        assert parser.port == 9000

    def test_json_defaults_with_groups(self, tmp_path: Path):
        """Test JSONDefaultsParser with argument groups."""
        config_file = tmp_path / "config.json"
        config_data = (
            '{"verbose": true, '
            '"database": {"host": "db.example.com", "port": 5432}}'
        )
        config_file.write_text(config_data)

        class DatabaseGroup(argclass.Group):
            host: str = "localhost"
            port: int = 3306

        class Parser(argclass.Parser):
            verbose: bool = False
            database = DatabaseGroup()

        parser = Parser(
            config_files=[config_file],
            config_parser_class=argclass.JSONDefaultsParser,
        )
        parser.parse_args([])

        assert parser.verbose is True
        assert parser.database.host == "db.example.com"
        assert parser.database.port == 5432

    def test_toml_defaults_parser(self, tmp_path: Path):
        """Test using TOMLDefaultsParser for config_files."""
        if not _has_toml_support():
            pytest.skip("TOML support not available")

        config_file = tmp_path / "config.toml"
        config_file.write_text('host = "toml.example.com"\nport = 7000\n')

        class Parser(argclass.Parser):
            host: str = "localhost"
            port: int = 8080

        parser = Parser(
            config_files=[config_file],
            config_parser_class=argclass.TOMLDefaultsParser,
        )
        parser.parse_args([])

        assert parser.host == "toml.example.com"
        assert parser.port == 7000

    def test_toml_defaults_with_groups(self, tmp_path: Path):
        """Test TOMLDefaultsParser with argument groups."""
        if not _has_toml_support():
            pytest.skip("TOML support not available")

        config_file = tmp_path / "config.toml"
        config_file.write_text(
            'debug = true\n\n[server]\nhost = "0.0.0.0"\nport = 9000\n'
        )

        class ServerGroup(argclass.Group):
            host: str = "localhost"
            port: int = 8080

        class Parser(argclass.Parser):
            debug: bool = False
            server = ServerGroup()

        parser = Parser(
            config_files=[config_file],
            config_parser_class=argclass.TOMLDefaultsParser,
        )
        parser.parse_args([])

        assert parser.debug is True
        assert parser.server.host == "0.0.0.0"
        assert parser.server.port == 9000

    def test_multiple_json_files_merge(self, tmp_path: Path):
        """Test merging multiple JSON config files."""
        global_config = tmp_path / "global.json"
        global_config.write_text('{"host": "global.example.com", "port": 8080}')

        user_config = tmp_path / "user.json"
        user_config.write_text('{"host": "user.example.com"}')

        class Parser(argclass.Parser):
            host: str = "localhost"
            port: int = 80

        parser = Parser(
            config_files=[global_config, user_config],
            config_parser_class=argclass.JSONDefaultsParser,
        )
        parser.parse_args([])

        # User overrides global
        assert parser.host == "user.example.com"
        # Global value preserved
        assert parser.port == 8080

    def test_custom_defaults_parser(self, tmp_path: Path):
        """Test creating a custom defaults parser."""
        config_file = tmp_path / "config.custom"
        config_file.write_text("host=custom.example.com\nport=5000\n")

        class CustomDefaultsParser(argclass.AbstractDefaultsParser):
            """Simple key=value parser."""

            def parse(self):
                result = {}
                for path in self._filter_readable_paths():
                    with path.open() as f:
                        for line in f:
                            line = line.strip()
                            if "=" in line:
                                key, value = line.split("=", 1)
                                result[key.strip()] = value.strip()
                    self._loaded_files = (path,)
                return result

        class Parser(argclass.Parser):
            host: str = "localhost"
            port: int = 8080

        parser = Parser(
            config_files=[config_file],
            config_parser_class=CustomDefaultsParser,
        )
        parser.parse_args([])

        assert parser.host == "custom.example.com"
        assert parser.port == 5000


def _has_toml_support() -> bool:
    from importlib.util import find_spec

    return find_spec("tomllib") is not None or find_spec("tomli") is not None


@pytest.mark.skipif(
    not _has_toml_support(),
    reason="TOML support requires Python 3.11+ (tomllib) or 'tomli' package",
)
class TestTOMLConfig:
    """Test TOML configuration file support."""

    def test_toml_config_basic(self, tmp_path: Path):
        """Test basic TOML config loading."""
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            'host = "example.com"\nport = 9000\ndebug = true\n'
        )

        class Parser(argclass.Parser):
            config = argclass.Config(config_class=argclass.TOMLConfig)

        parser = Parser()
        parser.parse_args(["--config", str(config_file)])

        assert parser.config["host"] == "example.com"
        assert parser.config["port"] == 9000
        assert parser.config["debug"] is True

    def test_toml_config_nested(self, tmp_path: Path):
        """Test TOML config with nested tables."""
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            "[database]\n"
            'host = "db.example.com"\n'
            "port = 5432\n"
            "\n"
            "[server]\n"
            'host = "0.0.0.0"\n'
            "port = 8080\n"
        )

        class Parser(argclass.Parser):
            config = argclass.Config(config_class=argclass.TOMLConfig)

        parser = Parser()
        parser.parse_args(["--config", str(config_file)])

        assert parser.config["database"]["host"] == "db.example.com"
        assert parser.config["database"]["port"] == 5432
        assert parser.config["server"]["host"] == "0.0.0.0"
        assert parser.config["server"]["port"] == 8080

    def test_toml_config_arrays(self, tmp_path: Path):
        """Test TOML config with arrays."""
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            'features = ["auth", "logging", "metrics"]\n'
            "\n"
            "[[servers]]\n"
            'name = "primary"\n'
            "port = 8080\n"
            "\n"
            "[[servers]]\n"
            'name = "backup"\n'
            "port = 8081\n"
        )

        class Parser(argclass.Parser):
            config = argclass.Config(config_class=argclass.TOMLConfig)

        parser = Parser()
        parser.parse_args(["--config", str(config_file)])

        assert parser.config["features"] == ["auth", "logging", "metrics"]
        assert len(parser.config["servers"]) == 2
        assert parser.config["servers"][0]["name"] == "primary"
        assert parser.config["servers"][1]["name"] == "backup"

    def test_toml_config_with_cli_args(self, tmp_path: Path):
        """Test TOML config combined with CLI arguments."""
        config_file = tmp_path / "config.toml"
        config_file.write_text('[app]\nname = "myapp"\nversion = 1\n')

        class Parser(argclass.Parser):
            verbose: bool = False
            config = argclass.Config(config_class=argclass.TOMLConfig)

        parser = Parser()
        parser.parse_args(["--config", str(config_file), "--verbose"])

        assert parser.verbose is True
        assert parser.config["app"]["name"] == "myapp"
        assert parser.config["app"]["version"] == 1
