# CLAUDE.md

## What is argclass

Declarative CLI parser for Python over `argparse`. Type hints → CLI args automatically. `str`→string, `bool`→flag, `Optional[T]`→optional, `list[T]`→multi-value, `Literal[...]`→choices. Priority: defaults < config files < env vars < CLI args. Zero deps, stdlib only, Python 3.10-3.14.

## Commands

```bash
uv sync                                    # install deps
uv run pytest -vv --cov=argclass --cov-report=term-missing --doctest-modules tests  # full test suite
uv run pytest tests/test_simple.py::TestClassName::test_method -vv  # single test
uv run ruff check                          # lint
uv run ruff format --check                 # verify formatting
uv run ruff format                         # apply formatting
uv run mypy                                # type checking
```

## Examples

### Minimal parser

```python
import argclass

class CLI(argclass.Parser):
    host: str = "localhost"      # --host (default: localhost)
    port: int = 8080             # --port (default: 8080)
    verbose: bool = False        # --verbose flag (store_true)

parser = CLI()
parser.parse_args()
```

### Optional, list, and literal types

```python
from typing import Optional, Literal
import argclass

class CLI(argclass.Parser):
    name: Optional[str] = None               # --name (optional)
    tags: list[str] = argclass.Argument(      # --tags a b c
        nargs=argclass.Nargs.ONE_OR_MORE,
    )
    mode: Literal["fast", "slow"] = "fast"   # --mode {fast,slow}
```

### Argument groups

```python
import argclass

class Database(argclass.Group):
    host: str = "localhost"
    port: int = 5432

class CLI(argclass.Parser):
    debug: bool = False
    db: Database = Database(title="Database options")

parser = CLI()
parser.parse_args()
print(parser.db.host, parser.db.port)
```

### Subcommands

```python
import argclass

class Serve(argclass.Parser):
    port: int = 8080

class Deploy(argclass.Parser):
    target: str = "production"

class CLI(argclass.Parser):
    serve = Serve()
    deploy = Deploy()
```

### Environment variables and secrets

```python
import argclass

class CLI(argclass.Parser):
    db_url: str = argclass.Argument(env_var="DATABASE_URL")
    api_key: str = argclass.Secret()  # masked in repr/logs

# auto_env_var_prefix generates env vars from arg names
parser = CLI(auto_env_var_prefix="APP_")
parser.parse_args()
parser.sanitize_env(only_secrets=True)
```

### Testing parsers

```python
class CLI(argclass.Parser):
    debug: bool = False
    db: Database = Database(title="Database options")

parser = CLI()
parser.parse_args(["--debug", "--db-host=127.0.0.1", "--db-port", "9876"])
assert parser.debug is True
assert parser.db.host == "127.0.0.1"
```

## Architecture

Metaclass-driven: `Meta` metaclass in `parser.py` processes annotations at class definition time, creating `__arguments__`, `__argument_groups__`, `__subparsers__`.

- **`parser.py`** — `Meta`, `Base`, `Parser`, `Group`, `Destination`. Argparse integration, config files, env vars.
- **`factory.py`** — `Argument`, `ArgumentSingle`, `ArgumentSequence`, `EnumArgument`, `Secret`, `Config`, `LogLevel` factories.
- **`store.py`** — `StoreMeta`/`Store` for typed field storage; `ArgumentBase`/`TypedArgument` extend it.
- **`defaults.py`** — Config file parsers (INI/JSON/TOML) implementing `AbstractDefaultsParser`.
- **`actions.py`** — Custom argparse `Action` subclasses.
- **`secret.py`** — `SecretString` masks values in repr/logging.
- **`exceptions.py`** — `ArgclassError` hierarchy with suggestions.
- **`types.py`** — Type aliases, enums (`Actions`, `Nargs`, `LogLevelEnum`), constants.
- **`utils.py`** — `parse_bool`, `read_ini_configs`, type introspection helpers, annotation merging.

## Code Style

- Line length: 80 chars (ruff). Rules: E, F, W, C90 (C901 ignored)
- mypy strict for `argclass/`, relaxed for `tests/`
- Build backend: hatchling
