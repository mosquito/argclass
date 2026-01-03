# argclass

![Coverage](https://coveralls.io/repos/github/mosquito/argclass/badge.svg?branch=master) [![Actions](https://github.com/mosquito/argclass/workflows/tests/badge.svg)](https://github.com/mosquito/argclass/actions?query=workflow%3Atests) [![Latest Version](https://img.shields.io/pypi/v/argclass.svg)](https://pypi.python.org/pypi/argclass/) [![Python Versions](https://img.shields.io/pypi/pyversions/argclass.svg)](https://pypi.python.org/pypi/argclass/) [![License](https://img.shields.io/pypi/l/argclass.svg)](https://pypi.python.org/pypi/argclass/)

**Declarative CLI parser with type hints, config files, and environment variables.**

Build type-safe command-line interfaces using Python classes. Get IDE autocompletion, automatic `--help` generation, and seamless integration with config files and environment variables - all with zero dependencies.

<!--- name: test_hero_example --->
```python
import argclass

class Server(argclass.Parser):
    host: str = "127.0.0.1"
    port: int = 8080
    debug: bool = False

server = Server()
server.parse_args(["--host", "0.0.0.0", "--port", "9000", "--debug"])
assert server.host == "0.0.0.0"
assert server.port == 9000
assert server.debug is True
```

Usage:
```bash
$ python server.py --host 0.0.0.0 --port 9000 --debug
```

## Why argclass?

| Feature                  | argclass   | argparse   | click/typer |
|--------------------------|------------|------------|-------------|
| Type hints → arguments   | ✅          | ❌          | ✅           |
| IDE autocompletion       | ✅          | ❌          | ✅           |
| Config file support      | ✅ Built-in | ❌          | ❌           |
| Environment variables    | ✅ Built-in | ❌          | ❌ Plugin    |
| Secret masking           | ✅ Built-in | ❌          | ❌           |
| Argument groups          | ✅ Reusable | ⚠️ Limited | ❌           |
| Dependencies             | stdlib     | stdlib     | many        |

**argclass** is ideal for applications that need configuration from multiple sources 
(CLI + config files + environment) with full type safety.

## Table of Contents

- [Why argclass?](#why-argclass)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Type Annotations](#type-annotations)
  - [Optional Types](#optional-types)
  - [PEP 604 Union Types](#pep-604-union-types)
  - [List and Collection Types](#list-and-collection-types)
- [Boolean Arguments](#boolean-arguments)
- [Argument Groups](#argument-groups)
  - [Empty Prefix for Groups](#empty-prefix-for-groups)
- [Parser Inheritance](#parser-inheritance)
- [Subparsers](#subparsers)
- [Configuration Files](#configuration-files)
- [Environment Variables](#environment-variables)
- [Value Conversion](#value-conversion)
- [Enum Arguments](#enum-arguments)
- [Secrets](#secrets)
- [Custom Config Parsers](#custom-config-parsers)
- [Third Party Integration](#third-party-integration)

## Installation

```bash
pip install argclass
```

## Quick Start

<!--- name: test_simple_example --->
```python
import argclass

class CopyParser(argclass.Parser):
    recursive: bool
    preserve_attributes: bool

parser = CopyParser()
parser.parse_args(["--recursive", "--preserve-attributes"])
assert parser.recursive
assert parser.preserve_attributes
```

Arguments are automatically derived from class annotations.

## When to Use `argclass.Argument`

Most arguments can be defined with just type annotations. Use `argclass.Argument()` only when you need extra configuration:

| You need...              | Just annotation       | Use `argclass.Argument()`      |
|--------------------------|-----------------------|--------------------------------|
| Required string          | `name: str`           | -                              |
| Optional with default    | `count: int = 10`     | -                              |
| Boolean flag             | `debug: bool = False` | -                              |
| Optional (None default)  | `name: str \| None`   | -                              |
| Path argument            | `config: Path`        | -                              |
| **Help text**            | -                     | `Argument(help="...")`         |
| **Short alias**          | -                     | `Argument("-n", "--name")`     |
| **Environment variable** | -                     | `Argument(env_var="APP_NAME")` |
| **Multiple values**      | -                     | `Argument(nargs="+")`          |
| **Choices**              | -                     | `Argument(choices=["a", "b"])` |
| **Custom conversion**    | -                     | `Argument(converter=func)`     |
| **Hide from help**       | -                     | `Argument(secret=True)`        |

**Simple example - no `Argument()` needed:**

<!--- name: test_simple_no_argument --->
```python
import argclass
from pathlib import Path

class Parser(argclass.Parser):
    name: str                      # required
    count: int = 10                # optional with default
    debug: bool = False            # flag
    config: Path | None = None     # optional path

parser = Parser()
parser.parse_args(["--name", "test", "--debug"])
assert parser.name == "test"
assert parser.count == 10
assert parser.debug is True
assert parser.config is None
```

**When you need more control:**

<!--- name: test_when_argument_needed --->
```python
import argclass
from typing import List

class Parser(argclass.Parser):
    # Short alias and help text
    name: str = argclass.Argument(
        "-n", "--name",
        help="Your name"
    )
    # Multiple values
    files: List[str] = argclass.Argument(
        nargs="+",
        help="Files to process"
    )
    # Restricted choices
    mode: str = argclass.Argument(
        choices=["fast", "slow", "auto"],
        default="auto"
    )

parser = Parser()
parser.parse_args(["-n", "Alice", "--files", "a.txt", "b.txt", "--mode", "fast"])
assert parser.name == "Alice"
assert parser.files == ["a.txt", "b.txt"]
assert parser.mode == "fast"
```

## Type Annotations

argclass uses type annotations to determine argument types. Simple types like `str`, `int`, `float` are supported out of the box.

<!--- name: test_type_annotations --->
```python
import argclass

class Parser(argclass.Parser):
    name: str                    # required string argument
    count: int = 10              # optional integer with default
    threshold: float = 0.5       # optional float with default

parser = Parser()
parser.parse_args(["--name", "test", "--count", "5"])
assert parser.name == "test"
assert parser.count == 5
assert parser.threshold == 0.5
```

### Optional Types

Use `Optional[T]` to make an argument optional (not required) with `None` as default:

<!--- name: test_optional_example --->
```python
import argclass
from typing import Optional

class Parser(argclass.Parser):
    required_arg: str                  # required
    optional_arg: Optional[str]        # optional, defaults to None
    optional_with_default: Optional[int] = 42  # optional with default

parser = Parser()
parser.parse_args(["--required-arg", "value"])
assert parser.required_arg == "value"
assert parser.optional_arg is None
assert parser.optional_with_default == 42
```

### PEP 604 Union Types

Python 3.10+ union syntax (`X | None`) is fully supported:

<!--- name: test_pep604_example --->
```python
import argclass

class Parser(argclass.Parser):
    name: str | None                   # optional string
    count: int | None = 10             # optional with default

parser = Parser()
parser.parse_args([])
assert parser.name is None
assert parser.count == 10

parser.parse_args(["--name", "test", "--count", "5"])
assert parser.name == "test"
assert parser.count == 5
```

### List and Collection Types

Container types are automatically handled - just use the type annotation:

<!--- name: test_list_types --->
```python
import argclass

class Parser(argclass.Parser):
    # list[str] and List[str] are equivalent (PEP 585)
    names: list[str]                  # required list of strings
    numbers: list[int]                # required list of integers

    # set[T] automatically deduplicates values
    unique_ids: set[int]              # required unique integers

    # frozenset[T] for immutable collections
    tags: frozenset[str]              # required immutable set

    # Optional collections use Optional[] or | None
    extras: list[str] | None          # optional list

parser = Parser()
parser.parse_args([
    "--names", "alice", "bob",
    "--numbers", "1", "2", "3",
    "--unique-ids", "1", "2", "2", "3",
    "--tags", "web", "api", "web"
])
assert parser.names == ["alice", "bob"]
assert parser.numbers == [1, 2, 3]
assert parser.unique_ids == {1, 2, 3}
assert parser.tags == frozenset(["web", "api"])
assert parser.extras is None
```

Both `list[str]` (PEP 585, Python 3.9+) and `List[str]` (typing module) are supported.

### Path Arguments

`Path` type is automatically recognized:

<!--- name: test_path_types --->
```python
import argclass
from pathlib import Path

class Parser(argclass.Parser):
    config: Path
    output: Path = Path("./output")

parser = Parser()
parser.parse_args(["--config", "/etc/app/config.yaml"])
assert parser.config == Path("/etc/app/config.yaml")
assert parser.output == Path("./output")
```

### Complex Type Conversions

For complex types, use `converter` to transform parsed values:

<!--- name: test_complex_types --->
```python
import argclass
from typing import Tuple
import json

def parse_json(value: str) -> dict:
    return json.loads(value)

def parse_endpoint(value: str) -> Tuple[str, int]:
    host, port = value.rsplit(":", 1)
    return (host, int(port))

class Parser(argclass.Parser):
    # JSON string to dict
    metadata: dict = argclass.Argument(
        converter=parse_json,
        default="{}"
    )
    # "host:port" string to tuple
    endpoint: Tuple[str, int] = argclass.Argument(
        converter=parse_endpoint
    )

parser = Parser()
parser.parse_args([
    "--metadata", '{"env": "prod", "version": 2}',
    "--endpoint", "localhost:8080"
])
assert parser.metadata == {"env": "prod", "version": 2}
assert parser.endpoint == ("localhost", 8080)
```

### Multiple Values with Choices

Restrict arguments to specific choices:

<!--- name: test_choices_types --->
```python
import argclass
from typing import List

class Parser(argclass.Parser):
    # Single choice
    log_format: str = argclass.Argument(
        choices=["json", "text", "structured"],
        default="text"
    )
    # Multiple choices
    features: List[str] = argclass.Argument(
        nargs="*",
        choices=["auth", "cache", "metrics", "tracing"],
        default=[]
    )

parser = Parser()
parser.parse_args(["--log-format", "json", "--features", "auth", "metrics"])
assert parser.log_format == "json"
assert parser.features == ["auth", "metrics"]
```

## Boolean Arguments

Boolean arguments have special handling in argclass.

### Shortcut Syntax

Using `bool = False` or `bool = True` directly creates flag-style arguments:

<!--- name: test_bools --->
```python
import argclass


class ArgumentParser(argclass.Parser):
    # bool = False is a shortcut for action="store_true"
    # The flag --debug sets it to True
    debug: bool = False
    # bool = True is a shortcut for action="store_false"
    # The flag --no-cache sets it to False
    cache: bool = True


parser = ArgumentParser()
parser.parse_args(["--debug"])
assert parser.debug is True
assert parser.cache is True
```

### Explicit Syntax with Argument()

When using `argclass.Argument()` for booleans (e.g., to add help text or aliases),
you **must** explicitly specify the `action` parameter:

<!--- name: test_bools_explicit --->
```python
import argclass


class Parser(argclass.Parser):
    # Using Argument() requires explicit action
    verbose: bool = argclass.Argument(
        "-v", "--verbose",
        action=argclass.Actions.STORE_TRUE,  # Required!
        default=False,
        help="Enable verbose output"
    )
    # Can also use string literal
    quiet: bool = argclass.Argument(
        "-q", "--quiet",
        action="store_true",  # String literal works too
        default=False,
        help="Suppress output"
    )


parser = Parser()
parser.parse_args(["-v", "-q"])
assert parser.verbose is True
assert parser.quiet is True
```

Without `action`, the boolean argument would expect a value like `--verbose true`.

## Argument Groups

Groups allow organizing related arguments together and **reusing the same definition** for multiple purposes. Each group instance gets its own prefix based on the attribute name:

<!-- name: test_argument_groups_example -->
```python
import argclass

class HostPortGroup(argclass.Group):
    host: str = "localhost"
    port: int

class Parser(argclass.Parser):
    api = HostPortGroup(title="API server", defaults={"port": 8080})
    metrics = HostPortGroup(title="Metrics endpoint", defaults={"port": 9090})

parser = Parser()
parser.parse_args([
    "--api-host", "0.0.0.0",
    "--api-port", "8888",
    "--metrics-port", "9999"
])
assert parser.api.host == "0.0.0.0"
assert parser.api.port == 8888
assert parser.metrics.host == "localhost"
assert parser.metrics.port == 9999
```

This produces help output like:
```
API server:
  --api-host API_HOST   (default: localhost)
  --api-port API_PORT   (default: 8080)

Metrics endpoint:
  --metrics-host METRICS_HOST
                        (default: localhost)
  --metrics-port METRICS_PORT
                        (default: 9090)
```

### Empty Prefix for Groups

Use `prefix=""` to create arguments without a group prefix:

<!--- name: test_empty_prefix --->
```python
import argclass

class ConnectionGroup(argclass.Group):
    host: str = "localhost"
    port: int = 8080

class Parser(argclass.Parser):
    # No prefix: --host and --port
    conn = ConnectionGroup(prefix="")

parser = Parser()
parser.parse_args(["--host", "example.com", "--port", "9000"])
assert parser.conn.host == "example.com"
assert parser.conn.port == 9000
```

You can also use custom prefixes:

```python
import argclass

class ConnectionGroup(argclass.Group):
    host: str = "localhost"
    port: int = 8080

class Parser(argclass.Parser):
    # Custom prefix: --api-host and --api-port
    conn = ConnectionGroup(prefix="api")

parser = Parser()
parser.parse_args(["--api-host", "example.com"])
assert parser.conn.host == "example.com"
```

## Parser Inheritance

Parsers can inherit from other parsers. All arguments from parent parsers are inherited and remain required if they were required in the parent:

<!--- name: test_inheritance_example --->
```python
import argclass

class BaseParser(argclass.Parser):
    debug: bool = False
    config: str                        # required in base

class ExtendedParser(BaseParser):
    output: str                        # required in extended

parser = ExtendedParser()
parser.parse_args(["--config", "app.ini", "--output", "result.txt", "--debug"])
assert parser.debug is True
assert parser.config == "app.ini"
assert parser.output == "result.txt"
```

You can also inherit from groups to add their arguments directly to the parser:

```python
import argclass

class AddressPort(argclass.Group):
    address: str = "0.0.0.0"
    port: int = 8080

class Parser(argclass.Parser, AddressPort):
    debug: bool = False

parser = Parser()
parser.parse_args(["--address", "127.0.0.1", "--port", "9000"])
assert parser.address == "127.0.0.1"
assert parser.port == 9000
```

## Subparsers

Subparsers allow creating command-based CLIs:

```python
import argclass

class CommitCommand(argclass.Parser):
    message: str

    def __call__(self) -> int:
        print(f"Committing with message: {self.message}")
        return 0

class PushCommand(argclass.Parser):
    remote: str = "origin"
    branch: str = "main"

    def __call__(self) -> int:
        print(f"Pushing to {self.remote}/{self.branch}")
        return 0

class GitParser(argclass.Parser):
    verbose: bool = False
    commit = CommitCommand()
    push = PushCommand()

if __name__ == '__main__':
    parser = GitParser()
    parser.parse_args()
    exit(parser())
```

Usage:
```bash
$ python git.py commit --message "Initial commit"
Committing with message: Initial commit

$ python git.py push --remote upstream --branch feature
Pushing to upstream/feature
```

The `__parent__` attribute provides access to the parent parser from subcommands.

## Configuration Files

Parsers can read default values from INI configuration files:

<!--- name: test_config_example --->
```python
import logging
from pathlib import Path
from tempfile import TemporaryDirectory
import argclass

class Parser(argclass.Parser):
    log_level: int = argclass.LogLevel
    address: str
    port: int

with TemporaryDirectory() as tmpdir:
    tmp = Path(tmpdir)
    with open(tmp / "config.ini", "w") as fp:
        fp.write(
            "[DEFAULT]\n"
            "log_level=info\n"
            "address=localhost\n"
            "port=8080\n"
        )

    parser = Parser(config_files=[tmp / "config.ini"])
    parser.parse_args([])
    assert parser.log_level == logging.INFO
    assert parser.address == "localhost"
    assert parser.port == 8080
```

Group arguments are read from INI sections:

```ini
[DEFAULT]
log_level=info

[database]
host=db.example.com
port=5432

[cache]
host=redis.example.com
port=6379
```

## Environment Variables

Use `auto_env_var_prefix` to automatically read defaults from environment variables:

```python
import argclass

class Parser(argclass.Parser):
    database_url: str
    debug: bool = False

parser = Parser(auto_env_var_prefix="APP_")
# Reads from APP_DATABASE_URL and APP_DEBUG
```

Use `parser.sanitize_env()` to remove used environment variables after parsing.

## Value Conversion

For complex types, use `type` or `converter` arguments. Understanding the difference is important:

| Parameter   | When Called         | Called With                        | Use Case                                   |
|-------------|---------------------|------------------------------------|--------------------------------------------|
| `type`      | **During** parsing  | Each individual string value       | Basic type conversion (str→int, str→Path)  |
| `converter` | **After** parsing   | Final parsed value (may be a list) | Post-processing (list→set, JSON→dict)      |

### Basic Example

<!--- name: test_converter_example --->
```python
import uuid
import argclass

def string_uid(value: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_OID, value)

class Parser(argclass.Parser):
    strid1: uuid.UUID = argclass.Argument(converter=string_uid)
    strid2: uuid.UUID = argclass.Argument(type=string_uid)

parser = Parser()
parser.parse_args(["--strid1=hello", "--strid2=world"])
assert parser.strid1 == uuid.uuid5(uuid.NAMESPACE_OID, 'hello')
assert parser.strid2 == uuid.uuid5(uuid.NAMESPACE_OID, 'world')
```

For single values, both work similarly. The difference becomes clear with `nargs`.

### With nargs: type vs converter

<!--- name: test_type_vs_converter --->
```python
import argclass

class Parser(argclass.Parser):
    # type=int is called for EACH value: "1" -> 1, "2" -> 2, "3" -> 3
    # Result: [1, 2, 3]
    numbers: list = argclass.Argument(nargs="+", type=int)

    # type=int converts each value, THEN converter=set transforms the list
    # "1", "2", "2", "3" -> [1, 2, 2, 3] -> {1, 2, 3}
    unique: set = argclass.Argument(nargs="+", type=int, converter=set)

parser = Parser()
parser.parse_args(["--numbers", "1", "2", "3", "--unique", "1", "2", "2", "3"])
assert parser.numbers == [1, 2, 3]
assert parser.unique == {1, 2, 3}
```

### Combining type and converter

<!--- name: test_list_converter_frozenset_example --->
```python
import argclass

class Parser(argclass.Parser):
    numbers = argclass.Argument(
        nargs=argclass.Nargs.ONE_OR_MORE, type=int, converter=frozenset
    )

parser = Parser()
parser.parse_args(["--numbers", "1", "2", "3"])
assert parser.numbers == frozenset([1, 2, 3])
```

Pipeline: `["1", "2", "3"]` → (type=int each) → `[1, 2, 3]` → (converter) → `frozenset({1, 2, 3})`

## Enum Arguments

Enum arguments automatically generate choices and convert values:

<!--- name: test_enum_example --->
```python
import enum
import logging
import argclass

class LogLevelEnum(enum.IntEnum):
    debug = logging.DEBUG
    info = logging.INFO
    warning = logging.WARNING
    error = logging.ERROR
    critical = logging.CRITICAL

class Parser(argclass.Parser):
    """Log level with default"""
    log_level = argclass.EnumArgument(LogLevelEnum, default="info")

class ParserLogLevelIsRequired(argclass.Parser):
    log_level: LogLevelEnum

parser = Parser()
parser.parse_args([])
assert parser.log_level == logging.INFO

parser = Parser()
parser.parse_args(["--log-level=error"])
assert parser.log_level == logging.ERROR

parser = ParserLogLevelIsRequired()
parser.parse_args(["--log-level=warning"])
assert parser.log_level == logging.WARNING
```

The built-in `argclass.LogLevel` provides a ready-to-use log level argument.

## Secrets

Use `secret=True` or `argclass.Secret` to hide sensitive defaults in help output:

```python
import argclass

class Parser(argclass.Parser):
    api_key: str = argclass.Secret()
    password: str = argclass.Argument(secret=True)

parser = Parser(auto_env_var_prefix="APP_")
parser.print_help()
# Defaults are hidden in help output
```

### SecretString

`SecretString` prevents accidental logging of sensitive values:

```python
import logging
from argclass import SecretString

logging.basicConfig(level=logging.INFO)
password = SecretString("super-secret")

logging.info(password)           # Logs: '******'
logging.info(f"{password!r}")    # Logs: '******'
print(str(password))             # Prints: super-secret
```

## Custom Config Parsers

Create custom configuration file parsers by extending `ConfigAction`:

### YAML Parser

```python
from pathlib import Path
from typing import Mapping, Any
import argclass
import yaml

class YAMLConfigAction(argclass.ConfigAction):
    def parse_file(self, file: Path) -> Mapping[str, Any]:
        with file.open("r") as fp:
            return yaml.safe_load(fp)

class YAMLConfig(argclass.ConfigArgument):
    action = YAMLConfigAction

class Parser(argclass.Parser):
    config = argclass.Config(config_class=YAMLConfig)
```

### TOML Parser

```python
from pathlib import Path
from typing import Mapping, Any
import argclass
import tomllib  # Python 3.11+ or use tomli

class TOMLConfigAction(argclass.ConfigAction):
    def parse_file(self, file: Path) -> Mapping[str, Any]:
        with file.open("rb") as fp:
            return tomllib.load(fp)

class TOMLConfig(argclass.ConfigArgument):
    action = TOMLConfigAction

class Parser(argclass.Parser):
    config = argclass.Config(config_class=TOMLConfig)
```

## Third Party Integration

**argclass** is a thin layer between `argparse` and Python's type system. Since it builds on the standard library, any argparse extension or third-party library works seamlessly.

### Rich Help Output

Use `rich_argparse` for beautiful help formatting:

```python
import argclass
from rich_argparse import RawTextRichHelpFormatter

class Parser(argclass.Parser):
    verbose: bool = False
    output: str = "result.txt"

parser = Parser(formatter_class=RawTextRichHelpFormatter)
parser.print_help()
```

![Help Output](https://raw.githubusercontent.com/mosquito/argclass/master/.github/rich_example.png)
