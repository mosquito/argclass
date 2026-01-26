# Common Pitfalls

Quick reference for common mistakes and their solutions. These are the issues
most frequently encountered when building CLI applications with argclass.

## Boolean Flags

Boolean arguments are the most common source of confusion. The shortcut syntax
`bool = False` automatically creates a flag, but using `Argument()` requires
explicit action configuration.

### Visual Behavior Summary

```
┌─────────────────────────────────────────────────────────────────────┐
│ default=False:  no flag → False    --flag → True   ✓ Common pattern │
│ default=True:   no flag → True     --flag → False  ⚠ Inverted!      │
└─────────────────────────────────────────────────────────────────────┘
```

**For features that should be OFF by default:**
```python
verbose: bool = False    # --verbose enables it (sets to True)
```

**For features that should be ON by default:**
```python
cache: bool = True       # --cache DISABLES it (sets to False)
# Better naming for clarity:
no_cache: bool = False   # --no-cache disables cache (sets to True)
```

### Syntax Reference

| Syntax | Behavior |
|--------|----------|
| `flag: bool = False` | `--flag` sets to `True` (recommended) |
| `flag: bool = True` | `--flag` sets to `False` (toggles) |
| `Argument(default=False)` without action | Expects value like `--flag true` (wrong) |
| `Argument(default=False, action=Actions.STORE_TRUE)` | Works as flag |

**Rule:** Use simple `bool = False` syntax. Only use `Argument()` for booleans
when you need help text or aliases, and always include `action=Actions.STORE_TRUE`.

:::{warning}
A common mistake is `bool = True` expecting `--flag` to enable a feature.
Instead, `--flag` will *disable* it (set to `False`). If you want a feature
enabled by default that users can disable, name it `--no-feature` with `bool = True`.
:::

<!--- name: test_pitfall_bool_true --->
```python
import argclass

class Parser(argclass.Parser):
    feature: bool = True  # --feature toggles to False

parser = Parser()
parser.parse_args(["--feature"])
assert parser.feature is False
```

## Environment Variables

Environment variables are strings, so argclass must parse them into the
appropriate types. Boolean parsing is particularly tricky because there's
no universal standard for representing true/false in environment variables.

| Issue | Solution |
|-------|----------|
| Boolean strings | See table below (case-insensitive) |
| Spaces preserved | Trim in application logic: `value.strip()` |
| Type errors | Same rules as CLI — invalid values exit with code 2 |

### Boolean String Parsing

argclass recognizes common conventions for boolean environment variables.
Values are case-insensitive.

| Parsed as `True` | Parsed as `False` |
|------------------|-------------------|
| `1`, `y`, `yes`, `t`, `true` | Everything else |
| `on`, `enable`, `enabled` | `0`, `n`, `no`, `f`, `false`, `off`, `disable`, etc. |

<!--- name: test_pitfall_env_bool --->
```python
import os
import argclass

os.environ["TEST_FLAG"] = "yes"  # Also: true, 1, on, enable

class Parser(argclass.Parser):
    flag: bool = argclass.Argument(env_var="TEST_FLAG", default=False)

parser = Parser()
parser.parse_args([])
assert parser.flag is True

del os.environ["TEST_FLAG"]
```

<!--- name: test_pitfall_env_bool_false --->
```python
import os
import argclass

os.environ["TEST_FLAG"] = "no"  # Also: false, 0, off, disable, or any other string

class Parser(argclass.Parser):
    flag: bool = argclass.Argument(env_var="TEST_FLAG", default=False)

parser = Parser()
parser.parse_args([])
assert parser.flag is False

os.environ.pop("TEST_FLAG", None)
```

## Lists

List arguments have subtle behavior differences depending on `nargs` configuration.
The most common mistake is using `nargs="+"` when you want to allow empty lists.

| Issue | Solution |
|-------|----------|
| `--files` without values errors | Use `nargs="*"` for zero-or-more |
| Comma-separated values | CLI uses spaces: `--files a.txt b.txt` |
| Default `[]` with `nargs="+"` | Requires at least one value when flag is used |

:::{tip}
Use `nargs="*"` if the flag can appear with zero values (`--files` alone is valid).
Use `nargs="+"` if at least one value is required when the flag is used.
:::

<!--- name: test_pitfall_list_nargs --->
```python
import argclass

class Parser(argclass.Parser):
    files: list[str] = argclass.Argument(nargs="*", default=[])

parser = Parser()
parser.parse_args(["--files"])  # Zero values OK with nargs="*"
assert parser.files == []
```

## Type Hints

Type hints determine whether arguments are required or optional. A common
surprise is that `T | None` without a default value implies `default=None`,
making the argument optional rather than required.

| Hint | Behavior |
|------|----------|
| `name: str` | Required argument |
| `name: str = "default"` | Optional with default |
| `name: str \| None` | Optional, defaults to `None` |
| `name: Path` | Auto-converts string to `Path` |

:::{note}
The `| None` union type automatically sets `default=None`. If you want a
required argument that can accept `None` as a valid CLI value, you'll need
custom handling.
:::

<!--- name: test_pitfall_optional --->
```python
import argclass

class Parser(argclass.Parser):
    config: str | None  # Implies default=None, NOT required

parser = Parser()
parser.parse_args([])
assert parser.config is None
```

---

## Config Files (INI)

INI config files have specific formatting requirements. Section names must
exactly match group attribute names (case-sensitive), and complex types like
lists use Python literal syntax, not comma-separated values.

| Issue | Solution |
|-------|----------|
| Section name mismatch | Section must match group attribute name (lowercase) |
| Lists as comma-separated | Use Python literal: `ports = [8080, 8081]` |
| Strings in lists | Quote them: `hosts = ["a.com", "b.com"]` |

```ini
# Group attribute: database = DatabaseGroup()

[database]        # RIGHT - matches attribute name
host = db.example.com

[Database]        # WRONG - case mismatch (won't be loaded)
```

:::{warning}
INI section names are case-sensitive in argclass. `[Database]` and `[database]`
are different sections. Always use lowercase to match Python attribute names.
:::

## Groups

When you add a group to a parser, all its arguments get prefixed with the
group's attribute name. This is a common source of confusion when users
expect unprefixed argument names.

```text
class Parser(argclass.Parser):
    database = DatabaseGroup()  # prefix is "database"

# CLI usage:
--database-host value    # RIGHT
--host value             # WRONG - no such argument
```

:::{tip}
To add group arguments without a prefix, use `prefix=""`:
```python
import argclass

class DatabaseGroup(argclass.Group):
    host: str = "localhost"
    port: int = 5432

class Parser(argclass.Parser):
    database = DatabaseGroup(prefix="")  # Arguments: --host, --port
```
:::

---

## Subcommands

When using subcommands, only the selected subcommand's arguments are parsed
and populated. Other subcommands retain their default values. Don't assume
all subcommand attributes are populated after parsing.

<!--- name: test_pitfall_subparser --->
```python
import argclass

class Serve(argclass.Parser):
    port: int = 8080

class Build(argclass.Parser):
    output: str = "dist"

class CLI(argclass.Parser):
    serve = Serve()
    build = Build()

cli = CLI()
cli.parse_args(["serve", "--port", "9000"])
assert cli.serve.port == 9000
# cli.build.output is still default
```

:::{tip}
Use `cli.current_subparsers` to check which subcommand was selected, or
implement `__call__` on each subcommand and call `cli()` to dispatch
automatically to the selected command.
:::

---

## Exception-Raising Patterns

These patterns will raise specific argclass exceptions at parser definition
or parsing time.

### ComplexTypeError: Unsupported Union Types

Union types like `str | int` cannot be automatically converted because argclass
doesn't know which type to try first. You must provide an explicit converter.

| Pattern | Result |
|---------|--------|
| `field: str \| int` | `ComplexTypeError` at definition time |
| `field: str \| None` | OK — `None` is handled specially |
| `field: list[str] \| None` | OK — `None` is handled specially |

<!--- name: test_pitfall_complex_type --->
```python
import argclass

# This works - Optional types are supported
class WorkingParser(argclass.Parser):
    name: str | None  # OK: Union with None

parser = WorkingParser()
parser.parse_args([])
assert parser.name is None
```

To fix union types, provide an explicit converter:

```python
import argclass

def flexible_int(value: str) -> int | str:
    try:
        return int(value)
    except ValueError:
        return value

class Parser(argclass.Parser):
    count: int | str = argclass.Argument(type=flexible_int, default=0)
```

### EnumValueError: Invalid Enum Defaults

When using `EnumArgument`, the default must be a valid enum member or its
string name. Providing an invalid default raises `EnumValueError`.

<!--- name: test_pitfall_enum_valid --->
```python
import argclass
from enum import Enum

class Color(Enum):
    RED = "red"
    GREEN = "green"
    BLUE = "blue"

# Correct: default is a valid enum member name
class Parser(argclass.Parser):
    color: Color = argclass.EnumArgument(Color, default="RED")

parser = Parser()
parser.parse_args([])
assert parser.color == Color.RED
```

### ArgumentDefinitionError: Conflicting Aliases

If you define an alias that conflicts with another argument or a reserved
argparse option, `ArgumentDefinitionError` is raised.

<!--- name: test_pitfall_alias_ok --->
```python
import argclass

# This works - no conflicts
class Parser(argclass.Parser):
    verbose: bool = argclass.Argument("-v", default=False)
    output: str = argclass.Argument("-o", default="out.txt")

parser = Parser()
parser.parse_args(["-v", "-o", "result.txt"])
assert parser.verbose is True
assert parser.output == "result.txt"
```

### TypeConversionError: Converter Failures

When a custom converter raises an exception, argclass wraps it in
`TypeConversionError` with context about what value failed and the target type.

<!--- name: test_pitfall_converter --->
```python
import argclass

def positive_int(value: str) -> int:
    num = int(value)
    if num <= 0:
        raise ValueError(f"{value} must be positive")
    return num

class Parser(argclass.Parser):
    count: int = argclass.Argument(type=positive_int, default=1)

parser = Parser()
parser.parse_args(["--count", "5"])
assert parser.count == 5
```

### ConfigurationError: Invalid Config Files

When loading config files with `config_files` parameter, malformed files or
type mismatches raise `ConfigurationError`.

| Issue | Result |
|-------|--------|
| Malformed INI/JSON/TOML | `ConfigurationError` with file path |
| Value doesn't match type | `ConfigurationError` with field and section |
| Missing file | Silently ignored (unless `strict_config=True`) |

<!--- name: test_pitfall_config_ok --->
```python
import argclass
from pathlib import Path
from tempfile import NamedTemporaryFile

class Parser(argclass.Parser):
    host: str = "localhost"
    port: int = 8080

# Create a valid config file
with NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
    f.write('{"host": "example.com", "port": 9000}')
    config_path = f.name

parser = Parser(
    config_files=[config_path],
    config_parser_class=argclass.JSONDefaultsParser,
)
parser.parse_args([])
assert parser.host == "example.com"
assert parser.port == 9000

Path(config_path).unlink()
```
