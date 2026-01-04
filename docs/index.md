# argclass

[![PyPI Version](https://img.shields.io/pypi/v/argclass.svg)](https://pypi.python.org/pypi/argclass/)
[![Python Versions](https://img.shields.io/pypi/pyversions/argclass.svg)](https://pypi.python.org/pypi/argclass/)
[![Coverage](https://coveralls.io/repos/github/mosquito/argclass/badge.svg?branch=master)](https://coveralls.io/github/mosquito/argclass?branch=master)
[![Tests](https://github.com/mosquito/argclass/workflows/tests/badge.svg)](https://github.com/mosquito/argclass/actions?query=workflow%3Atests)
[![License](https://img.shields.io/pypi/l/argclass.svg)](https://pypi.python.org/pypi/argclass/)

**Declarative CLI parser with type hints, config files, and environment variables.**

Build type-safe command-line interfaces using Python classes. Get IDE autocompletion,
automatic `--help` generation, and seamless integration with config files and
environment variables - all with zero dependencies.

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

---

## Why argclass?

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

| Feature                 | argclass | argparse | click/typer |
|-------------------------|----------|----------|-------------|
| Type hints → arguments  | Yes      | No       | Yes         |
| IDE autocompletion      | Yes      | No       | Yes         |
| Config file support     | Built-in | No       | No          |
| Environment variables   | Built-in | No       | Plugin      |
| Secret masking          | Built-in | No       | No          |
| Argument groups         | Reusable | Limited  | No          |
| Dependencies            | stdlib   | stdlib   | Many        |

---

## Installation

```console
pip install argclass
```

:::{tip}
📥 <a href="_static/argclass.pdf" download>**Download PDF Documentation**</a> for offline reading.
:::

---

## Quick Examples

### Groups

Organize related arguments:

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
# parser.db.host == "prod.db"
```

### Config Files

Load defaults from INI, JSON, or TOML:

```python
import argclass

class Parser(argclass.Parser):
    host: str = "localhost"
    port: int = 8080

parser = Parser(config_files=[
    "/etc/myapp.ini",
    "~/.config/myapp.ini",
])
```

### Environment Variables

Read from environment with a prefix:

```python
import argclass

class Parser(argclass.Parser):
    host: str = "localhost"
    port: int = 8080

parser = Parser(auto_env_var_prefix="MYAPP_")
# Reads from MYAPP_HOST, MYAPP_PORT
```

---

## Get Started

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
