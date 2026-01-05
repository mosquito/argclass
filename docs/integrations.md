# Third-Party Integrations

**argclass** builds on the standard library's `argparse`, so many argparse
extensions work with argclass.

## Rich Help Output

Use `rich_argparse` for beautiful help formatting:

```python
import argclass

class Parser(argclass.Parser):
    verbose: bool = False
    output: str = "result.txt"

# Requires: pip install rich-argparse
# from rich_argparse import RawTextRichHelpFormatter
# parser = Parser(formatter_class=RawTextRichHelpFormatter)
# parser.print_help()
```

![Help Output](_static/rich_example.png)

---

## Logging Configuration

argclass provides a pre-built `LogLevel` argument for easy logging integration.
It accepts level names (`debug`, `info`, `warning`, `error`, `critical`)
case-insensitively and returns the corresponding `logging` module constant.

### Using the Built-in LogLevel

<!--- name: test_integrations_loglevel --->
```python
import argclass
import logging

class Parser(argclass.Parser):
    log_level: int = argclass.LogLevel

parser = Parser()
parser.parse_args(["--log-level", "debug"])

assert parser.log_level == logging.DEBUG
logging.basicConfig(level=parser.log_level)
```

### Custom Logging Setup

For more control, combine `LogLevel` with additional options:

```python
import argclass
import logging

class Parser(argclass.Parser):
    log_level: int = argclass.LogLevel
    log_file: str | None = argclass.Argument(
        "--log-file",
        default=None,
        help="Log to file instead of stderr"
    )

    def configure_logging(self) -> None:
        handlers = []
        if self.log_file:
            handlers.append(logging.FileHandler(self.log_file))
        else:
            handlers.append(logging.StreamHandler())

        logging.basicConfig(
            level=self.log_level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=handlers,
            force=True,
        )

parser = Parser()
parser.parse_args([])
parser.configure_logging()
```

## pytest Integration

Test your CLI with pytest:

<!--- name: test_integrations_pytest --->
```python
import pytest
import argclass

class Parser(argclass.Parser):
    name: str
    count: int = 1

@pytest.fixture()
def parser():
    parser = Parser()
    parser.parse_args(["--name", "test"])
    return parser

def test_parser_defaults(parser):
    assert parser.name == "test"
    assert parser.count == 1
```

---

## Accessing the Underlying ArgumentParser

Use `create_parser()` to get the underlying `argparse.ArgumentParser` instance
for integrations that need direct access to the parser structure:

<!--- name: test_integrations_create_parser --->
```python
import argclass

class Parser(argclass.Parser):
    """My application."""
    name: str = argclass.Argument(help="User name")
    verbose: bool = False

parser = Parser()
argparse_parser = parser.create_parser()

# Inspect parser structure
assert len(argparse_parser._actions) > 0

# Access help text
help_text = argparse_parser.format_help()
assert "User name" in help_text
```

This is useful for tools that inspect argument structure, generate documentation,
or need argparse compatibility.

:::{warning}
`create_parser()` does **not** back populate parser attributes.
Always use `parse_args()` to actually parse command-line arguments.
:::
