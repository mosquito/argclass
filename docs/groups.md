# Argument Groups

Groups organize related arguments together and enable reuse across parsers.
They provide logical structure to your CLI, make `--help` output more readable,
and allow you to define common argument sets once and reuse them in multiple parsers.

## Basic Groups

Create a group by inheriting from `argclass.Group`. When you add a group to a
parser, its arguments are prefixed with the attribute name. Here, `database`
becomes the prefix, so arguments become `--database-host`, `--database-port`, etc.

<!--- name: test_groups_basic --->
```python
import argclass

class DatabaseGroup(argclass.Group):
    host: str = "localhost"
    port: int = 5432
    user: str = "admin"

class Parser(argclass.Parser):
    verbose: bool = False
    database = DatabaseGroup()

parser = Parser()
parser.parse_args(["--database-host", "db.example.com", "--database-port", "3306"])

assert parser.verbose is False
assert parser.database.host == "db.example.com"
assert parser.database.port == 3306
assert parser.database.user == "admin"
```

## Group Titles

Add a descriptive title that appears in `--help` output. This makes the help
more readable by clearly labeling each section of related arguments.

<!--- name: test_groups_title --->
```python
import argclass

class DatabaseGroup(argclass.Group):
    host: str = "localhost"
    port: int = 5432

class Parser(argclass.Parser):
    database = DatabaseGroup(title="Database connection")

parser = Parser()
parser.parse_args(["--database-host", "db.example.com"])

assert parser.database.host == "db.example.com"
assert parser.database.port == 5432
```

## Custom Prefixes

Override the default prefix with `prefix=`. Use an empty string to add
arguments without any prefix. This is useful when you want short argument
names or when the group represents the main configuration.

<!--- name: test_groups_custom_prefix --->
```python
import argclass

class ConnectionGroup(argclass.Group):
    host: str = "localhost"
    port: int = 8080

class Parser(argclass.Parser):
    # Custom prefix: --api-host, --api-port
    api = ConnectionGroup(prefix="api")
    # No prefix: --host, --port
    server = ConnectionGroup(prefix="")

parser = Parser()
parser.parse_args([
    "--api-host", "api.example.com",
    "--api-port", "9000",
    "--host", "server.example.com",
    "--port", "3000"
])

assert parser.api.host == "api.example.com"
assert parser.api.port == 9000
assert parser.server.host == "server.example.com"
assert parser.server.port == 3000
```

## Reusing Groups

The same group class can be instantiated multiple times with different
settings. Use `defaults=` to override default values for each instance.
This avoids duplicating group definitions for similar configurations.

<!--- name: test_groups_reuse --->
```python
import argclass

class HostPort(argclass.Group):
    host: str = "localhost"
    port: int

class Parser(argclass.Parser):
    api = HostPort(title="API Server", defaults={"port": 8080})
    metrics = HostPort(title="Metrics Server", defaults={"port": 9090})
    database = HostPort(title="Database", defaults={"port": 5432})

parser = Parser()
parser.parse_args([
    "--api-host", "0.0.0.0",
    "--metrics-port", "9999"
])

assert parser.api.host == "0.0.0.0"
assert parser.api.port == 8080
assert parser.metrics.host == "localhost"
assert parser.metrics.port == 9999
assert parser.database.port == 5432
```

## Group Defaults

Use `defaults=` to provide instance-specific default values. This is useful
for deployment presets like production vs development configurations, where
the same group structure needs different default values.

<!--- name: test_groups_defaults --->
```python
import argclass

class ServerGroup(argclass.Group):
    host: str = "localhost"
    port: int = 8080
    ssl: bool = False

class Parser(argclass.Parser):
    prod = ServerGroup(defaults={
        "host": "0.0.0.0",
        "port": 443,
        "ssl": True,
    })

parser = Parser()
parser.parse_args([])

assert parser.prod.host == "0.0.0.0"
assert parser.prod.port == 443
assert parser.prod.ssl is True
```

## Inheriting from Groups

Parsers can inherit from groups as mixins to include arguments directly
at the top level (without a prefix). This is useful for common arguments
like logging or verbosity that you want available in multiple parsers.

<!--- name: test_groups_inherit --->
```python
import argclass

class LoggingMixin(argclass.Group):
    log_level: str = "info"
    log_file: str | None = None

class VerboseMixin(argclass.Group):
    verbose: bool = False
    quiet: bool = False

class Parser(argclass.Parser, LoggingMixin, VerboseMixin):
    name: str

parser = Parser()
parser.parse_args(["--name", "test", "--log-level", "debug", "--verbose"])

assert parser.name == "test"
assert parser.log_level == "debug"
assert parser.verbose is True
assert parser.quiet is False
```

## Accessing Group Values

After parsing, access group values through the group attribute. Groups behave
like regular Python objects - use dot notation to read the parsed values.

<!--- name: test_groups_access --->
```python
import argclass

class DatabaseGroup(argclass.Group):
    host: str = "localhost"
    port: int = 5432

class Parser(argclass.Parser):
    database = DatabaseGroup()

parser = Parser()
parser.parse_args(["--database-host", "db.example.com"])

# Access via group
assert parser.database.host == "db.example.com"
assert parser.database.port == 5432
```

## Groups in Config Files

Groups map to INI sections. The section name matches the group attribute name.
Top-level parser arguments go in `[DEFAULT]`, while each group gets its own
section named after the attribute.

<!--- name: test_groups_config --->
```python
import argclass
from pathlib import Path
from tempfile import NamedTemporaryFile

class ConnectionGroup(argclass.Group):
    host: str = "localhost"
    port: int = 8080

class Parser(argclass.Parser):
    verbose: bool = False
    database = ConnectionGroup()
    cache = ConnectionGroup()

CONFIG = """
[DEFAULT]
verbose = true

[database]
host = db.example.com
port = 5432

[cache]
host = redis.example.com
port = 6379
"""

with NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
    f.write(CONFIG)
    config_path = f.name

parser = Parser(config_files=[config_path])
parser.parse_args([])

assert parser.verbose is True
assert parser.database.host == "db.example.com"
assert parser.database.port == 5432
assert parser.cache.host == "redis.example.com"
assert parser.cache.port == 6379

Path(config_path).unlink()
```
