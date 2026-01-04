# Arguments

This guide covers all ways to define and configure arguments in argclass.

## Basic Arguments

The simplest way to define an argument is with a type annotation:

<!--- name: test_args_basic --->
```python
import argclass

class Parser(argclass.Parser):
    name: str           # Required string
    count: int = 10     # Optional integer with default
    ratio: float = 0.5  # Optional float with default

parser = Parser()
parser.parse_args(["--name", "test", "--count", "5"])

assert parser.name == "test"
assert parser.count == 5
assert parser.ratio == 0.5
```

## Type Annotations

### Supported Types

argclass automatically handles these types:

| Type | Description | Example |
|------|-------------|---------|
| `str` | String value | `"hello"` |
| `int` | Integer value | `42` |
| `float` | Floating point | `3.14` |
| `bool` | Boolean flag | `True` |
| `Path` | File path | `Path("/tmp")` |
| `list[T]` | List of values | `["a", "b"]` |
| `set[T]` | Unique values | `{1, 2, 3}` |
| `frozenset[T]` | Immutable set | `frozenset([1, 2])` |

### Optional Types

Use `Optional[T]` or `T | None` for optional arguments:

<!--- name: test_args_optional --->
```python
import argclass
from typing import Optional

class Parser(argclass.Parser):
    required_arg: str
    optional_arg: Optional[str]
    optional_with_default: Optional[int] = 42

parser = Parser()
parser.parse_args(["--required-arg", "value"])

assert parser.required_arg == "value"
assert parser.optional_arg is None
assert parser.optional_with_default == 42
```

### Collection Types

Collection types automatically use `nargs`:

<!--- name: test_args_collections --->
```python
import argclass

class Parser(argclass.Parser):
    files: list[str]
    numbers: set[int]
    tags: frozenset[str]

parser = Parser()
parser.parse_args([
    "--files", "a.txt", "b.txt",
    "--numbers", "1", "2", "2", "3",
    "--tags", "web", "api", "web"
])

assert parser.files == ["a.txt", "b.txt"]
assert parser.numbers == {1, 2, 3}
assert parser.tags == frozenset(["web", "api"])
```

## Using Argument()

Use `argclass.Argument()` for additional configuration:

<!--- name: test_args_argument_func --->
```python
import argclass

class Parser(argclass.Parser):
    name: str = argclass.Argument(
        "-n", "--name",
        help="User name",
        metavar="NAME",
    )
    count: int = argclass.Argument(default=1)

parser = Parser()
parser.parse_args(["-n", "Alice", "--count", "5"])

assert parser.name == "Alice"
assert parser.count == 5
```

## Typed Argument Functions

For precise type inference, use the typed variants:

### ArgumentSingle

For single-value arguments with exact type:

<!--- name: test_args_single --->
```python
import argclass

class Parser(argclass.Parser):
    count: int = argclass.ArgumentSingle(type=int, default=10)
    name: str = argclass.ArgumentSingle(type=str)

parser = Parser()
parser.parse_args(["--name", "test", "--count", "42"])

assert parser.count == 42
assert parser.name == "test"
```

### ArgumentSequence

For multi-value arguments:

<!--- name: test_args_sequence --->
```python
import argclass

class Parser(argclass.Parser):
    numbers: list[int] = argclass.ArgumentSequence(type=int)
    files: list[str] = argclass.ArgumentSequence(type=str, nargs="*", default=[])

parser = Parser()
parser.parse_args(["--numbers", "1", "2", "3"])

assert parser.numbers == [1, 2, 3]
assert parser.files == []
```

## Boolean Flags

Boolean arguments have special handling in argclass.

**Shortcut syntax** - Using `bool = False` or `bool = True` directly:

<!--- name: test_args_bool_shortcut --->
```python
import argclass

class Parser(argclass.Parser):
    # bool = False is a shortcut for action="store_true"
    # The flag --debug sets it to True
    debug: bool = False

    # bool = True is a shortcut for action="store_false"
    # The flag --no-cache sets it to False
    cache: bool = True

parser = Parser()
parser.parse_args(["--debug", "--cache"])

assert parser.debug is True
assert parser.cache is False
```

**Explicit syntax** - When using `argclass.Argument()` for booleans (e.g., to add
help text or aliases), you **must** explicitly specify the `action` parameter:

<!--- name: test_args_bool_explicit --->
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

Without `action`, the boolean argument expects a value like `--verbose true`.

## Actions

Control how arguments are processed:

<!--- name: test_args_actions --->
```python
import argclass

class Parser(argclass.Parser):
    verbose: bool = argclass.Argument(
        "-v",
        action=argclass.Actions.STORE_TRUE,
        default=False
    )
    no_cache: bool = argclass.Argument(
        action=argclass.Actions.STORE_FALSE,
        default=True
    )
    verbosity: int = argclass.Argument(
        action=argclass.Actions.COUNT,
        default=0
    )

parser = Parser()
parser.parse_args(["-v", "--no-cache", "--verbosity", "--verbosity"])

assert parser.verbose is True
assert parser.no_cache is False
assert parser.verbosity == 2
```

## Nargs

Control how many values an argument accepts:

<!--- name: test_args_nargs --->
```python
import argclass

class Parser(argclass.Parser):
    output: str = argclass.Argument(nargs="?", default="out.txt")
    extras: list[str] = argclass.Argument(nargs="*", default=[])
    files: list[str] = argclass.Argument(nargs="+")
    point: list[float] = argclass.Argument(nargs=3)

parser = Parser()
parser.parse_args([
    "--files", "a.txt", "b.txt",
    "--point", "1.0", "2.0", "3.0"
])

assert parser.output == "out.txt"
assert parser.extras == []
assert parser.files == ["a.txt", "b.txt"]
assert parser.point == [1.0, 2.0, 3.0]
```

Using the `Nargs` enum:

<!--- name: test_args_nargs_enum --->
```python
import argclass

class Parser(argclass.Parser):
    optional: str | None = argclass.Argument(
        nargs=argclass.Nargs.ZERO_OR_ONE,
        default=None
    )
    multiple: list[str] = argclass.Argument(
        nargs=argclass.Nargs.ZERO_OR_MORE,
        default=[]
    )

parser = Parser()
parser.parse_args(["--multiple", "a", "b", "c"])

assert parser.optional is None
assert parser.multiple == ["a", "b", "c"]
```

## Choices

Restrict values to specific options:

<!--- name: test_args_choices --->
```python
import argclass

class Parser(argclass.Parser):
    log_level: str = argclass.Argument(
        choices=["debug", "info", "warning", "error"],
        default="info"
    )
    format: str = argclass.Argument(
        choices=["json", "yaml", "toml"],
        default="json"
    )

parser = Parser()
parser.parse_args(["--log-level", "debug", "--format", "yaml"])

assert parser.log_level == "debug"
assert parser.format == "yaml"
```

## Type vs Converter

Understanding the difference:

- **`type`**: Called for each input value during parsing
- **`converter`**: Called once on the final result after parsing

<!--- name: test_args_type_vs_converter --->
```python
import argclass

class Parser(argclass.Parser):
    # type=int converts each string to int
    numbers: list[int] = argclass.Argument(nargs="+", type=int)

    # type=int converts each string, then converter=set deduplicates
    unique: set[int] = argclass.Argument(nargs="+", type=int, converter=set)

    # Single converter function
    unique_alt: set[int] = argclass.Argument(
        nargs="+",
        converter=lambda vals: set(map(int, vals))
    )

parser = Parser()
parser.parse_args([
    "--numbers", "1", "2", "3",
    "--unique", "1", "2", "2", "3",
    "--unique-alt", "4", "5", "4"
])

assert parser.numbers == [1, 2, 3]
assert parser.unique == {1, 2, 3}
assert parser.unique_alt == {4, 5}
```

## Custom Types

Use any callable as a type:

<!--- name: test_args_custom_types --->
```python
import argclass
from datetime import datetime
from pathlib import Path

def parse_date(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d")

class Parser(argclass.Parser):
    date: datetime = argclass.Argument(type=parse_date)
    output: Path = argclass.Argument(type=Path, default=Path("."))

parser = Parser()
parser.parse_args(["--date", "2024-01-15", "--output", "/tmp/output"])

assert parser.date == datetime(2024, 1, 15)
assert parser.output == Path("/tmp/output")
```
