# Frequently Asked Questions

Common questions and answers about argclass.

## Arguments

### How do I make an argument required?

Don't provide a default value. Arguments without defaults are automatically required.

<!--- name: test_faq_required --->
```python
import argclass

class Parser(argclass.Parser):
    required_arg: str      # Required - no default
    optional_arg: str = "default"  # Optional - has default

parser = Parser()
parser.parse_args(["--required-arg", "value"])
assert parser.required_arg == "value"
assert parser.optional_arg == "default"
```

### How do I create a positional argument?

Pass the argument name (without dashes) as the first parameter to `Argument()`:

<!--- name: test_faq_positional --->
```python
import argclass

class Parser(argclass.Parser):
    filename: str = argclass.Argument("filename", help="Input file")
    output: str = "out.txt"  # Named optional

parser = Parser()
parser.parse_args(["input.txt"])
assert parser.filename == "input.txt"
```

### Why does my boolean flag not work as expected?

The most common issue is using `bool = True` expecting `--flag` to enable something.
In argclass, `bool = True` means the flag **disables** (sets to False):

<!--- name: test_faq_bool --->
```python
import argclass

class Parser(argclass.Parser):
    # --verbose enables (sets to True)
    verbose: bool = False

    # --cache DISABLES (sets to False) - often confusing!
    cache: bool = True

parser = Parser()
parser.parse_args(["--verbose", "--cache"])
assert parser.verbose is True   # Enabled
assert parser.cache is False    # Disabled!
```

**Rule of thumb:** Use `bool = False` for features you want to enable with a flag.

### How do I add a `--version` flag?

Override `__init__` and add it to the underlying argparse parser:

<!--- name: test_faq_version --->
```python
import argclass

class Parser(argclass.Parser):
    name: str = "World"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.create_parser().add_argument(
            "-V", "--version",
            action="version",
            version="myapp 1.0.0"
        )

parser = Parser()
parser.parse_args([])
assert parser.name == "World"
```

### How do I accept multiple values for an argument?

Use a collection type hint like `list[str]`:

<!--- name: test_faq_multiple --->
```python
import argclass

class Parser(argclass.Parser):
    files: list[str]  # Accepts: --files a.txt b.txt c.txt
    tags: list[str] = []  # Optional, defaults to empty list

parser = Parser()
parser.parse_args(["--files", "a.txt", "b.txt"])
assert parser.files == ["a.txt", "b.txt"]
```

### How do I restrict values to specific choices?

Use `Literal` types (recommended) or the `choices` parameter:

<!--- name: test_faq_choices --->
```python
import argclass
from typing import Literal

class Parser(argclass.Parser):
    # Literal type - type-safe, IDE support
    level: Literal["debug", "info", "error"] = "info"

    # choices parameter - same as argparse
    format: str = argclass.Argument(
        choices=["json", "yaml"],
        default="json"
    )

parser = Parser()
parser.parse_args(["--level", "debug"])
assert parser.level == "debug"
```

## Configuration

### How do I load settings from a config file?

Pass config file paths to the parser constructor:

<!--- name: test_faq_config --->
```python
import argclass
from tempfile import NamedTemporaryFile
from pathlib import Path

class Parser(argclass.Parser):
    host: str = "localhost"
    port: int = 8080

with NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
    f.write("[DEFAULT]\nhost = example.com\nport = 9000\n")
    config_path = f.name

parser = Parser(config_files=[config_path])
parser.parse_args([])
assert parser.host == "example.com"
assert parser.port == 9000

Path(config_path).unlink()
```

### What's the priority order for config sources?

CLI arguments override environment variables, which override config files:

```
CLI arguments  >  Environment variables  >  Config files  >  Code defaults
```

### How do I read from environment variables?

Use `env_var` parameter or `auto_env_var_prefix`:

<!--- name: test_faq_env --->
```python
import os
import argclass

os.environ["MYAPP_HOST"] = "from-env.com"

class Parser(argclass.Parser):
    host: str = "localhost"

# Auto-prefix generates MYAPP_HOST from "host"
parser = Parser(auto_env_var_prefix="MYAPP_")
parser.parse_args([])
assert parser.host == "from-env.com"

del os.environ["MYAPP_HOST"]
```

## Security

### How do I handle passwords and API keys?

Use `argclass.Secret()` which masks values in logs and can sanitize the environment:

<!--- name: test_faq_secret --->
```python
import os
import argclass

os.environ["DB_PASSWORD"] = "secret123"

class Parser(argclass.Parser):
    password: str = argclass.Secret(env_var="DB_PASSWORD")

parser = Parser()
parser.parse_args([])

# Value is accessible for use in code
assert parser.password == "secret123"

# But masked in repr() - safe for logging
assert "secret123" not in repr(parser.password)
assert "******" in repr(parser.password)

# Remove from environment after parsing
parser.sanitize_env()
assert "DB_PASSWORD" not in os.environ
```

### Why should I call `sanitize_env()`?

Environment variables are inherited by child processes. If your application spawns
subprocesses, they could access secrets from the environment. `sanitize_env()`
removes secret values after parsing to prevent this.

## Groups and Subcommands

### How do I organize related arguments?

Use `argclass.Group` to bundle related arguments with automatic prefixing:

<!--- name: test_faq_group --->
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
```

### How do I create subcommands like `git commit`?

Nest parser classes:

<!--- name: test_faq_subcommand --->
```python
import argclass

class AddCommand(argclass.Parser):
    files: list[str]

class CommitCommand(argclass.Parser):
    message: str = argclass.Argument("-m", "--message")

class Git(argclass.Parser):
    add = AddCommand()
    commit = CommitCommand()

git = Git()
git.parse_args(["commit", "-m", "Initial commit"])
assert git.commit.message == "Initial commit"
```

### How do I know which subcommand was selected?

Check `current_subparsers` or implement `__call__` on subcommands:

<!--- name: test_faq_which_subcommand --->
```python
import argclass

class Build(argclass.Parser):
    output: str = "dist"
    def __call__(self) -> int:
        return 0

class Test(argclass.Parser):
    verbose: bool = False
    def __call__(self) -> int:
        return 0

class CLI(argclass.Parser):
    build = Build()
    test = Test()

cli = CLI()
cli.parse_args(["build", "--output", "out"])

# Option 1: Check current_subparsers - contains the selected parser(s)
selected = cli.current_subparsers
assert len(selected) == 1
assert isinstance(selected[0], Build)

# Option 2: Call the CLI - dispatches to selected subcommand
assert cli() == 0
```

## Testing

### How do I test my CLI parser?

Create parser instances and call `parse_args()` with test arguments:

<!--- name: test_faq_testing --->
```python
import argclass

class Parser(argclass.Parser):
    name: str
    count: int = 1

def test_parser():
    parser = Parser()
    parser.parse_args(["--name", "test", "--count", "5"])
    assert parser.name == "test"
    assert parser.count == 5

test_parser()
```

### How do I test with environment variables?

Use pytest's `monkeypatch` fixture or set/delete manually:

<!--- name: test_faq_test_env --->
```python
import os
import argclass

class Parser(argclass.Parser):
    host: str = argclass.Argument(env_var="TEST_HOST", default="localhost")

# Set environment for test
os.environ["TEST_HOST"] = "test-host"

parser = Parser()
parser.parse_args([])
assert parser.host == "test-host"

# Cleanup
del os.environ["TEST_HOST"]
```

## Compatibility

### Can I use argclass with existing argparse code?

Yes, argclass is built on argparse and can coexist:

<!--- name: test_faq_compat --->
```python
import argparse
import argclass

# New code with argclass
class NewParser(argclass.Parser):
    feature: bool = False

# Legacy argparse code
legacy = argparse.ArgumentParser()
legacy.add_argument("--old-flag", action="store_true")

new = NewParser()
new.parse_args([])
args = legacy.parse_args([])

assert new.feature is False
assert args.old_flag is False
```

### Does argclass work with argparse extensions like rich-argparse?

Yes, use `formatter_class` and other argparse parameters:

<!--- name: test_faq_formatter --->
```python
import argparse
import argclass

class Parser(argclass.Parser):
    name: str = "World"

# Use any argparse formatter class
parser = Parser(formatter_class=argparse.RawDescriptionHelpFormatter)
parser.parse_args([])
assert parser.name == "World"
```

### How do I add shell tab completion?

Use `argcomplete` with the underlying argparse parser via `create_parser()`:

<!--- name: test_faq_argcomplete --->
```python
import argclass

class Parser(argclass.Parser):
    name: str
    format: str = argclass.Argument(choices=["json", "yaml"], default="json")

parser = Parser()

# Enable shell completion (requires: pip install argcomplete)
try:
    import argcomplete
    argcomplete.autocomplete(parser.create_parser())
except ImportError:
    pass

parser.parse_args(["--name", "test"])
assert parser.name == "test"
```

See the [Integrations guide](integrations.md#shell-completions) for full setup
instructions including bash and zsh configuration.

### Can I use argparse features that argclass doesn't explicitly document?

Yes. argclass passes all `**kwargs` through to argparse. If a feature isn't
explicitly documented in argclass, try using it anyway - it will work if
argparse supports it:

<!--- name: test_faq_argparse_passthrough --->
```python
import argclass

class Parser(argclass.Parser):
    # Using argparse's 'const' parameter (not documented in argclass)
    mode: str = argclass.Argument(
        "--mode",
        nargs="?",
        const="auto",  # Value when flag given without argument
        default="manual",  # Value when flag not given at all
    )

parser = Parser()

# No flag: default value
parser.parse_args([])
assert parser.mode == "manual"

# Flag with value: explicit value
parser.parse_args(["--mode", "custom"])
assert parser.mode == "custom"
```

**Rule of thumb:** If you find yourself thinking "I need raw argparse for this,"
try it with `argclass.Argument(**kwargs)` first - it probably works.

## Troubleshooting

### Why am I getting "argument is required" errors?

Check if you forgot to provide a default value, or if you're using `str | None`
which implies `default=None` (making it optional):

<!--- name: test_faq_optional_type --->
```python
import argclass

class Parser(argclass.Parser):
    # This is OPTIONAL because str | None implies default=None
    config: str | None

parser = Parser()
parser.parse_args([])
assert parser.config is None  # Not required!
```

### Why doesn't my config file load?

Common issues:
1. **Wrong section name**: Section must match group attribute name (lowercase)
2. **Wrong file format**: Specify `config_parser_class` for JSON/TOML
3. **Missing file**: By default, missing files are silently ignored

<!--- name: test_faq_config_debug --->
```python
import argclass
from tempfile import NamedTemporaryFile
from pathlib import Path

class DatabaseGroup(argclass.Group):
    host: str = "localhost"

class Parser(argclass.Parser):
    database = DatabaseGroup()

# Section name must match group attribute name
config_content = """
[database]
host = prod.db
"""

with NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
    f.write(config_content)
    config_path = f.name

parser = Parser(config_files=[config_path])
parser.parse_args([])
assert parser.database.host == "prod.db"

Path(config_path).unlink()
```
