# argclass

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
```

## Why argclass?

| Feature | argclass | argparse | click/typer |
|---------|----------|----------|-------------|
| Type hints → arguments | Yes | No | Yes |
| IDE autocompletion | Yes | No | Yes |
| Config file support | Built-in | No | No |
| Environment variables | Built-in | No | Plugin |
| Secret masking | Built-in | No | No |
| Argument groups | Reusable | Limited | No |
| Dependencies | None | stdlib | Many |

**argclass** is a thin layer between `argparse` and Python's type system.
Any argparse extension works seamlessly with argclass.

## Installation

```bash
pip install argclass
```

## Documentation

```{toctree}
:maxdepth: 2
:caption: Getting Started

quickstart
tutorial
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
```

```{toctree}
:maxdepth: 2
:caption: Reference

api
changelog
```

## Indices and tables

- {ref}`genindex`
- {ref}`modindex`
- {ref}`search`
