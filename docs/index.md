# argclass

```{only} html
[![PyPI Version](https://img.shields.io/pypi/v/argclass.svg)](https://pypi.python.org/pypi/argclass/)
[![Python Versions](https://img.shields.io/pypi/pyversions/argclass.svg)](https://pypi.python.org/pypi/argclass/)
[![Coverage](https://coveralls.io/repos/github/mosquito/argclass/badge.svg?branch=master)](https://coveralls.io/github/mosquito/argclass?branch=master)
[![Tests](https://github.com/mosquito/argclass/workflows/tests/badge.svg)](https://github.com/mosquito/argclass/actions?query=workflow%3Atests)
[![License](https://img.shields.io/pypi/l/argclass.svg)](https://pypi.python.org/pypi/argclass/)

:::{note}
For offline access, you can download the full documentation as a PDF: <a href="_static/argclass.pdf">**Download PDF Documentation**</a>
:::
```

**Declarative CLI parser with type hints, config files, and environment variables.**

argclass is a Python library that transforms ordinary Python classes into
fully-featured command-line interface parsers. By leveraging Python's type
hints and class syntax, argclass eliminates the boilerplate code typically
associated with argument parsing while providing type safety, IDE autocompletion,
and seamless integration with configuration files and environment variables.

**Key features:**

- **Type-safe arguments** - Define arguments using Python type hints. argclass
  automatically validates and converts values to the correct types.
- **Pure OOP design** - Unlike decorator-based libraries, argclass uses real
  classes. This enables proper inheritance and composition
  for building complex CLIs. Parsers are testable objects you can instantiate,
  extend, and compose without decorator magic.
- **Zero dependencies** - Built entirely on Python's standard library `argparse`.
  No external packages required.
- **IDE support** - Full autocompletion and type checking in modern editors
  like VS Code and PyCharm.
- **Multiple config formats** - Load defaults from INI, JSON, or TOML configuration
  files with automatic type conversion. Each format has built-in support with
  no additional dependencies (TOML requires Python 3.11+ or `tomli` package).
- **Environment variables** - Read configuration from environment variables
  with optional prefix support for namespacing.
- **Secret handling** - Built-in support for sensitive values that are masked
  in logs and can be sanitized from the environment.
- **Reusable groups** - Define argument groups once and reuse them across
  multiple parsers for consistent configuration.
- **Subcommands** - Build multi-command CLIs like `git` or `docker` with
  nested parser classes.
- **Extensible architecture** - Create custom argument types, converters,
  and configuration file parsers. Integrate with argparse extensions like
  `rich_argparse` for enhanced help formatting.
- **argparse compatible** - Full compatibility with the standard library
  `argparse`. Use any argparse extension or migrate existing code gradually.

```python
import argclass

class Server(argclass.Parser):
    host: str = "127.0.0.1"
    port: int = 8080
    debug: bool = False

server = Server()
server.parse_args()
print(f"Starting server on {server.host}:{server.port}")
```

```bash
$ python server.py --host 0.0.0.0 --port 9000 --debug
Starting server on 0.0.0.0:9000
```

## Why argclass?

argclass bridges the gap between simple argument parsing and full-featured
CLI frameworks. Unlike raw `argparse`, argclass provides type safety and
IDE support. Unlike decorator-based frameworks like Click or Typer, argclass
uses pure OOP: your parsers are real classes with inheritance, composition,
and easy testability. And with zero dependencies, it stays close to Python's
standard library.

| Feature                 | argclass | argparse | click/typer |
|-------------------------|----------|----------|-------------|
| Type hints → arguments  | Yes      | No       | Yes         |
| Class-based (OOP)       | Yes      | No       | Decorators  |
| IDE autocompletion      | Yes      | No       | Yes         |
| Config file support     | Built-in | No       | No          |
| Environment variables   | Built-in | No       | Plugin      |
| Secret masking          | Built-in | No       | No          |
| Argument groups         | Reusable | Limited  | No          |
| Dependencies            | stdlib   | stdlib   | Many        |

```{only} html
::::{grid} 3
:gutter: 3

:::{grid-item-card} Type-Safe
:class-card: sd-border-0

Define arguments with Python type hints. Get automatic validation and conversion.
:::

:::{grid-item-card} Zero Dependencies
:class-card: sd-border-0

Built on stdlib `argparse`. No external dependencies required.
:::

:::{grid-item-card} IDE Support
:class-card: sd-border-0

Full autocompletion and type checking in your editor.
:::

::::
```

## How to Read This Documentation

All code examples in this documentation are automatically tested to ensure they
work correctly. This means examples are written in a specific way that may look
slightly different from real-world usage.

### parse_args() with explicit arguments

Throughout the documentation, you'll see examples like:

<!--- name: test_index_parse_args_explicit --->
```python
import argclass

class Parser(argclass.Parser):
    host: str = "localhost"
    port: int = 8080

parser = Parser()
parser.parse_args(["--host", "example.com", "--port", "9000"])
assert parser.host == "example.com"
```

**This is for testing purposes only.** In real applications, you would call
`parse_args()` without arguments, which reads from `sys.argv` (the command line):

<!--- name: test_index_parse_args_real --->
```python
import argclass

class Parser(argclass.Parser):
    host: str = "localhost"

parser = Parser()
parser.parse_args([])  # In real code: parser.parse_args()
# Real usage reads from command line: python app.py --host example.com
```

The explicit list form `parse_args(["--arg", "value"])` is used in documentation
so examples can be tested automatically without requiring actual command-line
execution.

:::{note}
Experienced users may pass arguments directly in specific scenarios, such as
filtering `sys.argv`, implementing argument preprocessing, or building nested
CLI tools. However, this is not a common pattern for typical applications.
:::

### Assert statements

Examples often end with `assert` statements for verification:

<!--- name: test_index_assert_example --->
```python
import argclass

class Parser(argclass.Parser):
    name: str

parser = Parser()
parser.parse_args(["--name", "Alice"])
assert parser.name == "Alice"  # Verification for testing
```

In your actual code, you would simply use the parsed values:

<!--- name: test_index_real_usage --->
```python
import argclass

class Parser(argclass.Parser):
    name: str = "World"

parser = Parser()
parser.parse_args([])
message = f"Hello, {parser.name}!"
assert message == "Hello, World!"
```

### Environment variables and temporary files

Examples that demonstrate environment variables set them programmatically:

<!--- name: test_index_env_example --->
```python
import os
import argclass

os.environ["MY_API_KEY"] = "secret123"  # Set for testing

class Parser(argclass.Parser):
    api_key: str = argclass.Argument(env_var="MY_API_KEY")

parser = Parser()
parser.parse_args([])
assert parser.api_key == "secret123"

del os.environ["MY_API_KEY"]  # Cleanup after test
```

In production, environment variables would be set externally (by your shell,
container orchestrator, or deployment system), not in your Python code.

Similarly, config file examples use `NamedTemporaryFile` to create test files.
In real applications, you would reference actual configuration file paths:

<!--- name: test_index_config_example --->
```python
import argclass
from tempfile import NamedTemporaryFile
from pathlib import Path

class Parser(argclass.Parser):
    host: str = "localhost"

# Documentation uses temporary files for testing:
with NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
    f.write("[DEFAULT]\nhost = example.com\n")
    config_path = f.name

parser = Parser(config_files=[config_path])
parser.parse_args([])
assert parser.host == "example.com"

Path(config_path).unlink()

# Real applications use actual paths:
# parser = Parser(config_files=["/etc/myapp.ini", "~/.config/myapp.ini"])
```

### Real-world usage pattern

Here's what a complete real-world application looks like:

<!--- name: test_index_real_world --->
```python
import argclass

class MyApp(argclass.Parser):
    """My application description."""
    host: str = "localhost"
    port: int = 8080
    debug: bool = False

def main():
    app = MyApp()
    app.parse_args([])  # Real code: app.parse_args()
    return f"Starting on {app.host}:{app.port}"

result = main()
assert "localhost:8080" in result
```

Run it with: `python myapp.py --host 0.0.0.0 --port 9000 --debug`

## Installation

argclass requires Python 3.10 or later and has no external dependencies.

### Using pip

The simplest way to install argclass:

```console
pip install argclass
```

### Using uv

For faster installation with [uv](https://github.com/astral-sh/uv):

```console
uv add argclass
```

Or in a virtual environment:

```console
uv pip install argclass
```

### Using Poetry

Add argclass to your Poetry project:

```console
poetry add argclass
```

### From Source

Clone the repository and install in development mode:

```console
git clone https://github.com/mosquito/argclass.git
cd argclass
pip install -e .
```

### Verifying Installation

After installation, verify it works:

```console
$ python -m argclass --help
usage: python -m argclass [-h] [--verbose] [--secret-key SECRET_KEY] {greet} ...

This code produces this help:

import argparse
import sys
from pathlib import Path

import argclass

class GreetCommand(argclass.Parser):
    user: str = argclass.Argument("user", help="User to greet")

    def __call__(self) -> int:
        print(f"Hello, {self.user}!")
        return 0

class Parser(argclass.Parser):
    verbose: bool = False
    secret_key: str = argclass.Secret(help="Secret API key")
    greet = GreetCommand()

def main() -> None:
    parser = Parser(
        prog=f"{Path(sys.executable).name} -m argclass",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "This code produces this help:\n\n```"
            f"python\n{open(__file__).read().strip()}\n```"
        ),
    )
    parser.parse_args()
    parser.sanitize_env()
    exit(parser())

if __name__ == "__main__":
    main()

positional arguments:
{greet}

options:
-h, --help            show this help message and exit
--verbose             (default: False)
--secret-key SECRET_KEY
Secret API key

$ python -m argclass greet Guido
Hello, Guido!
```

## Quick Examples

### Groups

Organize related arguments into reusable groups. Group arguments are
automatically prefixed with the group name:

<!--- name: test_groups_basic --->
```python
import argclass

class DatabaseGroup(argclass.Group):
    host: str = "localhost"
    port: int = 5432

class Parser(argclass.Parser):
    debug: bool = False
    db = DatabaseGroup()

parser = Parser()
parser.parse_args(["--db-host", "prod.db", "--db-port", "5432"])
assert parser.db.host == "prod.db"
```

### Config Files

Load defaults from INI, JSON, or TOML configuration files. Values from
config files can be overridden by environment variables or CLI arguments:

<!--- name: test_config_files_basic --->
```python
import argclass

class Parser(argclass.Parser):
    host: str = "localhost"
    port: int = 8080

parser = Parser(config_files=[
    "/etc/myapp.ini",
    "~/.config/myapp.ini",
])

# Reads from config files in order, then environment, then CLI
```

### Environment Variables

Read configuration from environment variables. Use `auto_env_var_prefix`
to automatically generate environment variable names from argument names:

<!--- name: test_environment_auto_prefix --->
```python
import argclass

class Parser(argclass.Parser):
    host: str = "localhost"
    port: int = 8080

parser = Parser(auto_env_var_prefix="MYAPP_")
# Reads from MYAPP_HOST, MYAPP_PORT
```

## Get Started

New to argclass? Here's the recommended learning path:

### Quick Start (5 minutes)

The [Quick Start](quickstart.md) guide covers the essentials:

- Defining arguments with type hints
- Required vs optional arguments
- Boolean flags and short aliases
- Reading from environment variables
- Basic help text customization

This is enough to build simple CLI tools and understand argclass fundamentals.

### Tutorial (30 minutes)

The [Tutorial](tutorial.md) walks through building a complete backup tool:

- Starting with a basic parser structure
- Adding options with defaults and help text
- Organizing arguments into groups
- Creating subcommands for different operations
- Loading configuration from files
- Reading secrets from environment variables

By the end, you'll understand how all argclass features work together.

### Examples Gallery

The [Examples](examples.md) page provides ready-to-use patterns:

- Simple CLI tools with options and flags
- Multi-command CLIs (git-style subcommands)
- Full configuration stack (config + env + CLI)
- File processing utilities
- HTTP client with authentication
- Database migration tools
- Daemon/service configuration
- Testing patterns for your CLI

Each example includes explanations and can be copied directly into your project.

### Reference Documentation

Once comfortable with the basics, explore the User Guide for detailed coverage:

- [Arguments](arguments.md) - All argument types, actions, and customization options
- [Groups](groups.md) - Organizing and reusing argument sets
- [Subparsers](subparsers.md) - Building multi-command CLIs
- [Config Files](config-files.md) - INI, JSON, and TOML configuration
- [Environment](environment.md) - Environment variable integration
- [Secrets](secrets.md) - Handling sensitive values securely

```{only} html
::::{grid} 2
:gutter: 3

:::{grid-item-card} Quick Start
:link: quickstart
:link-type: doc
:class-card: sd-rounded-3

**5 minute introduction**

Learn the basics: arguments, types, flags, and environment variables.
:::

:::{grid-item-card} Tutorial
:link: tutorial
:link-type: doc
:class-card: sd-rounded-3

**Complete walkthrough**

Build a real CLI application step by step.
:::

::::
```

---

## Documentation

```{toctree}
:maxdepth: 2
:caption: Getting Started

quickstart
tutorial
examples
```

```{toctree}
:maxdepth: 2
:caption: User Guide

arguments
groups
subparsers
config-files
environment
secrets
security
integrations
```

```{toctree}
:maxdepth: 2
:caption: Help

errors
pitfalls
```

```{toctree}
:maxdepth: 2
:caption: Reference

api
```

## Indices and tables

- {ref}`genindex`
- {ref}`modindex`
- {ref}`search`
