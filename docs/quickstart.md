# Quick Start

This guide will get you started with argclass in 5 minutes.

## Installation

```bash
pip install argclass
```

## Your First Parser

Create a simple command-line parser by defining a class:

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

## How It Works

1. **Class attributes become arguments** - Each annotated attribute becomes a CLI argument
2. **Types are enforced** - `int` annotations automatically convert string input to integers
3. **Defaults make arguments optional** - `count: int = 1` means `--count` is optional
4. **No default means required** - `name: str` has no default, so `--name` is required

## Adding Help Text

Use `argclass.Argument()` to add descriptions:

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

## Short Aliases

Add short flags with aliases:

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

## Boolean Flags

Boolean arguments with `False` default become flags:

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

## Multiple Values

Use `list[T]` for arguments that accept multiple values:

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

## Environment Variables

Read defaults from environment variables:

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

## Next Steps

- [Tutorial](tutorial.md) - Complete walkthrough of all features
- [Arguments](arguments.md) - Detailed argument configuration
- [Config Files](config-files.md) - Load defaults from INI/JSON files
- [API Reference](api.md) - Complete API documentation
