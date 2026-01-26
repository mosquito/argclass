# Migrating from argparse

This guide helps you migrate existing argparse code to argclass. The good news:
argclass is built on argparse, so your existing knowledge transfers directly,
and you can migrate incrementally.

## Side-by-Side Comparison

### Basic Arguments

**argparse:**
<!--- name: test_migration_argparse_basic --->
```python
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--host", default="localhost")
parser.add_argument("--port", type=int, default=8080)
parser.add_argument("--verbose", "-v", action="store_true")

args = parser.parse_args([])
assert args.host == "localhost"
assert args.port == 8080
```

**argclass:**
<!--- name: test_migration_argclass_basic --->
```python
import argclass

class Parser(argclass.Parser):
    host: str = "localhost"
    port: int = 8080
    verbose: bool = argclass.Argument("-v", default=False)

parser = Parser()
parser.parse_args([])
assert parser.host == "localhost"
assert parser.port == 8080
```

**Key differences:**
- Type hints replace `type=int` parameters
- Default values are Python assignments, not keyword arguments
- Accessing values: `parser.host` instead of `args.host`
- IDE autocompletion works with argclass

### Required Arguments

**argparse:**
<!--- name: test_migration_argparse_required --->
```python
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--name", required=True)
parser.add_argument("--count", type=int, required=True)

args = parser.parse_args(["--name", "test", "--count", "5"])
assert args.name == "test"
assert args.count == 5
```

**argclass:**
<!--- name: test_migration_argclass_required --->
```python
import argclass

class Parser(argclass.Parser):
    name: str              # Required: no default value
    count: int             # Required: no default value

parser = Parser()
parser.parse_args(["--name", "test", "--count", "5"])
assert parser.name == "test"
assert parser.count == 5
```

Arguments without defaults are required. It's that simple.

### Boolean Flags

**argparse:**
<!--- name: test_migration_argparse_boolean --->
```python
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--debug", action="store_true")
parser.add_argument("--no-cache", action="store_false", dest="cache")

args = parser.parse_args(["--debug", "--no-cache"])
assert args.debug is True
assert args.cache is False
```

**argclass:**
<!--- name: test_migration_argclass_boolean --->
```python
import argclass

class Parser(argclass.Parser):
    debug: bool = False     # --debug sets to True
    cache: bool = True      # --cache sets to False (inverts)

parser = Parser()
parser.parse_args(["--debug", "--cache"])
assert parser.debug is True
assert parser.cache is False
```

```{warning}
Boolean flag behavior differs from argparse! In argclass:
- `bool = False` → flag sets to `True` (like `store_true`)
- `bool = True` → flag sets to `False` (like `store_false`)

This can be confusing. See [Boolean Flags](arguments.md#boolean-flags) for details.
```

### Positional Arguments

**argparse:**
<!--- name: test_migration_argparse_positional --->
```python
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("filename")
parser.add_argument("targets", nargs="+")

args = parser.parse_args(["input.txt", "target1", "target2"])
assert args.filename == "input.txt"
assert args.targets == ["target1", "target2"]
```

**argclass:**
<!--- name: test_migration_argclass_positional --->
```python
import argclass

class Parser(argclass.Parser):
    filename: str = argclass.Argument("filename")
    targets: list[str] = argclass.Argument("targets", nargs="+")

parser = Parser()
parser.parse_args(["input.txt", "target1", "target2"])
assert parser.filename == "input.txt"
assert parser.targets == ["target1", "target2"]
```

Positional arguments require `argclass.Argument()` with the name as the first parameter.

### Multiple Values (nargs)

**argparse:**
<!--- name: test_migration_argparse_nargs --->
```python
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--files", nargs="+")
parser.add_argument("--tags", nargs="*", default=[])
parser.add_argument("--coords", nargs=3, type=float)

args = parser.parse_args([
    "--files", "a.txt", "b.txt",
    "--coords", "1.0", "2.0", "3.0"
])
assert args.files == ["a.txt", "b.txt"]
assert args.tags == []
assert args.coords == [1.0, 2.0, 3.0]
```

**argclass:**
<!--- name: test_migration_argclass_nargs --->
```python
import argclass

class Parser(argclass.Parser):
    # Simpler: use collection types directly
    files: list[str]                              # nargs="+" automatic
    tags: list[str] = argclass.Argument(nargs="*", default=[])
    coords: list[float] = argclass.Argument(nargs=3)

parser = Parser()
parser.parse_args([
    "--files", "a.txt", "b.txt",
    "--coords", "1.0", "2.0", "3.0"
])
assert parser.files == ["a.txt", "b.txt"]
assert parser.tags == []
assert parser.coords == [1.0, 2.0, 3.0]
```

### Choices

**argparse:**
<!--- name: test_migration_argparse_choices --->
```python
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--level", choices=["debug", "info", "warning", "error"], default="info")

args = parser.parse_args(["--level", "debug"])
assert args.level == "debug"
```

**argclass:**
<!--- name: test_migration_argclass_choices --->
```python
import argclass
from typing import Literal

class Parser(argclass.Parser):
    # Option 1: Literal type (recommended - type-safe)
    level: Literal["debug", "info", "warning", "error"] = "info"

    # Option 2: choices parameter (same as argparse)
    format: str = argclass.Argument(
        choices=["json", "yaml", "toml"],
        default="json"
    )

parser = Parser()
parser.parse_args(["--level", "debug"])
assert parser.level == "debug"
```

`Literal` types are preferred because they provide compile-time type checking.

### Argument Groups

**argparse:**
<!--- name: test_migration_argparse_groups --->
```python
import argparse

parser = argparse.ArgumentParser()
db_group = parser.add_argument_group("database")
db_group.add_argument("--db-host", default="localhost")
db_group.add_argument("--db-port", type=int, default=5432)

args = parser.parse_args(["--db-host", "prod.db"])
assert args.db_host == "prod.db"
assert args.db_port == 5432
```

**argclass:**
<!--- name: test_migration_argclass_groups --->
```python
import argclass

class DatabaseGroup(argclass.Group):
    host: str = "localhost"
    port: int = 5432

class Parser(argclass.Parser):
    db = DatabaseGroup()

parser = Parser()
parser.parse_args(["--db-host", "prod.db"])
assert parser.db.host == "prod.db"
assert parser.db.port == 5432
```

Groups in argclass are reusable classes. The prefix (`db-`) is automatic.

### Subcommands (Subparsers)

**argparse:**
<!--- name: test_migration_argparse_subparsers --->
```python
import argparse

parser = argparse.ArgumentParser()
subparsers = parser.add_subparsers(dest="command")

init_parser = subparsers.add_parser("init")
init_parser.add_argument("--force", action="store_true")

run_parser = subparsers.add_parser("run")
run_parser.add_argument("--port", type=int, default=8080)

args = parser.parse_args(["init", "--force"])
assert args.command == "init"
assert args.force is True
```

**argclass:**
<!--- name: test_migration_argclass_subparsers --->
```python
import argclass

class InitCommand(argclass.Parser):
    force: bool = False

class RunCommand(argclass.Parser):
    port: int = 8080

class CLI(argclass.Parser):
    init = InitCommand()
    run = RunCommand()

cli = CLI()
cli.parse_args(["init", "--force"])
assert cli.init.force is True
```

Subcommands are nested parser classes. Much cleaner!

### Help Text

**argparse:**
<!--- name: test_migration_argparse_help --->
```python
import argparse

parser = argparse.ArgumentParser()
parser.add_argument(
    "--config",
    help="Path to configuration file",
    metavar="FILE",
    default="config.ini"
)

args = parser.parse_args([])
assert args.config == "config.ini"
```

**argclass:**
<!--- name: test_migration_argclass_help --->
```python
import argclass

class Parser(argclass.Parser):
    config: str = argclass.Argument(
        help="Path to configuration file",
        metavar="FILE",
        default="config.ini"
    )

parser = Parser()
parser.parse_args([])
assert parser.config == "config.ini"
```

All argparse parameters work with `argclass.Argument()`.

## Features argclass Adds

These features have no direct argparse equivalent:

### Config File Support

<!--- name: test_migration_config --->
```python
import argclass
from tempfile import NamedTemporaryFile
from pathlib import Path

class Parser(argclass.Parser):
    host: str = "localhost"

# Create test config
with NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
    f.write("[DEFAULT]\nhost = example.com\n")
    config_path = f.name

parser = Parser(config_files=[config_path])
parser.parse_args([])
assert parser.host == "example.com"

Path(config_path).unlink()
```

### Environment Variables

<!--- name: test_migration_env --->
```python
import os
import argclass

os.environ["MYAPP_HOST"] = "from-env.com"

class Parser(argclass.Parser):
    host: str = "localhost"

parser = Parser(auto_env_var_prefix="MYAPP_")
parser.parse_args([])
assert parser.host == "from-env.com"

del os.environ["MYAPP_HOST"]
```

### Secret Handling

<!--- name: test_migration_secrets --->
```python
import os
import argclass

os.environ["API_KEY"] = "secret123"

class Parser(argclass.Parser):
    api_key: str = argclass.Secret(env_var="API_KEY")

parser = Parser()
parser.parse_args([])
assert parser.api_key == "secret123"

# Clean up secrets from environment
parser.sanitize_env()
assert "API_KEY" not in os.environ
```

## Migration Strategy

### Gradual Migration

You don't have to migrate everything at once. argclass can coexist with
argparse code:

<!--- name: test_migration_coexist --->
```python
import argparse
import argclass

# New code uses argclass
class NewFeature(argclass.Parser):
    enable_feature: bool = False
    feature_level: int = 1

# Existing argparse code stays unchanged
legacy_parser = argparse.ArgumentParser()
legacy_parser.add_argument("--old-option", default="legacy")

# Both can be used in the same application
new_parser = NewFeature()
new_parser.parse_args([])
legacy_args = legacy_parser.parse_args([])

assert new_parser.enable_feature is False
assert legacy_args.old_option == "legacy"
```

### Step-by-Step Process

1. **Start with new code** - Write new CLI features using argclass
2. **Identify candidates** - Look for parsers with many arguments or groups
3. **Migrate one parser at a time** - Convert argparse to argclass incrementally
4. **Add config/env support** - Enhance with argclass-specific features
5. **Update tests** - argclass parsers are easier to test as regular objects

### What Transfers Directly

These argparse concepts work identically in argclass:

- `nargs` values: `?`, `*`, `+`, integers
- `action` values: `store`, `store_true`, `store_false`, `count`, `append`, `version`
- `choices` parameter
- `metavar` parameter
- `help` parameter
- `default` parameter
- `type` parameter (callable converters)

### What Changes

| argparse | argclass | Notes |
|----------|----------|-------|
| `parser.add_argument()` | Class field with type hint | Simpler syntax |
| `args = parser.parse_args()` | `parser.parse_args()` | Access via `parser.field` |
| `args.some_field` | `parser.some_field` | Dot notation same |
| `add_argument_group()` | Nested `argclass.Group` | Reusable, composable |
| `add_subparsers()` | Nested `argclass.Parser` | Cleaner nesting |
| `required=True` | No default value | Pythonic |
| `dest="name"` | Field name | Automatic |

### Common Migration Mistakes

Watch out for these common issues when migrating from argparse:

**1. Accessing parsed values incorrectly**

<!--- name: test_migration_mistake_access --->
```python
import argclass

class Parser(argclass.Parser):
    host: str = "localhost"

parser = Parser()

# argparse pattern returns namespace - but argclass stores on parser itself
parser.parse_args([])

# Correct: access via parser attribute
assert parser.host == "localhost"
```

**2. Field name is the destination**

<!--- name: test_migration_mistake_dest --->
```python
import argclass

class Parser(argclass.Parser):
    # Field name IS the destination - no dest parameter needed
    host_name: str = "localhost"  # Creates --host-name flag

parser = Parser()
parser.parse_args(["--host-name", "example.com"])
assert parser.host_name == "example.com"
```

**3. Omit default for required arguments**

<!--- name: test_migration_mistake_required --->
```python
import argclass

class Parser(argclass.Parser):
    # No default = required (no need for required=True)
    name: str

parser = Parser()
parser.parse_args(["--name", "test"])
assert parser.name == "test"
```

**4. Boolean flag default confusion**

<!--- name: test_migration_mistake_bool --->
```python
import argclass

class GoodParser(argclass.Parser):
    # Correct: default=False, --verbose sets to True
    verbose: bool = False

class BadParser(argclass.Parser):
    # Confusing: default=True, --verbose sets to False!
    verbose: bool = True

good = GoodParser()
good.parse_args(["--verbose"])
assert good.verbose is True  # Expected behavior

bad = BadParser()
bad.parse_args(["--verbose"])
assert bad.verbose is False  # Inverted - often not what you want!
```

**5. Positional argument name must match**

<!--- name: test_migration_mistake_positional --->
```python
import argclass

class Parser(argclass.Parser):
    # Correct: positional name matches field name
    input_file: str = argclass.Argument("input_file")

parser = Parser()
parser.parse_args(["myfile.txt"])
assert parser.input_file == "myfile.txt"
```

### Advanced argparse Features

These argparse features work in argclass because all kwargs pass through:

<!--- name: test_migration_fromfile --->
```python
import argclass
from tempfile import NamedTemporaryFile
from pathlib import Path

class Parser(argclass.Parser):
    name: str = "default"

# fromfile_prefix_chars - read args from file
parser = Parser(fromfile_prefix_chars="@")

# Create a file with arguments
with NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
    f.write("--name\nfromfile")
    args_file = f.name

parser.parse_args([f"@{args_file}"])
assert parser.name == "fromfile"

Path(args_file).unlink()
```

The key insight: **argclass doesn't wrap or limit argparse - it enhances it**.
Any argparse tutorial or Stack Overflow answer applies directly to argclass.

## Sample `--help` Output

Here's what the migrated argclass parser produces:

```
$ python app.py --help
usage: app.py [-h] [--host HOST] [--port PORT] [-v]

options:
  -h, --help            show this help message and exit
  --host HOST           (default: localhost)
  --port PORT           (default: 8080)
  -v, --verbose         (default: False)
```

The output is identical to argparse because argclass builds on it!
