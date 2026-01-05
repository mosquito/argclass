# API Reference

Complete API documentation for argclass.

## Quick Reference

Most users only need these:

| What you want | What to use |
|---------------|-------------|
| Create a CLI parser | `class MyApp(argclass.Parser)` |
| Group related arguments | `class MyGroup(argclass.Group)` |
| Customize an argument | `argclass.Argument(...)` |
| Handle sensitive values | `argclass.Secret(...)` or `argclass.Argument(..., secret=True)` |
| Load config file argument | `argclass.Config(...)` |
| Set log level argument | `argclass.LogLevel` |

## Primary API

These are the main classes and functions you'll use in most applications.

### Parser

The base class for creating CLI parsers. Define arguments as class attributes
with type hints.

<!--- name: test_api_parser --->
```python
import argclass

class MyApp(argclass.Parser):
    name: str                    # Required argument
    count: int = 1               # Optional with default
    verbose: bool = False        # Boolean flag

app = MyApp()
app.parse_args(["--name", "test"])
assert app.name == "test"
assert app.count == 1
assert app.verbose is False
```

```{eval-rst}
.. autoclass:: argclass.Parser
   :members:
   :show-inheritance:
```

### Group

Bundle related arguments under a common prefix. Groups can be reused across
multiple parsers.

<!--- name: test_api_group --->
```python
import argclass

class DatabaseGroup(argclass.Group):
    host: str = "localhost"
    port: int = 5432

class MyApp(argclass.Parser):
    db = DatabaseGroup()  # Arguments: --db-host, --db-port

app = MyApp()
app.parse_args(["--db-host", "prod.example.com"])
assert app.db.host == "prod.example.com"
assert app.db.port == 5432
```

```{eval-rst}
.. autoclass:: argclass.Group
   :members:
   :show-inheritance:
```

### Argument

Customize argument behavior: add help text, aliases, choices, and more.

<!--- name: test_api_argument --->
```python
import argclass

class MyApp(argclass.Parser):
    name: str = argclass.Argument(
        "-n", "--name",
        help="User name",
    )
    level: str = argclass.Argument(
        default="info",
        choices=["debug", "info", "warning", "error"],
    )

app = MyApp()
app.parse_args(["-n", "Alice", "--level", "debug"])
assert app.name == "Alice"
assert app.level == "debug"
```

```{eval-rst}
.. autofunction:: argclass.Argument
```

### Secret

Handle sensitive values that should be masked in logs and removed from
environment after parsing.

<!--- name: test_api_secret --->
```python
import os
import argclass

os.environ["TEST_API_KEY"] = "secret123"

class MyApp(argclass.Parser):
    api_key: str = argclass.Secret(env_var="TEST_API_KEY")

app = MyApp()
app.parse_args([])
assert str(app.api_key) == "******"  # Masked in string representation
assert app.api_key == "secret123"    # But actual value is accessible
app.sanitize_env()                   # Remove from environment
assert "TEST_API_KEY" not in os.environ
```

```{eval-rst}
.. autofunction:: argclass.Secret
```

### SecretString

The type returned for `Secret` arguments. Masks value in `str()` and `repr()`.

```{eval-rst}
.. autoclass:: argclass.SecretString
   :members:
   :special-members: __str__, __repr__, __eq__
```

---

## Configuration Files

Load defaults from INI, JSON, or TOML configuration files.

### Config

Add a `--config` argument that loads structured data from a file.
Access values via dict-like interface (`parser.config["key"]`).

<!--- name: test_api_config --->
```python
import argclass
from pathlib import Path
from tempfile import NamedTemporaryFile

class MyApp(argclass.Parser):
    config = argclass.Config(config_class=argclass.JSONConfig)
    verbose: bool = False

# Create a temporary config file
with NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
    f.write('{"database": {"host": "example.com", "port": 9000}}')
    config_path = f.name

app = MyApp()
app.parse_args(["--config", config_path])

# Access config data via dict-like interface
assert app.config["database"]["host"] == "example.com"
assert app.config["database"]["port"] == 9000

Path(config_path).unlink()
```

:::{tip}
For loading defaults into parser attributes, use `config_files` parameter instead.
See [Config File Parsers](#config-file-parsers).
:::

```{eval-rst}
.. autofunction:: argclass.Config
```

### Config Argument Classes

| Class | Format | Usage |
|-------|--------|-------|
| `INIConfig` | INI files | `config_class=argclass.INIConfig` |
| `JSONConfig` | JSON files | `config_class=argclass.JSONConfig` |
| `TOMLConfig` | TOML files | `config_class=argclass.TOMLConfig` |

```{eval-rst}
.. autoclass:: argclass.INIConfig
   :members:
   :show-inheritance:
```

```{eval-rst}
.. autoclass:: argclass.JSONConfig
   :members:
   :show-inheritance:
```

:::{note}
TOML requires `tomllib` (Python 3.11+) or `tomli` package (Python 3.10).
:::

```{eval-rst}
.. autoclass:: argclass.TOMLConfig
   :members:
   :show-inheritance:
```

### Config File Parsers

Used with `config_parser_class` parameter in `Parser()` to load defaults
from config files at parser initialization.

<!--- name: test_api_config_parser --->
```python
import argclass
from pathlib import Path
from tempfile import NamedTemporaryFile

class MyApp(argclass.Parser):
    host: str = "localhost"
    port: int = 8080

# Create a temporary config file
with NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
    f.write('{"host": "db.example.com", "port": 5432}')
    config_path = f.name

app = MyApp(
    config_files=[config_path],
    config_parser_class=argclass.JSONDefaultsParser,
)
app.parse_args([])
assert app.host == "db.example.com"
assert app.port == 5432

Path(config_path).unlink()
```

| Class | Format |
|-------|--------|
| `INIDefaultsParser` | INI files (default) |
| `JSONDefaultsParser` | JSON files |
| `TOMLDefaultsParser` | TOML files |

```{eval-rst}
.. autoclass:: argclass.INIDefaultsParser
   :members:
   :show-inheritance:
```

```{eval-rst}
.. autoclass:: argclass.JSONDefaultsParser
   :members:
   :show-inheritance:
```

```{eval-rst}
.. autoclass:: argclass.TOMLDefaultsParser
   :members:
   :show-inheritance:
```

---

## Pre-built Arguments

### LogLevel

A pre-configured argument for log levels. Accepts level names and returns
the corresponding `logging` module constant.

<!--- name: test_api_loglevel --->
```python
import argclass
import logging

class MyApp(argclass.Parser):
    log_level: int = argclass.LogLevel

app = MyApp()
app.parse_args(["--log-level", "debug"])
assert app.log_level == logging.DEBUG

app.parse_args(["--log-level", "WARNING"])
assert app.log_level == logging.WARNING
```

Accepts: `debug`, `info`, `warning`, `error`, `critical` (case-insensitive).

```{eval-rst}
.. autoclass:: argclass.LogLevelEnum
   :members:
   :undoc-members:
```

---

## Enums and Constants

### Actions

Argument actions (mirrors `argparse` actions).

| Action | Description |
|--------|-------------|
| `STORE` | Store the value (default) |
| `STORE_TRUE` | Store `True` when flag is present |
| `STORE_FALSE` | Store `False` when flag is present |
| `APPEND` | Append value to a list |
| `COUNT` | Count occurrences |

```{eval-rst}
.. autoclass:: argclass.Actions
   :members:
   :undoc-members:
```

### Nargs

Number of arguments constants.

| Value | Meaning |
|-------|---------|
| `OPTIONAL` (`?`) | Zero or one argument |
| `ZERO_OR_MORE` (`*`) | Zero or more arguments |
| `ONE_OR_MORE` (`+`) | One or more arguments |
| `REMAINDER` | All remaining arguments |

```{eval-rst}
.. autoclass:: argclass.Nargs
   :members:
   :undoc-members:
```

---

## Utility Functions

### parse_bool

Parse boolean strings from environment variables or config files.

<!--- name: test_api_parse_bool --->
```python
from argclass import parse_bool

assert parse_bool("true") is True
assert parse_bool("yes") is True
assert parse_bool("1") is True
assert parse_bool("on") is True

assert parse_bool("false") is False
assert parse_bool("no") is False
assert parse_bool("0") is False
assert parse_bool("off") is False
```

```{eval-rst}
.. autofunction:: argclass.parse_bool
```

### read_configs

Read and merge multiple configuration files.

```{eval-rst}
.. autofunction:: argclass.read_configs
```

---

## Advanced / Internal

These classes are primarily for advanced use cases or extending argclass.

### Base

Abstract base class for both `Parser` and `Group`.

```{eval-rst}
.. autoclass:: argclass.Base
   :members:
   :show-inheritance:
```

### AbstractDefaultsParser

Base class for implementing custom config file parsers.

```{eval-rst}
.. autoclass:: argclass.AbstractDefaultsParser
   :members:
   :show-inheritance:
```

### ConfigArgument

Base class for config file argument types.

```{eval-rst}
.. autoclass:: argclass.ConfigArgument
   :members:
   :show-inheritance:
```

### ConfigAction

Action class for config file arguments.

```{eval-rst}
.. autoclass:: argclass.ConfigAction
   :members:
```

### TypedArgument

Internal class representing a typed argument.

```{eval-rst}
.. autoclass:: argclass.TypedArgument
   :members:
   :show-inheritance:
```

### Store

Internal storage for argument metadata.

```{eval-rst}
.. autoclass:: argclass.Store
   :members:
```

### Specialized Argument Functions

```{eval-rst}
.. autofunction:: argclass.ArgumentSingle
```

```{eval-rst}
.. autofunction:: argclass.ArgumentSequence
```

```{eval-rst}
.. autofunction:: argclass.EnumArgument
```
