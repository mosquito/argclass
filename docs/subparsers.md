# Subparsers

Subparsers enable multi-command CLIs like `git commit`, `docker run`, etc.

## Basic Subcommands

Define subcommands as nested Parser classes:

<!--- name: test_subparsers_basic --->
```python
import argclass

class AddCommand(argclass.Parser):
    """Add a new item."""
    name: str
    value: int = 0

class RemoveCommand(argclass.Parser):
    """Remove an item."""
    name: str
    force: bool = False

class CLI(argclass.Parser):
    """Item management tool."""
    verbose: bool = False
    add = AddCommand()
    remove = RemoveCommand()

cli = CLI()
cli.parse_args(["add", "--name", "foo", "--value", "42"])

assert cli.verbose is False
assert cli.add.name == "foo"
assert cli.add.value == 42
```

## Executing Commands

Implement `__call__` to define command behavior:

<!--- name: test_subparsers_call --->
```python
import argclass

class StartCommand(argclass.Parser):
    """Start the server."""
    port: int = 8080

    def __call__(self) -> int:
        return self.port

class StopCommand(argclass.Parser):
    """Stop the server."""

    def __call__(self) -> int:
        return 0

class Server(argclass.Parser):
    start = StartCommand()
    stop = StopCommand()

server = Server()
server.parse_args(["start", "--port", "9000"])

result = server()
assert result == 9000
```

## Accessing Parent Parser

Use `__parent__` to access the parent parser:

<!--- name: test_subparsers_parent --->
```python
import argclass

class DeployCommand(argclass.Parser):
    environment: str = "staging"

    def __call__(self) -> bool:
        return self.__parent__.verbose

class CLI(argclass.Parser):
    verbose: bool = False
    deploy = DeployCommand()

cli = CLI()
cli.parse_args(["--verbose", "deploy", "--environment", "production"])

assert cli.verbose is True
assert cli.deploy.environment == "production"
assert cli.deploy() is True  # Returns parent's verbose
```

## Nested Subcommands

Subcommands can have their own subcommands:

<!--- name: test_subparsers_nested --->
```python
import argclass

class ListImages(argclass.Parser):
    """List container images."""
    all: bool = False

    def __call__(self) -> str:
        return "list"

class PullImage(argclass.Parser):
    """Pull an image."""
    name: str

    def __call__(self) -> str:
        return f"pull:{self.name}"

class ImageCommand(argclass.Parser):
    """Manage images."""
    list = ListImages()
    pull = PullImage()

class Docker(argclass.Parser):
    """Docker-like CLI."""
    image = ImageCommand()

cli = Docker()
cli.parse_args(["image", "pull", "--name", "ubuntu:latest"])

assert cli.image.pull.name == "ubuntu:latest"
assert cli() == "pull:ubuntu:latest"
```

## Current Subparser

Access the selected subparser chain:

<!--- name: test_subparsers_current --->
```python
import argclass

class Sub1(argclass.Parser):
    value: int = 1
    def __call__(self) -> int:
        return self.value

class Sub2(argclass.Parser):
    value: int = 2
    def __call__(self) -> int:
        return self.value

class CLI(argclass.Parser):
    sub1 = Sub1()
    sub2 = Sub2()

cli = CLI()
cli.parse_args(["sub1", "--value", "10"])

assert len(cli.current_subparsers) == 1
assert cli.current_subparsers[0].value == 10
assert cli() == 10
```

## Shared Arguments with Groups

Use groups for arguments shared across subcommands:

<!--- name: test_subparsers_shared --->
```python
import argclass

class OutputOptions(argclass.Group):
    format: str = argclass.Argument(
        choices=["json", "yaml", "table"],
        default="table"
    )
    output: str | None = None

class ListCommand(argclass.Parser):
    output = OutputOptions()

    def __call__(self) -> str:
        return self.output.format

class GetCommand(argclass.Parser):
    name: str
    output = OutputOptions()

    def __call__(self) -> str:
        return f"{self.name}:{self.output.format}"

class CLI(argclass.Parser):
    list = ListCommand()
    get = GetCommand()

cli = CLI()
cli.parse_args(["get", "--name", "item1", "--output-format", "json"])

assert cli.get.name == "item1"
assert cli.get.output.format == "json"
assert cli() == "item1:json"
```

## Multiple Subcommands Selection

Only one subcommand is active at a time:

<!--- name: test_subparsers_selection --->
```python
import argclass

class CreateCommand(argclass.Parser):
    name: str
    def __call__(self) -> str:
        return f"create:{self.name}"

class DeleteCommand(argclass.Parser):
    name: str
    force: bool = False
    def __call__(self) -> str:
        return f"delete:{self.name}"

class CLI(argclass.Parser):
    verbose: bool = False
    create = CreateCommand()
    delete = DeleteCommand()

# Test create command
cli = CLI()
cli.parse_args(["--verbose", "create", "--name", "myitem"])
assert cli.verbose is True
assert cli() == "create:myitem"

# Test delete command
cli2 = CLI()
cli2.parse_args(["delete", "--name", "myitem", "--force"])
assert cli2.delete.force is True
assert cli2() == "delete:myitem"
```
