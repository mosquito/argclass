# Error Handling

argclass inherits error handling from Python's `argparse`.

## Exit Codes

| Exit Code | Meaning | Triggered By |
|-----------|---------|--------------|
| `0` | Success | `__call__` returns `0` |
| `1` | Application error | `__call__` returns non-zero |
| `2` | Syntax error | Invalid arguments, missing required args, type errors |

## Validation Rules

### Built-in Validation

argparse validates automatically:

- **Required arguments**: No default → argument is required
- **Type conversion**: Type annotation determines converter (`int`, `float`, `Path`, etc.)
- **Choices**: Values must match `choices` list if specified
- **Nargs**: Correct number of values must be provided

All validation errors exit with code 2.

### Custom Validation

Two approaches:

**1. Type converter** — validates during parsing:

<!--- name: test_error_converter --->
```python
import argparse
import argclass

def positive_int(value: str) -> int:
    num = int(value)
    if num <= 0:
        raise argparse.ArgumentTypeError(f"{value} must be positive")
    return num

class Parser(argclass.Parser):
    count: int = argclass.Argument(default=1, type=positive_int)

parser = Parser()
parser.parse_args(["--count", "5"])
assert parser.count == 5
```

**2. Post-parse validation** — validates after all arguments are parsed:

<!--- name: test_error_post_validate --->
```python
import argclass

class Parser(argclass.Parser):
    start: int = 0
    end: int = 100

    def validate(self) -> None:
        if self.start >= self.end:
            raise ValueError("start must be less than end")

parser = Parser()
parser.parse_args(["--start", "50", "--end", "25"])

try:
    parser.validate()
except ValueError as e:
    assert "start must be less than end" in str(e)
```

## Application Exit Codes

Use `__call__` to return application-level exit codes:

<!--- name: test_error_exit_code --->
```python
import argclass

class Parser(argclass.Parser):
    config: str | None = None

    def __call__(self) -> int:
        if self.config is None:
            print("Error: --config is required")
            return 1
        return 0

parser = Parser()
parser.parse_args([])
exit_code = parser()
assert exit_code == 1
```

---

## Customization

### Program Name

```python
import argclass

parser = argclass.Parser(prog="myapp")
# Errors show "myapp: error:" instead of script name
```

### Custom Error Handler

Override `error()` for custom error formatting:

```python
import sys
import argclass

class Parser(argclass.Parser):
    def error(self, message: str) -> None:
        sys.stderr.write(f"ERROR: {message}\n")
        sys.exit(2)
```

## Config and Environment Errors

| Source | Behavior |
|--------|----------|
| Missing config file | Silently ignored (unless `strict_config=True`) |
| Malformed config | Silently ignored (unless `strict_config=True`) |
| Invalid env var value | Same as CLI — exits with code 2 |
| Config provides value | Does NOT make argument "provided" — CLI can still override |

## Testing

Catch `SystemExit` to test error handling:

<!--- name: test_error_catch_exit --->
```python
import argclass
import sys
from io import StringIO

class Parser(argclass.Parser):
    count: int = 1

parser = Parser()
old_stderr = sys.stderr
sys.stderr = StringIO()

try:
    parser.parse_args(["--count", "invalid"])
except SystemExit as e:
    assert e.code == 2
    assert "invalid int value" in sys.stderr.getvalue()
finally:
    sys.stderr = old_stderr
```

For pytest, use `capsys` fixture instead of manual stderr capture.

---

## argclass Exceptions

argclass provides typed exceptions with structured context for debugging
configuration and type errors at definition time.

### Exception Hierarchy

All exceptions inherit from `ArgclassError`, which provides common attributes
for debugging:

| Exception | Raised When | Key Attributes |
|-----------|-------------|----------------|
| `ArgclassError` | Base exception for all argclass errors | `field_name`, `hint` |
| `ArgumentDefinitionError` | Argument conflicts with argparse or invalid configuration | `aliases`, `kwargs` |
| `TypeConversionError` | Converter function fails during parsing | `value`, `target_type` |
| `ConfigurationError` | Config file cannot be parsed or contains invalid values | `file_path`, `section` |
| `EnumValueError` | Invalid enum default or value provided | `enum_class`, `valid_values` |
| `ComplexTypeError` | Unsupported type annotation that requires explicit converter | `typespec` |

### Catching Exceptions

Use specific exception types to handle different error categories:

<!--- name: test_exception_catching --->
```python
import argclass

class Parser(argclass.Parser):
    count: int = 1

parser = Parser()

try:
    parser.parse_args(["--count", "abc"])
except SystemExit:
    # argparse handles type conversion errors with SystemExit
    pass
```

For definition-time errors (raised when the parser class is constructed):

<!--- name: test_exception_definition --->
```python
import argclass
from enum import Enum

class Color(Enum):
    RED = "red"
    GREEN = "green"

try:
    # This would raise EnumValueError if "yellow" is not a valid Color
    class Parser(argclass.Parser):
        color: Color = argclass.EnumArgument(Color, default=Color.RED)
except argclass.EnumValueError as e:
    print(f"Invalid enum: {e.valid_values}")
```

### Exception Attributes

Each exception type includes contextual attributes for debugging:

```python
import argclass

# ArgclassError base attributes (available on all exceptions):
# - field_name: str | None - The field that caused the error
# - hint: str | None - Suggestion for fixing the error
# - message: str - The error message

# ArgumentDefinitionError adds:
# - aliases: tuple[str, ...] | None - Argument aliases that conflicted
# - kwargs: dict | None - The kwargs passed to argparse

# TypeConversionError adds:
# - value: Any - The value that failed conversion
# - target_type: type | None - The type we tried to convert to

# ConfigurationError adds:
# - file_path: str | None - Path to the config file
# - section: str | None - Config section with the error

# EnumValueError adds:
# - enum_class: type | None - The enum class
# - valid_values: tuple[str, ...] | None - Valid enum member names

# ComplexTypeError adds:
# - typespec: Any - The type annotation that couldn't be handled
```

### When Exceptions Are Raised

| Phase | Exception Types | Example |
|-------|-----------------|---------|
| Class definition | `ArgumentDefinitionError`, `EnumValueError`, `ComplexTypeError` | Invalid default for enum |
| Config loading | `ConfigurationError` | Malformed INI file |
| Argument parsing | `TypeConversionError` (wrapped by argparse) | `--count abc` for `int` field |

:::{note}
During argument parsing, most type conversion errors are caught by argparse
and converted to `SystemExit(2)`. The `TypeConversionError` is primarily
raised during config file value conversion or custom converter failures.
:::
