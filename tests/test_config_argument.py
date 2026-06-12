"""Tests for the ``config_argument`` Parser constructor parameter.

``config_argument="--config"`` adds a CLI flag that lets the end user
point at a configuration file whose values become argument defaults —
the same effect as the developer-supplied ``config_files``, resolved
at invocation time via two-pass parsing.

Priority chain: declared defaults < config_files < --config file
< env vars < CLI args.
"""

import json
from pathlib import Path

import pytest

import argclass


class DB(argclass.Group):
    host: str = "localhost"
    port: int = 5432


class Credentials(argclass.Group):
    username: str = "admin"


class Endpoint(argclass.Group):
    credentials: Credentials = Credentials()


def make_cli() -> type:
    class CLI(argclass.Parser):
        debug: bool = False
        workers: int = 1
        tags: list[str] = argclass.Argument(
            nargs=argclass.Nargs.ZERO_OR_MORE, default=[]
        )
        db: DB = DB()

    return CLI


@pytest.fixture
def ini_config(tmp_path) -> Path:
    config = tmp_path / "app.ini"
    config.write_text(
        "[DEFAULT]\n"
        "workers = 8\n"
        "debug = true\n"
        "tags = ['a', 'b']\n"
        "[db]\n"
        "host = db.example.com\n"
    )
    return config


class TestDefaultsFromConfigArgument:
    def test_values_become_defaults(self, ini_config):
        cli = make_cli()(config_argument="--config")
        cli.parse_args(["--config", str(ini_config)])
        assert cli.workers == 8
        assert cli.debug is True
        assert cli.tags == ["a", "b"]
        assert cli.db.host == "db.example.com"
        assert cli.db.port == 5432  # untouched: declared default

    def test_equals_form_and_aliases(self, ini_config):
        cli = make_cli()(config_argument=("-c", "--config"))
        cli.parse_args([f"--config={ini_config}"])
        assert cli.workers == 8

        cli = make_cli()(config_argument=("-c", "--config"))
        cli.parse_args(["-c", str(ini_config)])
        assert cli.workers == 8

    def test_nested_group_sections(self, tmp_path):
        config = tmp_path / "app.ini"
        config.write_text("[endpoint.credentials]\nusername = root\n")

        class CLI(argclass.Parser):
            endpoint: Endpoint = Endpoint()

        cli = CLI(config_argument="--config")
        cli.parse_args(["--config", str(config)])
        assert cli.endpoint.credentials.username == "root"

    def test_required_argument_satisfied_by_config(self, tmp_path):
        config = tmp_path / "app.ini"
        config.write_text("[DEFAULT]\nname = from-config\n")

        class CLI(argclass.Parser):
            name: str

        cli = CLI(config_argument="--config")
        cli.parse_args(["--config", str(config)])
        assert cli.name == "from-config"

        # Without the config the argument is still required.
        with pytest.raises(SystemExit):
            CLI(config_argument="--config").parse_args([])

    def test_json_parser_class(self, tmp_path):
        config = tmp_path / "app.json"
        config.write_text(
            json.dumps({"workers": 9, "db": {"host": "json-host"}}),
        )
        cli = make_cli()(
            config_argument="--config",
            config_parser_class=argclass.JSONDefaultsParser,
        )
        cli.parse_args(["--config", str(config)])
        assert cli.workers == 9
        assert cli.db.host == "json-host"


class TestPriorityChain:
    def test_cli_overrides_config(self, ini_config):
        cli = make_cli()(config_argument="--config")
        cli.parse_args(["--config", str(ini_config), "--workers", "2"])
        assert cli.workers == 2

    def test_env_overrides_config(self, ini_config, monkeypatch):
        monkeypatch.setenv("APP_WORKERS", "5")
        cli = make_cli()(
            config_argument="--config",
            auto_env_var_prefix="APP_",
        )
        cli.parse_args(["--config", str(ini_config)])
        assert cli.workers == 5

    def test_config_argument_overrides_config_files(self, ini_config, tmp_path):
        ctor = tmp_path / "ctor.ini"
        ctor.write_text("[DEFAULT]\nworkers = 3\n")
        cli = make_cli()(
            config_files=[ctor],
            config_argument="--config",
        )
        cli.parse_args(["--config", str(ini_config)])
        assert cli.workers == 8

    def test_config_files_still_used_for_missing_keys(
        self, ini_config, tmp_path
    ):
        ctor = tmp_path / "ctor.ini"
        ctor.write_text("[DEFAULT]\nworkers = 3\n[db]\nport = 9999\n")
        cli = make_cli()(
            config_files=[ctor],
            config_argument="--config",
        )
        cli.parse_args(["--config", str(ini_config)])
        # db.port comes from the constructor config (absent in user's)
        assert cli.db.port == 9999
        assert cli.db.host == "db.example.com"


class TestLifecycle:
    def test_no_flag_passed_keeps_declared_defaults(self):
        cli = make_cli()(config_argument="--config")
        cli.parse_args([])
        assert cli.workers == 1

    def test_no_staleness_between_parses(self, ini_config):
        cli = make_cli()(config_argument="--config")
        cli.parse_args(["--config", str(ini_config)])
        assert cli.workers == 8
        cli.parse_args([])
        assert cli.workers == 1

    def test_loaded_config_files_property(self, ini_config, tmp_path):
        ctor = tmp_path / "ctor.ini"
        ctor.write_text("[DEFAULT]\nworkers = 3\n")
        cli = make_cli()(
            config_files=[ctor],
            config_argument="--config",
        )
        cli.parse_args(["--config", str(ini_config)])
        assert cli.loaded_config_files == (ctor, ini_config)

    def test_flag_appears_in_help(self, capsys):
        cli = make_cli()(config_argument="--config")
        cli.print_help()
        out = capsys.readouterr().out
        assert "--config FILE" in out


class TestErrors:
    def test_missing_explicit_file_raises(self):
        cli = make_cli()(config_argument="--config")
        with pytest.raises(argclass.ConfigurationError) as exc_info:
            cli.parse_args(["--config", "/no/such/file.ini"])
        assert "/no/such/file.ini" in str(exc_info.value)

    def test_malformed_explicit_file_raises(self, tmp_path):
        bad = tmp_path / "bad.ini"
        bad.write_text("this is not an ini file at all\n")
        cli = make_cli()(config_argument="--config")
        with pytest.raises(argclass.ConfigurationError):
            cli.parse_args(["--config", str(bad)])

    def test_positional_config_argument_rejected(self):
        with pytest.raises(argclass.ArgumentDefinitionError):
            make_cli()(config_argument="config")

    def test_custom_parser_configuration_error_passes_through(self, tmp_path):
        # A custom defaults parser raising ConfigurationError keeps
        # its own error instead of being re-wrapped.
        marker = argclass.ConfigurationError("custom parser error")

        class FailingParser(argclass.INIDefaultsParser):
            def parse(self):
                # The constructor also instantiates this class for
                # ``config_files`` (with no paths); only fail for the
                # user-supplied file.
                if self._paths:
                    raise marker
                return super().parse()

        config = tmp_path / "app.ini"
        config.write_text("[DEFAULT]\n")
        cli = make_cli()(
            config_argument="--config",
            config_parser_class=FailingParser,
        )
        with pytest.raises(argclass.ConfigurationError) as exc_info:
            cli.parse_args(["--config", str(config)])
        assert exc_info.value is marker

    def test_flag_without_value_reported_by_real_parser(self, capsys):
        # The pre-scan swallows the syntax error; the real parser
        # reports it with proper usage text and exits.
        cli = make_cli()(config_argument="--config")
        with pytest.raises(SystemExit):
            cli.parse_args(["--config"])
        assert "--config" in capsys.readouterr().err


class TestConfigActionExplicitFileWins:
    """An explicit --config passed to argclass.Config() must override
    values coming from its search_paths (files merge in priority
    order, later wins)."""

    def test_explicit_overrides_search_paths(self, tmp_path):
        preset = tmp_path / "preset.ini"
        preset.write_text("[sec]\nkey = from-preset\nextra = e\n")
        explicit = tmp_path / "explicit.ini"
        explicit.write_text("[sec]\nkey = from-explicit\n")

        class CLI(argclass.Parser):
            config = argclass.Config(search_paths=[preset])

        cli = CLI()
        cli.parse_args(["--config", str(explicit)])
        assert cli.config["sec"]["key"] == "from-explicit"
        # Non-conflicting keys from search_paths are preserved.
        assert cli.config["sec"]["extra"] == "e"
