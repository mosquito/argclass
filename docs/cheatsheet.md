# Quick Reference

Single-page reference for common argclass patterns.

## Argument Types

<!--- name: test_cheat_types --->
```python
import argclass
from pathlib import Path
from typing import Literal

class Parser(argclass.Parser):
    # Required arguments (no default)
    name: str
    count: int

    # Optional arguments (with default)
    host: str = "localhost"
    port: int = 8080
    ratio: float = 0.5

    # Boolean flags
    verbose: bool = False      # --verbose enables
    cache: bool = True         # --cache disables

    # Collections
    files: list[str]           # --files a.txt b.txt
    tags: set[int]             # --tags 1 2 3 (unique)

    # Optional (can be None)
    config: str | None

    # Choices
    level: Literal["debug", "info", "error"] = "info"

    # File paths
    output: Path = Path(".")

parser = Parser()
parser.parse_args([
    "--name", "test",
    "--count", "5",
    "--files", "a.txt", "b.txt",
    "--tags", "1", "2",
    "--level", "debug",
])
assert parser.name == "test"
assert parser.files == ["a.txt", "b.txt"]
```

## Argument() Options

<!--- name: test_cheat_argument --->
```python
import argclass

class Parser(argclass.Parser):
    # Short alias
    verbose: bool = argclass.Argument(
        "-v", "--verbose",
        default=False,
        action=argclass.Actions.STORE_TRUE
    )

    # Help text
    output: str = argclass.Argument(
        "-o", "--output",
        default="out.txt",
        help="Output file path"
    )

    # Environment variable
    api_key: str = argclass.Argument(
        env_var="API_KEY",
        default=""
    )

    # Choices
    format: str = argclass.Argument(
        choices=["json", "yaml", "toml"],
        default="json"
    )

    # Multiple values
    hosts: list[str] = argclass.Argument(
        nargs="+",
        help="List of hosts"
    )

    # Positional argument
    filename: str = argclass.Argument("filename")

parser = Parser()
parser.parse_args(["input.txt", "--hosts", "a.com", "b.com", "-v"])
assert parser.filename == "input.txt"
assert parser.hosts == ["a.com", "b.com"]
assert parser.verbose is True
```

## Groups

<!--- name: test_cheat_groups --->
```python
import argclass

class DatabaseGroup(argclass.Group):
    host: str = "localhost"
    port: int = 5432
    name: str = "mydb"

class CacheGroup(argclass.Group):
    enabled: bool = True
    ttl: int = 300

class Parser(argclass.Parser):
    debug: bool = False
    database = DatabaseGroup()
    cache = CacheGroup()

parser = Parser()
parser.parse_args([
    "--database-host", "prod.db",
    "--database-port", "5433",
    "--cache-ttl", "600"
])
assert parser.database.host == "prod.db"
assert parser.cache.ttl == 600
```

## Subcommands

<!--- name: test_cheat_subcommands --->
```python
import argclass

class InitCommand(argclass.Parser):
    """Initialize project."""
    force: bool = False

    def __call__(self) -> int:
        return 0

class BuildCommand(argclass.Parser):
    """Build project."""
    output: str = "dist"
    release: bool = False

    def __call__(self) -> int:
        return 0

class CLI(argclass.Parser):
    """Project management tool."""
    verbose: bool = False
    init = InitCommand()
    build = BuildCommand()

cli = CLI()
cli.parse_args(["--verbose", "build", "--release"])
assert cli.verbose is True
assert cli.build.release is True
assert cli() == 0
```

## Config Files

<!--- name: test_cheat_config --->
```python
import argclass
from tempfile import NamedTemporaryFile
from pathlib import Path

class Parser(argclass.Parser):
    host: str = "localhost"
    port: int = 8080

# INI format
ini_content = """
[DEFAULT]
host = example.com
port = 9000
"""

with NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
    f.write(ini_content)
    config_path = f.name

parser = Parser(config_files=[
    "/etc/myapp.ini",      # System config (missing = ignored)
    "~/.config/myapp.ini", # User config (missing = ignored)
    config_path,           # Local config
])
parser.parse_args([])
assert parser.host == "example.com"

Path(config_path).unlink()
```

## Environment Variables

<!--- name: test_cheat_env --->
```python
import os
import argclass

os.environ["MYAPP_HOST"] = "from-env.com"
os.environ["MYAPP_PORT"] = "9000"

class Parser(argclass.Parser):
    host: str = "localhost"
    port: int = 8080

# Auto-generate env var names with prefix
parser = Parser(auto_env_var_prefix="MYAPP_")
parser.parse_args([])

assert parser.host == "from-env.com"
assert parser.port == 9000

del os.environ["MYAPP_HOST"]
del os.environ["MYAPP_PORT"]
```

## Secrets

<!--- name: test_cheat_secrets --->
```python
import os
import argclass

os.environ["DB_PASSWORD"] = "secret123"

class Parser(argclass.Parser):
    password: str = argclass.Secret(env_var="DB_PASSWORD")

parser = Parser()
parser.parse_args([])

# Value accessible for use in code
assert parser.password == "secret123"

# But masked in repr() - safe for logging
assert "secret123" not in repr(parser.password)

# Remove from environment
parser.sanitize_env()
assert "DB_PASSWORD" not in os.environ
```

## Common Patterns

### CLI Application Structure

<!--- name: test_cheat_app_structure --->
```python
import argclass

class App(argclass.Parser):
    """My CLI application."""
    config: str | None = argclass.Argument("-c", "--config")
    verbose: bool = argclass.Argument("-v", default=False)

    def __call__(self) -> int:
        if self.verbose:
            print("Verbose mode enabled")
        return 0

def main() -> int:
    app = App()
    app.parse_args([])
    return app()

result = main()
assert result == 0
```

### Shell Completion (argcomplete)

<!--- name: test_cheat_argcomplete --->
```python
import argclass

class CLI(argclass.Parser):
    name: str
    format: str = argclass.Argument(choices=["json", "yaml"], default="json")

cli = CLI()

# Add shell completion support
try:
    import argcomplete
    argcomplete.autocomplete(cli.create_parser())
except ImportError:
    pass

cli.parse_args(["--name", "test"])
assert cli.name == "test"
```

See [Integrations](integrations.md#shell-completions) for bash/zsh setup.

### Reusable Groups

<!--- name: test_cheat_reusable --->
```python
import argclass

class LoggingGroup(argclass.Group):
    """Reusable logging configuration."""
    level: str = argclass.Argument(
        choices=["debug", "info", "warning", "error"],
        default="info"
    )
    file: str | None = None

# Reuse in multiple parsers
class ServerApp(argclass.Parser):
    port: int = 8080
    logging = LoggingGroup()

class WorkerApp(argclass.Parser):
    concurrency: int = 4
    logging = LoggingGroup()

server = ServerApp()
server.parse_args(["--logging-level", "debug"])
assert server.logging.level == "debug"

worker = WorkerApp()
worker.parse_args(["--logging-level", "warning"])
assert worker.logging.level == "warning"
```

## Quick Reference Table

| Pattern | Syntax | CLI Usage |
|---------|--------|-----------|
| Required arg | `name: str` | `--name value` |
| Optional arg | `name: str = "default"` | `--name value` |
| Boolean flag | `flag: bool = False` | `--flag` |
| Short alias | `Argument("-n", "--name")` | `-n value` |
| Multiple values | `items: list[str]` | `--items a b c` |
| Positional | `Argument("name")` | `value` |
| Choices | `Literal["a", "b"]` | `--arg a` |
| Env var | `Argument(env_var="VAR")` | `VAR=x cmd` |
| Secret | `Secret(env_var="VAR")` | `VAR=x cmd` |
| Help text | `Argument(help="...")` | `--help` |
| Group | `grp = MyGroup()` | `--grp-field value` |
| Subcommand | `cmd = MyCommand()` | `cmd --arg value` |

## Priority Order

```
CLI arguments  >  Environment variables  >  Config files  >  Code defaults
     (highest)                                                    (lowest)
```

## Actions Reference

| Action | Effect | Usage |
|--------|--------|-------|
| `STORE` | Store value (default) | `--arg value` |
| `STORE_TRUE` | Set to True | `--flag` |
| `STORE_FALSE` | Set to False | `--no-flag` |
| `COUNT` | Count occurrences | `-vvv` → 3 |
| `APPEND` | Append to list | `--item a --item b` |

## Nargs Reference

| Nargs | Meaning | Example |
|-------|---------|---------|
| `None` | Single value | `--arg value` |
| `?` | Zero or one | `--arg` or `--arg value` |
| `*` | Zero or more | `--args` or `--args a b` |
| `+` | One or more | `--args a b c` |
| `N` (int) | Exactly N | `--point 1.0 2.0 3.0` |
