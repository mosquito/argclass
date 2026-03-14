# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

argclass is a declarative CLI argument parser for Python built on top of `argparse`. It uses class-based definitions with type hints to define CLI interfaces. Zero runtime dependencies, stdlib only. Python 3.10-3.14.

## Commands

```bash
# Install dependencies
uv sync

# Run full test suite with coverage and doctests (matches CI)
uv run pytest -vv --cov=argclass --cov-report=term-missing --doctest-modules tests

# Run a single test
uv run pytest tests/test_simple.py::TestClassName::test_method -vv

# Lint and format
uv run ruff check
uv run ruff format --check   # verify formatting
uv run ruff format            # apply formatting

# Type checking
uv run mypy
```

## Architecture

**Metaclass-driven declarative parsing:** Users define CLI parsers by subclassing `Parser` and declaring typed class attributes. The `Meta` metaclass (`parser.py`) processes annotations at class definition time, creating argument mappings (`__arguments__`, `__argument_groups__`, `__subparsers__`).

Key modules:
- **`parser.py`** — Core classes: `Meta` (metaclass), `Base`, `Parser`, `Group`, `Destination`. Handles argparse integration, config file loading, env var resolution, and the priority chain: defaults < config files < env vars < CLI args.
- **`factory.py`** — Factory functions (`Argument`, `ArgumentSingle`, `ArgumentSequence`, `EnumArgument`, `Secret`, `Config`, `LogLevel`) that create `TypedArgument`/`ConfigArgument` instances with proper typing.
- **`store.py`** — `StoreMeta` metaclass and `Store` base class for typed field storage. `ArgumentBase` and `TypedArgument` extend `Store`.
- **`defaults.py`** — Config file parsers (`INI/JSON/TOMLDefaultsParser`) implementing `AbstractDefaultsParser`.
- **`actions.py`** — Custom argparse `Action` subclasses for config file loading.
- **`secret.py`** — `SecretString` that masks values in repr/logging via stack inspection.
- **`exceptions.py`** — `ArgclassError` hierarchy with structured error messages and suggestions.

Type unwrapping in `Meta`: `Optional[T]` → optional arg, `list[T]`/`set[T]` → nargs, `Literal[...]` → choices, `bool` → store_true/store_false.

## Code Style

- Line length: 80 characters (ruff)
- Ruff rules: E, F, W, C90 (C901 ignored)
- mypy strict mode enabled for `argclass/`; relaxed (`disallow_untyped_defs=false`) for `tests/`
- Build backend: hatchling
