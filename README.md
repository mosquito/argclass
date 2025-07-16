# argclass

![Coverage](https://coveralls.io/repos/github/mosquito/argclass/badge.svg?branch=master) [![Actions](https://github.com/mosquito/argclass/workflows/tests/badge.svg)](https://github.com/mosquito/argclass/actions?query=workflow%3Atests) [![Latest Version](https://img.shields.io/pypi/v/argclass.svg)](https://pypi.python.org/pypi/argclass/) [![Python Versions](https://img.shields.io/pypi/pyversions/argclass.svg)](https://pypi.python.org/pypi/argclass/) [![License](https://img.shields.io/pypi/l/argclass.svg)](https://pypi.python.org/pypi/argclass/)

A wrapper around the standard `argparse` module that allows you to describe argument parsers declaratively.

By default, the `argparse` module suggests creating parsers imperatively, which is not convenient for type checking and attribute access. Additionally, IDE autocompletion and type hints are not applicable in this case.

This module allows you to declare command-line parsers using classes.

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

As you can see, this example shows basic module usage. When you want to specify argument defaults and other options, you have to use `argclass.Argument`.

## Subparsers

The following example shows how to use subparsers:

```python
import argclass

class SubCommand(argclass.Parser):
    comment: str

    def __call__(self) -> int:
        endpoint: str = self.__parent__.endpoint
        print("Subcommand called", self, "endpoint", endpoint)
        return 0

class Parser(argclass.Parser):
    endpoint: str
    subcommand = SubCommand()

if __name__ == '__main__':
    parser = Parser()
    parser.parse_args()
    exit(parser())
```

The `__call__` method will be called when the subparser is used. Otherwise, help will be printed.

## Value Conversion

If an argument has a generic or composite type, you must explicitly describe it using `argclass.Argument`, specifying a converter function with the `type` or `converter` argument to transform the value after parsing.

The main differences between `type` and `converter` are:

* `type` will be directly passed to the `argparse.ArgumentParser.add_argument` method.
* The `converter` function will be called after parsing the argument.

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

As you can see, the `string_uid` function is called in both cases, but `converter` is applied after parsing the argument.

The following example shows how `type` is applied to each item in a list when using `nargs`:

<!--- name: test_list_converter_example --->
```python
import argclass

class Parser(argclass.Parser):
    numbers = argclass.Argument(nargs=argclass.Nargs.ONE_OR_MORE, type=int)

parser = Parser()
parser.parse_args(["--numbers", "1", "2", "3"])
assert parser.numbers == [1, 2, 3]
```

`type` will be applied to each item in the list of arguments.

If you want to convert a list of strings to a list of integers and then to a `frozenset`, you can use the following example:

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

## Boolean arguments

Boolean arguments can be specified using like this:

<!--- name: test_bools --->
```python
import argclass


class ArgumentParser(argclass.Parser):
    # Complete form you have to set default and action
    stored_true: bool = argclass.Argument(
        action=argclass.Actions.STORE_TRUE,
        default=False
    )
    # Short form with default value
    # This is the alias for: argclass.Argument(action=argclass.Actions.STORE_TRUE, default=False)
    stored_true_short: bool = False
    # This is the alias for: argclass.Argument(action=argclass.Actions.STORE_FALSE, default=True)
    stored_false: bool = True


parser = ArgumentParser(auto_env_var_prefix='APP_')
arguments = parser.parse_args(["--stored-true-short"])
assert arguments.stored_true is False
assert arguments.stored_true_short is True
assert arguments.stored_false is True
```

## Configuration Files

Parser objects can get default values from environment variables or from specified configuration files.

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

When using configuration files, argclass uses Python's `ast.literal_eval` for parsing arguments with `nargs` and 
complex types. This means that in your INI configuration files, you should write values in a syntax that `literal_eval`
can parse for these specific arguments. 

For regular arguments (simple types like strings, integers, booleans), you can write the values as-is.

## Argument Groups

The following example uses `argclass.Argument` and argument groups:

<!-- name: test_argument_groups_example -->
```python
from typing import FrozenSet
import logging
import argclass

class AddressPortGroup(argclass.Group):
    address: str = argclass.Argument(default="127.0.0.1")
    port: int

class Parser(argclass.Parser):
    log_level: int = argclass.LogLevel
    http = AddressPortGroup(title="HTTP options", defaults=dict(port=8080))
    rpc = AddressPortGroup(title="RPC options", defaults=dict(port=9090))
    user_id: FrozenSet[int] = argclass.Argument(
        nargs="*", type=int, converter=frozenset
    )

parser = Parser(
    config_files=[".example.ini", "~/.example.ini", "/etc/example.ini"],
    auto_env_var_prefix="EXAMPLE_"
)
parser.parse_args([])

# Remove all used environment variables from os.environ
parser.sanitize_env()

logging.basicConfig(level=parser.log_level)
logging.info('Listening http://%s:%d', parser.http.address, parser.http.port)
logging.info('Listening rpc://%s:%d', parser.rpc.address, parser.rpc.port)

assert parser.http.address == '127.0.0.1'
assert parser.rpc.address == '127.0.0.1'

assert parser.http.port == 8080
assert parser.rpc.port == 9090
```

Argument groups are sections in the parser configuration. For example, in this case, the configuration file might be:

```ini
[DEFAULT]
log_level=info
user_id=[1, 2, 3]

[http]
port=9001

[rpc]
port=9002
```

Run this script:

```shell
$ python example.py
INFO:root:Listening http://127.0.0.1:8080
INFO:root:Listening rpc://127.0.0.1:9090
```

Example of `--help` output:

```shell
$ python example.py --help
usage: example.py [-h] [--log-level {debug,info,warning,error,critical}]
                  [--http-address HTTP_ADDRESS] [--http-port HTTP_PORT]
                  [--rpc-address RPC_ADDRESS] [--rpc-port RPC_PORT]

optional arguments:
  -h, --help            show this help message and exit
  --log-level {debug,info,warning,error,critical}
                        (default: info) [ENV: EXAMPLE_LOG_LEVEL]

HTTP options:
  --http-address HTTP_ADDRESS
                        (default: 127.0.0.1) [ENV: EXAMPLE_HTTP_ADDRESS]
  --http-port HTTP_PORT
                        (default: 8080) [ENV: EXAMPLE_HTTP_PORT]

RPC options:
  --rpc-address RPC_ADDRESS
                        (default: 127.0.0.1) [ENV: EXAMPLE_RPC_ADDRESS]
  --rpc-port RPC_PORT   (default: 9090) [ENV: EXAMPLE_RPC_PORT]

Default values will be based on the following configuration files ['example.ini',
'~/.example.ini', '/etc/example.ini']. Now 1 file has been applied
['example.ini']. The configuration files are INI-formatted files where
configuration groups are INI sections.
See more https://pypi.org/project/argclass/#configs
```

## Secrets

Arguments that contain sensitive data, such as tokens, encryption keys, or URLs with passwords, when passed through environment variables or a configuration file, can be printed in the output of `--help`. To hide defaults, add the `secret=True` parameter, or use the special default constructor `argclass.Secret` instead of `argclass.Argument`.

```python
import argclass

class HttpAuthentication(argclass.Group):
    username: str = argclass.Argument()
    password: str = argclass.Secret()

class HttpBearerAuthentication(argclass.Group):
    token: str = argclass.Argument(secret=True)

class Parser(argclass.Parser):
    http_basic = HttpAuthentication()
    http_bearer = HttpBearerAuthentication()

parser = Parser()
parser.print_help()
```

### Preventing Secrets from Being Logged

A secret is not actually a string, but a special class inherited from `str`. All attempts to cast this type to a `str` (using the `__str__` method) will return the original value, unless the `__str__` method is called from the `logging` module.

```python
import logging
from argclass import SecretString

logging.basicConfig(level=logging.INFO)
s = SecretString("my-secret-password")
logging.info(s)          # __str__ will be called from logging
logging.info(f"s=%s", s) # __str__ will be called from logging too
logging.info(f"{s!r}")   # repr is safe
logging.info(f"{s}")     # the password will be compromised
```

Of course, this is not absolute sensitive data protection, but it helps prevent accidental logging of these values.

The `repr` for this will always give a placeholder, so it is better to always add `!r` to any f-string, for example `f'{value!r}'`.

## Enum Argument

The library provides a special argument type for working with enumerations. For enum arguments, the `choices` parameter will be generated automatically from the enum names. After parsing the argument, the value will be converted to the enum member.

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

## Config Action

This library provides a base class for writing custom configuration parsers.

`argclass.Config` is a special argument type for parsing configuration files. The optional parameter `config_class` is used to specify the custom configuration parser. By default, it is an INI parser.

### YAML Parser

To parse YAML files, you need to install the `PyYAML` package. Follow code is an implementation of a YAML config parser.

```python
from typing import Mapping, Any
from pathlib import Path
import argclass
import yaml

class YAMLConfigAction(argclass.ConfigAction):
    def parse_file(self, file: Path) -> Mapping[str, Any]:
        with file.open("r") as fp:
            return yaml.load(fp, Loader=yaml.FullLoader)

class YAMLConfigArgument(argclass.ConfigArgument):
    action = YAMLConfigAction

class Parser(argclass.Parser):
    config = argclass.Config(
        required=True,
        config_class=YAMLConfigArgument,
    )
```

### TOML Parser

To parse TOML files, you need to install the `tomli` package. Follow code is an implementation of a TOML config parser.

```python
import tomli
import argclass
from pathlib import Path
from typing import Mapping, Any

class TOMLConfigAction(argclass.ConfigAction):
    def parse_file(self, file: Path) -> Mapping[str, Any]:
        with file.open("rb") as fp:
            return tomli.load(fp)

class TOMLConfigArgument(argclass.ConfigArgument):
    action = TOMLConfigAction

class Parser(argclass.Parser):
    config = argclass.Config(
        required=True,
        config_class=TOMLConfigArgument,
    )
```

## Subparsers Advanced Usage

There are two ways to work with subparsers: either by calling the parser as a regular function, in which case the
subparser must implement the `__call__` method (otherwise help will be printed and the program will exit with an
error), or by directly inspecting the `.current_subparser` attribute in the parser. The second method can be 
simplified using `functools.singledispatch`.

### Using `__call__`

Just implement the `__call__` method for subparsers and call the main parser.

```python
from typing import Optional
import argclass

class AddressPortGroup(argclass.Group):
    address: str = "127.0.0.1"
    port: int = 8080

class CommitCommand(argclass.Parser):
    comment: str = argclass.Argument()

    def __call__(self) -> int:
        endpoint: AddressPortGroup = self.__parent__.endpoint
        print(
            "Commit command called", self,
            "endpoint", endpoint.address, "port", endpoint.port
        )
        return 0

class PushCommand(argclass.Parser):
    comment: str = argclass.Argument()

    def __call__(self) -> int:
        endpoint: AddressPortGroup = self.__parent__.endpoint
        print(
            "Push command called", self,
            "endpoint", endpoint.address, "port", endpoint.port
        )
        return 0

class Parser(argclass.Parser):
    log_level: int = argclass.LogLevel
    endpoint = AddressPortGroup(title="Endpoint options")
    commit: Optional[CommitCommand] = CommitCommand()
    push: Optional[PushCommand] = PushCommand()

if __name__ == '__main__':
    parser = Parser(
        config_files=["example.ini", "~/.example.ini", "/etc/example.ini"],
        auto_env_var_prefix="EXAMPLE_"
    )
    parser.parse_args()
    exit(parser())
```

### Using `singledispatch`

You can use the `current_subparser` attribute to get the current subparser and then call it. This does not require implementing the `__call__` method.

```python
from functools import singledispatch
from typing import Optional, Any
import argclass

class AddressPortGroup(argclass.Group):
    address: str = argclass.Argument(default="127.0.0.1")
    port: int

class CommitCommand(argclass.Parser):
    comment: str = argclass.Argument()

class PushCommand(argclass.Parser):
    comment: str = argclass.Argument()

class Parser(argclass.Parser):
    log_level: int = argclass.LogLevel
    endpoint = AddressPortGroup(
        title="Endpoint options",
        defaults=dict(port=8080)
    )
    commit: Optional[CommitCommand] = CommitCommand()
    push: Optional[PushCommand] = PushCommand()

@singledispatch
def handle_subparser(subparser: Any) -> None:
    raise NotImplementedError(
        f"Unexpected subparser type {subparser.__class__!r}"
    )

@handle_subparser.register(type(None))
def handle_none(_: None) -> None:
    Parser().print_help()
    exit(2)

@handle_subparser.register(CommitCommand)
def handle_commit(subparser: CommitCommand) -> None:
    print("Commit command called", subparser)

@handle_subparser.register(PushCommand)
def handle_push(subparser: PushCommand) -> None:
    print("Push command called", subparser)

if __name__ == '__main__':
    parser = Parser(
        config_files=["example.ini", "~/.example.ini", "/etc/example.ini"],
        auto_env_var_prefix="EXAMPLE_"
    )
    parser.parse_args()
    handle_subparser(parser.current_subparser)
```

## Value Conversion with Optional and Union Types

If an argument has a generic or composite type, you must explicitly describe it using `argclass.Argument`, specifying 
the converter function with `type` or `converter` to transform the value after parsing. The exception to this rule 
is `Optional` with a single type. In this case, an argument without a default value will not be required, and 
its value can be `None`.

<!--- name: test_optional_union_example --->
```python
import argclass
from typing import Optional, Union

def converter(value: str) -> Optional[Union[int, str, bool]]:
    if value.lower() == "none":
        return None
    if value.isdigit():
        return int(value)
    if value.lower() in ("yes", "true", "enabled", "enable", "on"):
        return True
    return False

class Parser(argclass.Parser):
    gizmo: Optional[Union[int, str, bool]] = argclass.Argument(
        converter=converter
    )
    optional: Optional[int]

parser = Parser()

parser.parse_args(["--gizmo=65535"])
assert parser.gizmo == 65535

parser.parse_args(["--gizmo=None"])
assert parser.gizmo is None

parser.parse_args(["--gizmo=on"])
assert parser.gizmo is True
assert parser.optional is None

parser.parse_args(["--gizmo=off", "--optional=10"])
assert parser.gizmo is False
assert parser.optional == 10
```

# 3rd Party Libraries integration

`argclass` is able to integrate with some 3rd party libraries to provide additional features.

## `Rich` and `rich_argparse` integration examples

`rich_argparse` is a library that provides an ability to use `rich` for formatting help messages in `argparse`.
So this library can be used with `argclass` to provide a rich help output.

```python
from argparse import Action

import argclass
from rich.console import ConsoleRenderable, Group
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text
from rich_argparse import RawTextRichHelpFormatter


class HelpFormatter(RawTextRichHelpFormatter):
    def _rich_expand_help(self, action: Action) -> Text:
        try:
            if "%" in str(action.default):
                action.default = ""
            if "%" in str(action.help):
                action.help = ""
            return super()._rich_expand_help(action)
        except ValueError:
            return Text("FAILED")


class RichParser(argclass.Parser):
    def __init__(self, *args, **kwargs) -> None:
        help = kwargs.pop("help", None)
        description = kwargs.pop("description", help) or ""

        if isinstance(description, ConsoleRenderable):
            kwargs["description"] = description
        else:
            kwargs["description"] = Markdown(description)

        if help is not None:
            kwargs["help"] = help

        kwargs["formatter_class"] = HelpFormatter
        super().__init__(*args, **kwargs)


class Parser(RichParser):
    log_level = argclass.LogLevel


if __name__ == "__main__":
    parser = Parser(
        formatter_class=RawTextRichHelpFormatter,
        description=Group(
            Text("This code produces this help:\n\n"),
            Panel(Syntax(open(__file__).read().strip(), "python")),
        ),
    )
    parser.parse_args()
    parser.sanitize_env()
    exit(parser())
```

![Help Output](https://raw.githubusercontent.com/mosquito/argclass/master/.github/rich_example.png)
