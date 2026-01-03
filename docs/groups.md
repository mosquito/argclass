# Argument Groups

Groups organize related arguments together and enable reuse across parsers.

## Basic Groups

Define a group by inheriting from `argclass.Group`:

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

Add a title for help output:

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

Override the default prefix:

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

The same group class can be used multiple times:

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

Override defaults when instantiating:

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

Parsers can inherit from groups to include arguments directly:

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

Access group attributes through the group instance:

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

Groups map to INI sections:

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

# Create config file
with NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
    f.write("[DEFAULT]\n")
    f.write("verbose = true\n\n")
    f.write("[database]\n")
    f.write("host = db.example.com\n")
    f.write("port = 5432\n\n")
    f.write("[cache]\n")
    f.write("host = redis.example.com\n")
    f.write("port = 6379\n")
    config_path = f.name

parser = Parser(config_files=[config_path])
parser.parse_args([])

assert parser.verbose is True
assert parser.database.host == "db.example.com"
assert parser.database.port == 5432
assert parser.cache.host == "redis.example.com"
assert parser.cache.port == 6379

# Cleanup
Path(config_path).unlink()
```
