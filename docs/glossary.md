# Glossary

Definitions of terms used throughout the argclass documentation.

## Core Concepts

### Parser
A class that inherits from `argclass.Parser` and defines command-line arguments
as class attributes. Parsers are the main building blocks of argclass applications.

<!--- name: test_glossary_parser --->
```python
import argclass

class MyParser(argclass.Parser):
    name: str
    count: int = 1

parser = MyParser()
parser.parse_args(["--name", "test"])
assert parser.name == "test"
```

### Group
A class that inherits from `argclass.Group` used to bundle related arguments
together. Groups add a prefix to their arguments (e.g., `--database-host`).

<!--- name: test_glossary_group --->
```python
import argclass

class DatabaseGroup(argclass.Group):
    host: str = "localhost"

class Parser(argclass.Parser):
    database = DatabaseGroup()  # Arguments prefixed with "database-"

parser = Parser()
parser.parse_args(["--database-host", "prod.db"])
assert parser.database.host == "prod.db"
```

### Subcommand
A nested parser class that represents a command like `git commit` or `docker run`.
Subcommands have their own arguments and can be executed via `__call__`.

<!--- name: test_glossary_subcommand --->
```python
import argclass

class BuildCommand(argclass.Parser):
    output: str = "dist"

class CLI(argclass.Parser):
    build = BuildCommand()  # Creates "build" subcommand

cli = CLI()
cli.parse_args(["build", "--output", "out"])
assert cli.build.output == "out"
```

## Argument Types

### Named Argument
An argument specified with `--name value` syntax. Most argclass arguments are
named by default.

<!--- name: test_glossary_named --->
```python
import argclass

class Parser(argclass.Parser):
    host: str = "localhost"  # Named: --host value

parser = Parser()
parser.parse_args(["--host", "example.com"])
assert parser.host == "example.com"
```

### Positional Argument
An argument identified by its position, not a flag. Created by passing the name
without dashes to `Argument()`.

<!--- name: test_glossary_positional --->
```python
import argclass

class Parser(argclass.Parser):
    filename: str = argclass.Argument("filename")  # Positional

parser = Parser()
parser.parse_args(["input.txt"])
assert parser.filename == "input.txt"
```

### Required Argument
An argument that must be provided. Arguments without default values are required.

<!--- name: test_glossary_required --->
```python
import argclass

class Parser(argclass.Parser):
    name: str      # Required - no default
    count: int = 1 # Optional - has default

parser = Parser()
parser.parse_args(["--name", "test"])
assert parser.name == "test"
```

### Optional Argument
An argument with a default value that can be omitted from the command line.

### Boolean Flag
An argument that doesn't take a value; its presence sets a boolean value.
Use `bool = False` for flags that enable features.

<!--- name: test_glossary_flag --->
```python
import argclass

class Parser(argclass.Parser):
    verbose: bool = False  # --verbose enables (sets to True)

parser = Parser()
parser.parse_args(["--verbose"])
assert parser.verbose is True
```

## argparse Terminology

### nargs
Controls how many command-line values an argument consumes.

| Value | Meaning | Example |
|-------|---------|---------|
| `None` | Single value (default) | `--name value` |
| `?` | Zero or one | `--config` or `--config file.ini` |
| `*` | Zero or more | `--files` or `--files a.txt b.txt` |
| `+` | One or more | `--files a.txt b.txt` |
| `N` | Exactly N | `--point 1.0 2.0 3.0` |

<!--- name: test_glossary_nargs --->
```python
import argclass

class Parser(argclass.Parser):
    files: list[str] = argclass.Argument(nargs="*", default=[])

parser = Parser()
parser.parse_args(["--files", "a.txt", "b.txt"])
assert parser.files == ["a.txt", "b.txt"]
```

### action
Determines what happens when an argument is encountered.

| Action | Effect |
|--------|--------|
| `store` | Store the value (default) |
| `store_true` | Store `True` when flag present |
| `store_false` | Store `False` when flag present |
| `count` | Count occurrences (`-vvv` → 3) |
| `append` | Append to a list |
| `version` | Print version and exit |

### metavar
The placeholder shown in help text for an argument's value.

<!--- name: test_glossary_metavar --->
```python
import argclass

class Parser(argclass.Parser):
    config: str = argclass.Argument(
        metavar="FILE",  # Shows: --config FILE
        default="config.ini"
    )

parser = Parser()
parser.parse_args([])
assert parser.config == "config.ini"
```

### choices
Restricts an argument to specific allowed values.

<!--- name: test_glossary_choices --->
```python
import argclass

class Parser(argclass.Parser):
    level: str = argclass.Argument(
        choices=["debug", "info", "error"],
        default="info"
    )

parser = Parser()
parser.parse_args(["--level", "debug"])
assert parser.level == "debug"
```

### dest
The attribute name where the parsed value is stored. In argclass, this is
automatically derived from the field name.

## Configuration

### Config File
An external file (INI, JSON, or TOML) that provides default values for arguments.
Config file values are overridden by environment variables and CLI arguments.

### Config Parser
A class that reads and parses configuration files. argclass provides:
- `INIDefaultsParser` - For `.ini` files (default)
- `JSONDefaultsParser` - For `.json` files
- `TOMLDefaultsParser` - For `.toml` files

### auto_env_var_prefix
A string prefix used to automatically generate environment variable names from
argument names. For example, with prefix `"MYAPP_"`, argument `host` reads from
`MYAPP_HOST`.

<!--- name: test_glossary_prefix --->
```python
import os
import argclass

os.environ["MYAPP_HOST"] = "from-env"

class Parser(argclass.Parser):
    host: str = "localhost"

parser = Parser(auto_env_var_prefix="MYAPP_")
parser.parse_args([])
assert parser.host == "from-env"

del os.environ["MYAPP_HOST"]
```

## Security

### Secret
A value marked as sensitive using `argclass.Secret()`. Secrets are:
- Masked in `repr()` output (shows `******`) - safe for logging
- Accessible via `str()` for use in code
- Removed from environment when `sanitize_env()` is called

<!--- name: test_glossary_secret --->
```python
import os
import argclass

os.environ["API_KEY"] = "secret123"

class Parser(argclass.Parser):
    api_key: str = argclass.Secret(env_var="API_KEY")

parser = Parser()
parser.parse_args([])
assert "secret123" not in repr(parser.api_key)  # Masked in repr

parser.sanitize_env()
assert "API_KEY" not in os.environ  # Removed
```

### sanitize_env()
A method that removes secret values from environment variables after parsing.
Important for security when spawning child processes.

## Priority Order

The order in which argclass resolves argument values:

```
CLI arguments  >  Environment variables  >  Config files  >  Code defaults
     (1)                  (2)                   (3)              (4)
```

Higher priority sources override lower priority sources.

## Type Hints

### Literal
A typing construct that restricts values to specific options. Provides type-safe
choices with IDE support.

<!--- name: test_glossary_literal --->
```python
import argclass
from typing import Literal

class Parser(argclass.Parser):
    mode: Literal["read", "write"] = "read"

parser = Parser()
parser.parse_args(["--mode", "write"])
assert parser.mode == "write"
```

### Optional / Union with None
Indicates an argument can be `None`. In argclass, `T | None` implies `default=None`,
making the argument optional.

<!--- name: test_glossary_optional --->
```python
import argclass

class Parser(argclass.Parser):
    config: str | None  # Implies default=None

parser = Parser()
parser.parse_args([])
assert parser.config is None
```

### type vs converter

- **type**: Called for each input string during parsing (before collection)
- **converter**: Called once on the final collected result (after parsing)

<!--- name: test_glossary_type_converter --->
```python
import argclass

class Parser(argclass.Parser):
    # type converts each string to int
    numbers: list[int] = argclass.Argument(nargs="+", type=int)

    # converter transforms the final result
    unique: set[int] = argclass.Argument(nargs="+", type=int, converter=set)

parser = Parser()
parser.parse_args(["--numbers", "1", "2", "--unique", "1", "2", "2"])
assert parser.numbers == [1, 2]
assert parser.unique == {1, 2}
```
