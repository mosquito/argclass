# Quick Start

Get started with argclass in 5 minutes.

## Installation

```console
pip install argclass
```

## Basic Usage

Define a class with type hints to create a CLI parser:

```python
import argclass

class Greeter(argclass.Parser):
    name: str          # Required argument
    count: int = 1     # Optional with default

greeter = Greeter()
greeter.parse_args()
print(f"Hello, {greeter.name}!" * greeter.count)
```

```console
$ python greeter.py --name World --count 3
Hello, World!Hello, World!Hello, World!
```

## Examples

### Required and Optional Arguments

Arguments without defaults are required - the parser will exit with an error
if they're not provided. Arguments with defaults are optional. Type hints
determine how values are parsed and validated.

<!--- name: test_quickstart_first_parser --->
```python
import argclass

class Greeter(argclass.Parser):
    name: str
    count: int = 1

greeter = Greeter()
greeter.parse_args(["--name", "World", "--count", "3"])

assert greeter.name == "World"
assert greeter.count == 3
```

### Help Text

Use `argclass.Argument()` to add help text that appears in `--help` output.
Good help text makes your CLI self-documenting and easier for users to learn.

<!--- name: test_quickstart_help_text --->
```python
import argclass

class Greeter(argclass.Parser):
    name: str = argclass.Argument(help="Name to greet")
    count: int = argclass.Argument(default=1, help="Number of times to greet")

greeter = Greeter()
greeter.parse_args(["--name", "Alice"])

assert greeter.name == "Alice"
assert greeter.count == 1
```

### Short Aliases

Add short single-letter aliases like `-n` for frequently used arguments.
Users can then choose between `--name World` or the shorter `-n World`.

<!--- name: test_quickstart_aliases --->
```python
import argclass

class Greeter(argclass.Parser):
    name: str = argclass.Argument("-n", "--name", help="Name to greet")
    count: int = argclass.Argument("-c", "--count", default=1)

greeter = Greeter()
greeter.parse_args(["-n", "World", "-c", "3"])

assert greeter.name == "World"
assert greeter.count == 3
```

Usage: `python greeter.py -n World -c 3`

### Boolean Flags

Boolean arguments with `False` defaults become flags: `--verbose` sets
the value to `True`. No value is needed - the flag's presence is enough.

<!--- name: test_quickstart_bool_flags --->
```python
import argclass

class App(argclass.Parser):
    verbose: bool = False
    debug: bool = False

app = App()
app.parse_args(["--verbose", "--debug"])

assert app.verbose is True
assert app.debug is True
```

Usage: `python app.py --verbose --debug`

### Multiple Values

Use `list[T]` type hints to accept multiple values. Users can provide
several values after the flag: `--files a.txt b.txt c.txt`.

<!--- name: test_quickstart_multiple_values --->
```python
import argclass

class FileProcessor(argclass.Parser):
    files: list[str]
    exclude: list[str] = []

processor = FileProcessor()
processor.parse_args(["--files", "a.txt", "b.txt", "c.txt", "--exclude", "b.txt"])

assert processor.files == ["a.txt", "b.txt", "c.txt"]
assert processor.exclude == ["b.txt"]
```

Usage: `python processor.py --files a.txt b.txt c.txt --exclude b.txt`

### Environment Variables

Read defaults from environment variables with `env_var`. This is useful for
containerized deployments where configuration comes from the environment.

:::{tip}
For secrets, use `argclass.Secret(env_var="...")` and call `parser.sanitize_env()`
after parsing. This removes secrets from the environment, preventing child
processes from accessing them. See [Secrets](secrets.md).
:::

<!--- name: test_quickstart_env_vars --->
```python
import os
import argclass

os.environ["TEST_DB_HOST"] = "prod.example.com"
os.environ["TEST_DB_PORT"] = "5432"

class Database(argclass.Parser):
    host: str = argclass.Argument(env_var="TEST_DB_HOST", default="localhost")
    port: int = argclass.Argument(env_var="TEST_DB_PORT", default=5432)

db = Database()
db.parse_args([])

assert db.host == "prod.example.com"
assert db.port == 5432

# Cleanup
del os.environ["TEST_DB_HOST"]
del os.environ["TEST_DB_PORT"]
```

Usage: `TEST_DB_HOST=prod.example.com python app.py`

## Quick Reference

| Pattern | Syntax | Result |
|---------|--------|--------|
| Required arg | `name: str` | `--name` (required) |
| Optional arg | `name: str = "default"` | `--name` (optional) |
| Boolean flag | `debug: bool = False` | `--debug` |
| Multiple values | `files: list[str]` | `--files a b c` |
| Help text | `argclass.Argument(help="...")` | Shows in `--help` |
| Short alias | `argclass.Argument("-n", "--name")` | `-n` or `--name` |
| Env variable | `argclass.Argument(env_var="VAR")` | Reads from `$VAR` |

## Next Steps

::::{grid} 2
:gutter: 3

:::{grid-item-card} Tutorial
:link: tutorial
:link-type: doc

Complete walkthrough of all features with practical examples.
:::

:::{grid-item-card} Config Files
:link: config-files
:link-type: doc

Load defaults from INI, JSON, or TOML configuration files.
:::

:::{grid-item-card} Arguments
:link: arguments
:link-type: doc

Detailed argument configuration: types, choices, validators.
:::

:::{grid-item-card} API Reference
:link: api
:link-type: doc

Complete API documentation for all classes and functions.
:::

::::
