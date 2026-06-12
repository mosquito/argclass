# argclass

[![Coverage](https://coveralls.io/repos/github/mosquito/argclass/badge.svg?branch=master)](https://coveralls.io/github/mosquito/argclass?branch=master) [![Actions](https://github.com/mosquito/argclass/workflows/tests/badge.svg)](https://github.com/mosquito/argclass/actions?query=workflow%3Atests) [![Latest Version](https://img.shields.io/pypi/v/argclass.svg)](https://pypi.python.org/pypi/argclass/) [![Python Versions](https://img.shields.io/pypi/pyversions/argclass.svg)](https://pypi.python.org/pypi/argclass/) [![License](https://img.shields.io/pypi/l/argclass.svg)](https://pypi.python.org/pypi/argclass/)

**Declarative CLI parser with type hints, config files, and environment variables.**

Build type-safe command-line interfaces using Python classes. Zero dependencies.

**[Documentation](https://docs.argclass.com)** | **[PyPI](https://pypi.org/project/argclass/)**

## Installation

```bash
pip install argclass
```

## Quick Start

<!--- name: test_hero_example --->
```python
import argclass

class Server(argclass.Parser):
    host: str = "127.0.0.1"
    port: int = 8080
    debug: bool = False

server = Server()
server.parse_args(["--host", "0.0.0.0", "--port", "9000", "--debug"])
assert server.host == "0.0.0.0"
assert server.port == 9000
assert server.debug is True
```

```bash
$ python server.py --host 0.0.0.0 --port 9000 --debug
```

## Features

| Feature | argclass | argparse | click/typer |
|---------|----------|----------|-------------|
| Type hints | Yes | No | Yes |
| IDE autocompletion | Yes | No | Yes |
| Config files | Built-in | No | No |
| Environment variables | Built-in | No | Plugin |
| Secret masking | Built-in | No | No |
| Dependencies | stdlib | stdlib | Many |

## Examples

### Type Annotations

<!--- name: test_type_annotations --->
```python
import argclass
from pathlib import Path

class Parser(argclass.Parser):
    name: str                    # required
    count: int = 10              # optional with default
    config: Path | None = None   # optional path
    files: list[str]             # list of values

parser = Parser()
parser.parse_args(["--name", "test", "--files", "a.txt", "b.txt"])
assert parser.name == "test"
assert parser.count == 10
assert parser.files == ["a.txt", "b.txt"]
```

### Argument Groups

<!--- name: test_groups_example --->
```python
import argclass

class DatabaseGroup(argclass.Group):
    host: str = "localhost"
    port: int = 5432

class Parser(argclass.Parser):
    debug: bool = False
    db = DatabaseGroup()

parser = Parser()
parser.parse_args(["--db-host", "db.example.com", "--db-port", "3306"])
assert parser.db.host == "db.example.com"
assert parser.db.port == 3306
```

Groups can also contain other Groups. Names join with `-` (CLI), `_`
(env vars), or `.` (INI/TOML sections):

<!--- name: test_nested_groups_example --->
```python
import argclass

class Credentials(argclass.Group):
    username: str = "admin"
    password: str = "secret"

class Endpoint(argclass.Group):
    host: str = "localhost"
    credentials: Credentials = Credentials()

class Parser(argclass.Parser):
    endpoint: Endpoint = Endpoint()

parser = Parser()
parser.parse_args([
    "--endpoint-host", "api.example.com",
    "--endpoint-credentials-username", "root",
])
assert parser.endpoint.host == "api.example.com"
assert parser.endpoint.credentials.username == "root"
```

See [Groups](https://docs.argclass.com/groups.html#nested-groups) for
nested groups in config files, environment variables, and `--help`.

### Configuration Files

Load default values from configuration files. INI by default, JSON/TOML via `config_parser_class`.
See [Config Files](https://docs.argclass.com/config-files.html) for details.

<!--- name: test_config_example --->
```python
import argclass
from pathlib import Path
from tempfile import NamedTemporaryFile

class Parser(argclass.Parser):
    host: str = "localhost"
    port: int = 8080

# Config file content
CONFIG_CONTENT = """
[DEFAULT]
host = example.com
port = 9000
"""

with NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
    f.write(CONFIG_CONTENT)
    config_path = f.name

parser = Parser(config_files=[config_path])
parser.parse_args([])
assert parser.host == "example.com"
assert parser.port == 9000

Path(config_path).unlink()
```

**Tip:** Use `os.getenv()` for dynamic config paths. Multiple files are merged
(later overrides earlier), enabling global defaults with user overrides:

```python
import os
import argclass

class Parser(argclass.Parser):
    host: str = "localhost"

parser = Parser(config_files=[
    os.getenv("MYAPP_CONFIG", "/etc/myapp/config.ini"),  # Global defaults
    "~/.config/myapp.ini",  # User overrides (partial config OK)
])
```

To let the **end user** choose the config file, add
`config_argument="--config"` — the flag's file becomes argument
defaults (CLI and env vars still win):

<!--- name: test_config_argument_example --->
```python
import argclass
from pathlib import Path
from tempfile import NamedTemporaryFile

class Parser(argclass.Parser):
    host: str = "localhost"
    port: int = 8080

with NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
    f.write("[DEFAULT]\nhost = example.com\nport = 9000\n")
    config_path = f.name

parser = Parser(config_argument="--config")
parser.parse_args(["--config", config_path, "--port", "1234"])
assert parser.host == "example.com"   # default from the file
assert parser.port == 1234            # CLI still wins

Path(config_path).unlink()
```

### Environment Variables

<!--- name: test_env_example --->
```python
import os
import argclass

os.environ["APP_HOST"] = "env.example.com"
os.environ["APP_DEBUG"] = "true"

class Parser(argclass.Parser):
    host: str = "localhost"
    debug: bool = False

parser = Parser(auto_env_var_prefix="APP_")
parser.parse_args([])
assert parser.host == "env.example.com"
assert parser.debug is True

del os.environ["APP_HOST"]
del os.environ["APP_DEBUG"]
```

### Generating Config Files

argclass can WRITE config files for a parser — the inverse of
reading them. Wire a `--generate-config` flag and end users dump
a working config straight from the CLI:

<!--- name: test_readme_config_gen --->
```python
import argclass

class CLI(argclass.Parser):
    host: str = "localhost"
    port: int = 8080
    generate_config = argclass.Argument(
        action=argclass.GenerateConfigAction,
        generator=argclass.TOMLConfigGenerator,
        metavar="FILE",
    )
```

```
myapp --generate-config /etc/myapp.toml   # write a file
myapp --generate-config -                 # print to stdout
```

The action captures values from class defaults, `config_files=`,
env vars, and any CLI flags that appear BEFORE
`--generate-config`, then exits with status 0.

Four built-in generators: `INIConfigGenerator`,
`JSONConfigGenerator`, `TOMLConfigGenerator`, `EnvConfigGenerator`.
Subclass `ConfigGenerator` to add your own. See [Generating
Config Files](https://docs.argclass.com/config-generation.html)
for the full guide (multi-format wiring, env-listings, format
conversion, `NonConfigAction` opt-out for fire-and-exit actions).

### Subcommands

```python
import argclass

class ServeCommand(argclass.Parser):
    """Start the server."""
    host: str = "0.0.0.0"
    port: int = 8080

    def __call__(self) -> int:
        print(f"Serving on {self.host}:{self.port}")
        return 0

class CLI(argclass.Parser):
    verbose: bool = False
    serve = ServeCommand()

if __name__ == "__main__":
    cli = CLI()
    cli.parse_args()
    exit(cli())
```

```bash
$ python app.py serve --host 127.0.0.1 --port 9000
Serving on 127.0.0.1:9000
```

### Secrets

<!--- name: test_secrets_example --->
```python
import argclass

class Parser(argclass.Parser):
    api_key: str = argclass.Secret(env_var="API_KEY")

# SecretString prevents accidental logging
# repr() returns '******', str() returns actual value
```

### Argparse Passthrough

`Argument()` forwards any extra keyword arguments to
`argparse.add_argument()`, so argparse-specific options like `version=` work
out of the box:

<!--- name: test_version_example --->
```python
import argclass

class CLI(argclass.Parser):
    version = argclass.Argument(
        "-V", "--version",
        action=argclass.Actions.VERSION,
        version="myapp/1.2.3",
    )

try:
    CLI().parse_args(["--version"])
except SystemExit as exc:
    assert exc.code == 0
```

The same passthrough lets you ship custom `argparse.Action` subclasses
that take their own constructor parameters — for example, a
`--check-updates` flag that queries PyPI:

<!--- name: test_readme_custom_action_pypi_update --->
```python
import json, urllib.request
from importlib.metadata import version as get_version

import argclass

class CheckPyPIUpdate(argclass.NonConfigAction):
    def __init__(self, option_strings, dest, package_name, **kwargs):
        kwargs.setdefault("nargs", 0)
        self.package_name = package_name
        super().__init__(option_strings, dest, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        url = f"https://pypi.org/pypi/{self.package_name}/json"
        with urllib.request.urlopen(url, timeout=5) as r:
            latest = json.load(r)["info"]["version"]
        current = get_version(self.package_name)
        setattr(namespace, self.dest, {
            "current": current,
            "latest": latest,
            "up_to_date": current == latest,
        })

class CLI(argclass.Parser):
    # --check-updates is auto-derived from the attribute name
    check_updates = argclass.Argument(
        action=CheckPyPIUpdate,
        package_name="argclass",  # passthrough kwarg
    )

cli = CLI()
cli.parse_args(["--check-updates"])
assert cli.check_updates["current"] == get_version("argclass")
assert isinstance(cli.check_updates["latest"], str)
assert isinstance(cli.check_updates["up_to_date"], bool)
assert "check_updates" not in argclass.INIConfigGenerator().dump_to_string(cli)
```

See [Argparse Passthrough Kwargs](https://docs.argclass.com/arguments.html#argparse-passthrough-kwargs)
for the full pattern.

### Interactive Examples

Run `python -m argclass` to explore all features interactively.
Each subcommand prints its own source code and demonstrates a different feature:

```bash
python -m argclass basic          # str, int, float, bool, Optional
python -m argclass types          # Literal, list, Enum, frozenset
python -m argclass groups         # argument groups with prefixes
python -m argclass secrets        # Secret and SecretString masking
python -m argclass env            # environment variable integration
python -m argclass subcommands    # nested subcommands with __call__
```

## Documentation

Full documentation at **[docs.argclass.com](https://docs.argclass.com)**:

- [Quick Start](https://docs.argclass.com/quickstart.html)
- [Tutorial](https://docs.argclass.com/tutorial.html)
- [Arguments](https://docs.argclass.com/arguments.html)
- [Groups](https://docs.argclass.com/groups.html)
- [Subparsers](https://docs.argclass.com/subparsers.html)
- [Config Files](https://docs.argclass.com/config-files.html)
- [Environment Variables](https://docs.argclass.com/environment.html)
- [Secrets](https://docs.argclass.com/secrets.html)
- [API Reference](https://docs.argclass.com/api.html)
