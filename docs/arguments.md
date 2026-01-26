# Arguments

This guide covers all ways to define and configure arguments in argclass.

## Basic Arguments

The simplest way to define an argument is with a type annotation. Arguments
without defaults are required; arguments with defaults are optional. The type
hint determines how string values from the command line are converted.

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

Use `Optional[T]` or `T | None` for arguments that may not be provided.
Unlike required arguments, these default to `None` when not specified,
allowing you to detect whether the user provided a value.

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

Collection types accept multiple values after the flag. Use `list[T]` to
preserve order and duplicates, `set[T]` for unique values, or `frozenset[T]`
for immutable unique values. argclass automatically configures `nargs`.

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

### Literal Types

Use `Literal[...]` to restrict an argument to specific values. This is a
type-safe alternative to `choices` - the allowed values are defined in the
type annotation itself, making them visible to static type checkers.

<!--- name: test_args_literal_basic --->
```python
import argclass
from typing import Literal

class Parser(argclass.Parser):
    mode: Literal["ro", "rw"] = "ro"
    level: Literal[1, 2, 3] = 1

parser = Parser()
parser.parse_args(["--mode", "rw", "--level", "2"])

assert parser.mode == "rw"
assert parser.level == 2
```

Literal types work with `Optional` for arguments that may not be provided:

<!--- name: test_args_literal_optional --->
```python
import argclass
from typing import Literal, Optional

class Parser(argclass.Parser):
    env: Optional[Literal["dev", "staging", "prod"]]

parser = Parser()
parser.parse_args([])
assert parser.env is None

parser.parse_args(["--env", "prod"])
assert parser.env == "prod"
```

You can also use Literal types in argument groups:

<!--- name: test_args_literal_group --->
```python
import argclass
from typing import Literal

class StorageGroup(argclass.Group):
    type: Literal["s3", "posix"]
    path: str = "/data"

class Parser(argclass.Parser):
    storage = StorageGroup()

parser = Parser()
parser.parse_args(["--storage-type", "s3"])

assert parser.storage.type == "s3"
assert parser.storage.path == "/data"
```

## Using Argument()

Use `argclass.Argument()` when you need more control: short aliases like `-n`,
help text for `--help` output, custom metavars, or other argparse options.
The first positional arguments define flag names.

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

## Full argparse Compatibility

Every parameter you pass to `argclass.Argument()` is forwarded directly to
`argparse.add_argument()`. This means **all argparse features work**:

<!--- name: test_args_full_argparse --->
```python
import argclass

class Parser(argclass.Parser):
    # Every argparse parameter works
    path: str = argclass.Argument(
        "-p", "--path",
        help="Output path",
        metavar="PATH",
        default=".",
    )

    # Complex argparse features work too
    verbosity: int = argclass.Argument(
        "-v",
        action="count",  # Each -v increases count
        default=0,
        help="Increase verbosity (can be repeated)"
    )

parser = Parser()
parser.parse_args(["-v", "-v", "-v"])
assert parser.verbosity == 3
```

Similarly, `Parser(**kwargs)` passes all keyword arguments to the underlying
`argparse.ArgumentParser()`:

<!--- name: test_args_parser_kwargs --->
```python
import argparse
import argclass

class Parser(argclass.Parser):
    """Application with custom help formatting."""
    name: str = "World"

# All ArgumentParser parameters work
parser = Parser(
    prog="myapp",
    usage="%(prog)s [options]",
    formatter_class=argparse.RawDescriptionHelpFormatter,
    epilog="Examples:\n  myapp --name Alice",
    add_help=True,
    allow_abbrev=False,  # Disable abbreviated flags
)
parser.parse_args([])
assert parser.name == "World"
```

:::{tip}
**Rule of thumb:** If you find yourself thinking "I need raw argparse for this,"
try it with `argclass.Argument(**kwargs)` first - it probably works.
:::

## Typed Argument Functions

For better IDE support and type checking, use the typed variants. These
provide exact return type information to static analyzers like mypy and
enable precise autocompletion in your editor.

### ArgumentSingle

Use `ArgumentSingle` for arguments that accept exactly one value. Specify
the `type` parameter explicitly for proper type inference in your IDE.

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

Use `ArgumentSequence` for arguments that accept multiple values. The result
is always a list. Use `nargs="*"` for zero-or-more, `nargs="+"` for one-or-more.

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

```{warning}
**Boolean Flag Behavior**

With `bool = True` default, the flag **inverts** the value:
- `--flag` passed → `False` (toggles from True to False)
- No flag passed → `True` (the default)

For a flag that **enables** something when passed, use `default=False`:

    verbose: bool = False
    # --verbose → True, no flag → False  ✓ Common pattern

Flags with `default=True` toggle OFF when passed:

    cache: bool = True
    # --cache → False, no flag → True  ⚠ Inverted!
```

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

Actions define how argument values are stored. Use `STORE_TRUE` for flags
that enable features, `STORE_FALSE` for flags that disable features, and
`COUNT` for arguments that can be repeated (like `-vvv` for verbosity).

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

The `nargs` parameter controls how many values an argument consumes. Use `?`
for zero-or-one, `*` for zero-or-more, `+` for one-or-more, or an integer
for an exact count. This is essential for multi-value arguments.

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

For better readability, use the `Nargs` enum instead of string literals:

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

Use `choices` to restrict an argument to a predefined set of values. The
parser will reject any value not in the list and display valid options in
the error message and `--help` output.

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

## Enum Arguments

For type-safe choices, use `EnumArgument` with Python's `Enum` classes. This
provides compile-time safety and IDE autocompletion while automatically
generating valid choices.

<!--- name: test_args_enum_basic --->
```python
import argclass
from enum import Enum

class Color(Enum):
    RED = "red"
    GREEN = "green"
    BLUE = "blue"

class Parser(argclass.Parser):
    color: Color = argclass.EnumArgument(Color, default="RED")

parser = Parser()
parser.parse_args([])
assert parser.color == Color.RED

parser.parse_args(["--color", "BLUE"])
assert parser.color == Color.BLUE
```

The default can be either an enum member or a string name:

<!--- name: test_args_enum_default_forms --->
```python
import argclass
from enum import IntEnum

class Priority(IntEnum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3

class Parser(argclass.Parser):
    # String default - validated at class definition time
    level1: Priority = argclass.EnumArgument(Priority, default="MEDIUM")
    # Enum member default
    level2: Priority = argclass.EnumArgument(Priority, default=Priority.HIGH)

parser = Parser()
parser.parse_args([])
assert parser.level1 == Priority.MEDIUM
assert parser.level2 == Priority.HIGH
```

### Lowercase Choices

Use `lowercase=True` for user-friendly lowercase input:

<!--- name: test_args_enum_lowercase --->
```python
import argclass
from enum import Enum

class Environment(Enum):
    DEVELOPMENT = "dev"
    STAGING = "stg"
    PRODUCTION = "prod"

class Parser(argclass.Parser):
    env: Environment = argclass.EnumArgument(
        Environment, default="development", lowercase=True
    )

parser = Parser()
parser.parse_args(["--env", "production"])
assert parser.env == Environment.PRODUCTION
```

### Using Enum Values

By default, `EnumArgument` returns the enum member. Use `use_value=True` to
get the enum's value instead:

<!--- name: test_args_enum_use_value --->
```python
import argclass
from enum import IntEnum

class LogLevel(IntEnum):
    DEBUG = 10
    INFO = 20
    WARNING = 30

class Parser(argclass.Parser):
    # Returns enum member
    level: LogLevel = argclass.EnumArgument(LogLevel, default="INFO")
    # Returns enum value (int)
    level_int: int = argclass.EnumArgument(
        LogLevel, default="INFO", use_value=True
    )

parser = Parser()
parser.parse_args([])
assert parser.level == LogLevel.INFO
assert parser.level_int == 20  # The integer value
```

## Type vs Converter

These two parameters serve different purposes in the parsing pipeline:

- **`type`**: Called for each input string during parsing (before collecting)
- **`converter`**: Called once on the final collected result (after parsing)

Use `type` for per-value conversion, `converter` for post-processing the result.

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

Any callable that takes a string and returns the desired type works as a
type converter. This enables parsing dates, URLs, custom formats, or any
domain-specific value types your application needs.

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

## Version Flag

Adding a `--version` flag is a standard CLI feature. Since the version action
requires argparse-specific parameters, add it by overriding the parser
initialization.

<!--- name: test_args_version_basic --->
```python
import argclass

class Parser(argclass.Parser):
    """My application."""
    name: str = "World"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Add version argument to the underlying argparse parser
        self.create_parser().add_argument(
            "-V", "--version",
            action="version",
            version="myapp 1.0.0"
        )

parser = Parser()
parser.parse_args([])
assert parser.name == "World"
# Calling parser.parse_args(["--version"]) would print "myapp 1.0.0" and exit
```

For real applications, read the version from your package metadata:

```python
import argclass
from importlib.metadata import version

class Parser(argclass.Parser):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.create_parser().add_argument(
            "-V", "--version",
            action="version",
            version=f"%(prog)s {version('mypackage')}"
        )

# Running: myapp --version
# Output: myapp 1.2.3
```

The `%(prog)s` placeholder is replaced with the program name automatically.

You can also include additional information in the version output:

```python
import argclass
import sys

class Parser(argclass.Parser):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.create_parser().add_argument(
            "-V", "--version",
            action="version",
            version=f"myapp 1.0.0 (Python {sys.version_info.major}.{sys.version_info.minor})"
        )

# Running: myapp --version
# Output: myapp 1.0.0 (Python 3.12)
```

## Mutually Exclusive Arguments

Sometimes you need arguments where only one can be specified at a time, like
`--verbose` vs `--quiet`. argclass supports this through validation.

### Using Literal Types

The cleanest approach for mutually exclusive choices is to use a single argument
with `Literal` type:

<!--- name: test_args_mutex_literal --->
```python
import argclass
from typing import Literal

class Parser(argclass.Parser):
    """Application with verbosity level."""
    verbosity: Literal["quiet", "normal", "verbose"] = "normal"

parser = Parser()
parser.parse_args(["--verbosity", "verbose"])
assert parser.verbosity == "verbose"
```

### Manual Validation

For flags that need to be mutually exclusive, validate in `__call__`:

<!--- name: test_args_mutex_manual --->
```python
import argclass

class Parser(argclass.Parser):
    verbose: bool = False
    quiet: bool = False

    def __call__(self) -> int:
        if self.verbose and self.quiet:
            raise ValueError("Cannot use --verbose and --quiet together")
        return 0

parser = Parser()
parser.parse_args(["--verbose"])
assert parser() == 0
```

### Validation with Custom Error Messages

For better error handling, validate before using values:

<!--- name: test_args_mutex_validate --->
```python
import argclass

class Parser(argclass.Parser):
    json_output: bool = False
    yaml_output: bool = False
    csv_output: bool = False

    def validate(self) -> None:
        """Validate mutually exclusive options."""
        selected = sum([self.json_output, self.yaml_output, self.csv_output])
        if selected > 1:
            raise ValueError("Only one output format can be specified")

    def get_format(self) -> str:
        """Get selected output format."""
        self.validate()
        if self.json_output:
            return "json"
        if self.yaml_output:
            return "yaml"
        if self.csv_output:
            return "csv"
        return "text"  # Default

parser = Parser()
parser.parse_args(["--json-output"])
assert parser.get_format() == "json"
```

### Using argparse Directly

For full argparse mutually exclusive groups with `--help` integration, use
the underlying parser directly. Note that these arguments won't be accessible
as class attributes:

```python
import argclass

class Parser(argclass.Parser):
    name: str = "default"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Add mutex group to underlying argparse
        group = self.create_parser().add_mutually_exclusive_group()
        group.add_argument("--verbose", action="store_true")
        group.add_argument("--quiet", action="store_true")

# These arguments appear in --help but are accessed via argparse namespace
# parser.create_parser().parse_args(args).verbose
```

This provides `--help` output showing the mutual exclusion, but requires
accessing values through the underlying argparse namespace.
