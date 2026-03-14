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
