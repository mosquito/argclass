"""Config files reach subparser arguments through the parent parser."""

import json
import os
from pathlib import Path

import pytest

import argclass


class DB(argclass.Group):
    host: str = "localhost"
    port: int = 5432


class Worker(argclass.Parser):
    threads: int = 4


class Serve(argclass.Parser):
    port: int = 8080
    db = DB()
    worker = Worker()


class Deploy(argclass.Parser):
    target: str = "production"


class CLI(argclass.Parser):
    debug: bool = False
    serve = Serve()
    deploy = Deploy()


INI = """
[DEFAULT]
debug = true

[serve]
port = 9999

[serve.db]
host = db.example.com

[serve.worker]
threads = 8

[deploy]
target = staging
"""

DATA = {
    "debug": True,
    "serve": {
        "port": 9999,
        "db": {"host": "db.example.com"},
        "worker": {"threads": 8},
    },
    "deploy": {"target": "staging"},
}


def write_toml(path: Path) -> None:
    path.write_text(
        "debug = true\n\n"
        "[serve]\nport = 9999\n\n"
        '[serve.db]\nhost = "db.example.com"\n\n'
        "[serve.worker]\nthreads = 8\n\n"
        '[deploy]\ntarget = "staging"\n',
    )


@pytest.fixture
def ini_path(tmp_path: Path) -> Path:
    path = tmp_path / "app.ini"
    path.write_text(INI)
    return path


def assert_serve_tree(cli: CLI) -> None:
    assert cli.debug is True
    assert cli.serve.port == 9999
    assert cli.serve.db.host == "db.example.com"
    assert cli.serve.db.port == 5432
    assert cli.serve.worker.threads == 8


class TestConfigFiles:
    def test_ini_sections_reach_subparsers(self, ini_path: Path) -> None:
        cli = CLI(config_files=[ini_path])
        cli.parse_args(["serve", "worker"])
        assert_serve_tree(cli)

    def test_json_nesting_reaches_subparsers(self, tmp_path: Path) -> None:
        path = tmp_path / "app.json"
        path.write_text(json.dumps(DATA))
        cli = CLI(
            config_files=[path],
            config_parser_class=argclass.JSONDefaultsParser,
        )
        cli.parse_args(["serve", "worker"])
        assert_serve_tree(cli)

    def test_toml_tables_reach_subparsers(self, tmp_path: Path) -> None:
        path = tmp_path / "app.toml"
        write_toml(path)
        cli = CLI(
            config_files=[path],
            config_parser_class=argclass.TOMLDefaultsParser,
        )
        cli.parse_args(["serve", "worker"])
        assert_serve_tree(cli)

    def test_other_subparser_section(self, ini_path: Path) -> None:
        cli = CLI(config_files=[ini_path])
        cli.parse_args(["deploy"])
        assert cli.deploy.target == "staging"

    def test_root_default_section_does_not_leak(self, tmp_path: Path) -> None:
        """A ``port`` in ``[DEFAULT]`` must not become the subparser's
        ``port``: configparser cascades ``[DEFAULT]`` into every
        section, and the INI reader strips that cascade."""
        path = tmp_path / "app.ini"
        path.write_text("[DEFAULT]\nport = 1\n[serve]\n")
        cli = CLI(config_files=[path])
        cli.parse_args(["serve"])
        assert cli.serve.port == 8080

    def test_cli_overrides_subparser_section(self, ini_path: Path) -> None:
        cli = CLI(config_files=[ini_path])
        cli.parse_args(["serve", "--port", "1", "--db-host", "x", "worker"])
        assert cli.serve.port == 1
        assert cli.serve.db.host == "x"
        assert cli.serve.worker.threads == 8

    def test_env_overrides_subparser_section(
        self, ini_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("SERVE_PORT", "2")

        class Serve2(argclass.Parser):
            port: int = argclass.Argument(default=8080, env_var="SERVE_PORT")

        class Root(argclass.Parser):
            serve = Serve2()

        cli = Root(config_files=[ini_path])
        cli.parse_args(["serve"])
        assert cli.serve.port == 2


class TestConfigArgument:
    def test_config_flag_before_subcommand(self, ini_path: Path) -> None:
        cli = CLI(config_argument="--config")
        cli.parse_args(["--config", str(ini_path), "serve", "worker"])
        assert_serve_tree(cli)

    def test_config_flag_wins_over_config_files(
        self, ini_path: Path, tmp_path: Path
    ) -> None:
        preset = tmp_path / "preset.ini"
        preset.write_text("[serve]\nport = 1\n")
        cli = CLI(config_files=[preset], config_argument="--config")
        cli.parse_args(["--config", str(ini_path), "serve"])
        assert cli.serve.port == 9999

    def test_config_files_still_apply_without_flag(
        self, ini_path: Path
    ) -> None:
        cli = CLI(config_files=[ini_path], config_argument="--config")
        cli.parse_args(["serve"])
        assert cli.serve.port == 9999


class TestOwnConfigFiles:
    def test_subparser_own_files_still_read(self, tmp_path: Path) -> None:
        own = tmp_path / "serve.ini"
        own.write_text("[DEFAULT]\nport = 5\n")

        class Root(argclass.Parser):
            serve = Serve(config_files=[own])

        cli = Root()
        cli.parse_args(["serve"])
        assert cli.serve.port == 5

    def test_parent_file_wins_over_own_files(
        self, ini_path: Path, tmp_path: Path
    ) -> None:
        own = tmp_path / "serve.ini"
        own.write_text("[DEFAULT]\nport = 5\n")

        class Root(argclass.Parser):
            serve = Serve(config_files=[own])

        cli = Root(config_files=[ini_path])
        cli.parse_args(["serve"])
        assert cli.serve.port == 9999


class TestHelp:
    def test_subcommand_help_shows_file_default(
        self, ini_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        cli = CLI(config_files=[ini_path])
        with pytest.raises(SystemExit):
            cli.parse_args(["serve", "--help"])
        out = capsys.readouterr().out
        assert "9999" in out


class TestReuse:
    def test_second_instance_is_independent(self, ini_path: Path) -> None:
        first = CLI(config_files=[ini_path])
        first.parse_args(["serve"])
        second = CLI()
        second.parse_args(["serve"])
        assert first.serve.port == 9999
        assert second.serve.port == 8080


class TestEnvPrefix:
    """``auto_env_var_prefix`` reaches subparsers through the
    attribute path: ``APP_SERVE_PORT``, ``APP_SERVE_DB_HOST``,
    ``APP_SERVE_WORKER_THREADS``."""

    def test_prefix_reaches_subparser_tree(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("APP_DEBUG", "true")
        monkeypatch.setenv("APP_SERVE_PORT", "9999")
        monkeypatch.setenv("APP_SERVE_DB_HOST", "db.example.com")
        monkeypatch.setenv("APP_SERVE_WORKER_THREADS", "8")
        cli = CLI(auto_env_var_prefix="APP_")
        cli.parse_args(["serve", "worker"])
        assert_serve_tree(cli)

    def test_env_overrides_config_section(
        self, ini_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("APP_SERVE_PORT", "1")
        cli = CLI(config_files=[ini_path], auto_env_var_prefix="APP_")
        cli.parse_args(["serve"])
        assert cli.serve.port == 1

    def test_no_prefix_reads_nothing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("SERVE_PORT", "1")
        monkeypatch.setenv("PORT", "2")
        cli = CLI()
        cli.parse_args(["serve"])
        assert cli.serve.port == 8080

    def test_explicit_env_var_wins(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("APP_SERVE_PORT", "1")
        monkeypatch.setenv("MY_PORT", "2")

        class Serve2(argclass.Parser):
            port: int = argclass.Argument(default=8080, env_var="MY_PORT")

        class Root(argclass.Parser):
            serve = Serve2()

        cli = Root(auto_env_var_prefix="APP_")
        cli.parse_args(["serve"])
        assert cli.serve.port == 2

    def test_own_prefix_wins_over_inherited(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("APP_SERVE_PORT", "1")
        monkeypatch.setenv("SRV_PORT", "2")

        class Root(argclass.Parser):
            serve = Serve(auto_env_var_prefix="SRV_")

        cli = Root(auto_env_var_prefix="APP_")
        cli.parse_args(["serve"])
        assert cli.serve.port == 2

    def test_help_shows_inherited_env_var(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        cli = CLI(auto_env_var_prefix="APP_")
        with pytest.raises(SystemExit):
            cli.parse_args(["serve", "--help"])
        assert "[ENV: APP_SERVE_PORT]" in capsys.readouterr().out

    def test_sanitize_env_covers_subparsers(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("APP_SERVE_PORT", "1")
        cli = CLI(auto_env_var_prefix="APP_")
        cli.parse_args(["serve"])
        cli.sanitize_env()
        assert "APP_SERVE_PORT" not in os.environ

    def test_sanitize_secrets_covers_subparsers(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("APP_SERVE_TOKEN", "hunter2")

        class Serve2(argclass.Parser):
            token: str = argclass.Secret(default="")

        class Root(argclass.Parser):
            serve = Serve2()

        cli = Root(auto_env_var_prefix="APP_")
        cli.parse_args(["serve"], sanitize_secrets=True)
        assert cli.serve.token == "hunter2"
        assert "APP_SERVE_TOKEN" not in os.environ

    def test_second_instance_does_not_keep_prefix(self) -> None:
        first = CLI(auto_env_var_prefix="APP_")
        first.parse_args(["serve"])
        second = CLI()
        second.parse_args(["serve"])
        assert first.serve.env_var_prefix == "APP_SERVE_"
        assert second.serve.env_var_prefix is None


def squash(text: str) -> str:
    """Drop all whitespace: argparse wraps long paths mid-word."""
    return "".join(text.split())


class TestSubparserHelpEpilog:
    """A subcommand's --help names the config files it reads."""

    def test_subcommand_help_lists_parent_files(
        self, ini_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        cli = CLI(config_files=[ini_path, Path("/missing.ini")])
        with pytest.raises(SystemExit):
            cli.parse_args(["serve", "--help"])
        out = squash(capsys.readouterr().out)
        assert squash("Default values come from") in out
        assert squash(f"'{ini_path}'") in out
        assert "'/missing.ini'" in out
        assert squash("Found and applied (1):") in out
        assert "PosixPath" not in out

    def test_nested_subcommand_help_lists_parent_files(
        self, ini_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        cli = CLI(config_files=[ini_path])
        with pytest.raises(SystemExit):
            cli.parse_args(["serve", "worker", "--help"])
        out = squash(capsys.readouterr().out)
        assert squash(f"'{ini_path}'") in out
        assert squash("Found and applied (1):") in out

    def test_subcommand_help_reports_config_argument_file(
        self, ini_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        cli = CLI(config_argument="--config")
        with pytest.raises(SystemExit):
            cli.parse_args(["--config", str(ini_path), "serve", "--help"])
        out = squash(capsys.readouterr().out)
        assert squash("Found and applied (1):") in out
        assert squash(str(ini_path.resolve())) in out

    def test_subcommand_help_lists_own_and_parent_files(
        self, ini_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        own = tmp_path / "serve.ini"
        own.write_text("[DEFAULT]\nport = 5\n")

        class Root(argclass.Parser):
            serve = Serve(config_files=[own])

        cli = Root(config_files=[ini_path])
        with pytest.raises(SystemExit):
            cli.parse_args(["serve", "--help"])
        out = squash(capsys.readouterr().out)
        assert squash(f"'{ini_path}'") in out
        assert squash(f"'{own}'") in out
        assert squash("Found and applied (2):") in out

    def test_subcommand_help_without_config_has_no_epilog(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit):
            CLI().parse_args(["serve", "--help"])
        assert "configuration files" not in capsys.readouterr().out
