"""Config files reach subparser arguments through the parent parser."""

import json
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
