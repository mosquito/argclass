# Argument Groups

Groups organize related arguments together and enable reuse across parsers.
They provide logical structure to your CLI, make `--help` output more readable,
and allow you to define common argument sets once and reuse them in multiple parsers.

## The Mental Model: a Group Instance Is a Declaration, not a Parser

A `Group()` you assign on a parser class — `db = DatabaseGroup()` or
`db: DatabaseGroup = DatabaseGroup(defaults={...})` — is a **declaration
of structure and per-instance defaults**, not a runtime parser. You
don't call methods on it; you don't use it to read CLI arguments. Its
job at class-definition time is to:

- name a slot in the parsed result (`parser.db`),
- describe which arguments belong to that slot (via its annotations),
- optionally override defaults for this particular slot (`defaults=`,
  `title=`, `prefix=`).

When you call `Parser().parse_args(...)`, argclass walks these
declarations, builds an `argparse` parser from them, parses the
command line, and then writes the parsed values back into the same
group instance so you can read them as `parser.db.host`. The instance
is a write target during parsing, not an active participant in it.

Two consequences worth internalising:

1. **Don't call parser methods on a `Group` instance.** It has no
   `parse_args()`. Groups are not standalone parsers.
2. **Don't share one `Group` instance across two attributes.** Since
   the instance holds the parsed state for *its* slot, assigning the
   same instance to `primary = shared` and `secondary = shared` would
   make them aliases of one another — argclass raises
   `ArgclassError` at parse time to prevent this. Construct one
   `Group()` per slot. (Using the same Group *class* twice is fine —
   only sharing a single constructed instance is not.)

:::{note}
**Groups vs. subparsers.** This "instance-is-a-declaration" rule is
specific to `Group`. **Subparsers are different**: a subparser is a
`Parser` subclass instance assigned to an attribute (e.g.
`serve = Serve()`), and at runtime the selected subparser really does
parse its own slice of `sys.argv` — it has a working `parse_args()`,
its own `__call__`, its own subparsers. Subparsers are real parsers
chosen by name from the CLI; groups are namespaced collections of
arguments declared upfront. If you want a runnable sub-command, use a
subparser. If you want to bundle related options under a prefix, use a
group. See [Subparsers](subparsers.md) for the runtime contract.
:::

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

## Nested Groups

Groups can contain other Groups as fields. This works for any depth and
keeps `Parser → Group → Group → ...` cleanly modelled in code. Names are
built by joining the attribute path with the appropriate separator for
each source:

| Source | Separator | Example                                       |
|--------|-----------|-----------------------------------------------|
| CLI    | `-`       | `--endpoint-credentials-username`             |
| ENV    | `_`       | `<PREFIX>ENDPOINT_CREDENTIALS_USERNAME`       |
| INI    | `.`       | `[endpoint.credentials]` section, `username`  |
| JSON   | nested    | `{"endpoint": {"credentials": {"username":…}}}` |
| TOML   | `.`       | `[endpoint.credentials]` table, `username`    |

<!--- name: test_groups_nested_cli --->
```python
import argclass

class Credentials(argclass.Group):
    username: str = "admin"
    password: str = "secret"

class Endpoint(argclass.Group):
    host: str = "localhost"
    port: int = 8080
    credentials: Credentials = Credentials()

class Parser(argclass.Parser):
    endpoint: Endpoint = Endpoint()

parser = Parser()
parser.parse_args([
    "--endpoint-host", "api.example.com",
    "--endpoint-credentials-username", "root",
    "--endpoint-credentials-password", "hunter2",
])

assert parser.endpoint.host == "api.example.com"
assert parser.endpoint.credentials.username == "root"
assert parser.endpoint.credentials.password == "hunter2"
```

Nested groups appear as separate sections in `--help`, titled with their
dotted attribute path (e.g. `endpoint.credentials`). Set `title=` on a
group to override the default title for that one level.

### Nested groups in config files

INI sections use a dotted section name; JSON/TOML use natural nesting.

<!--- name: test_groups_nested_ini --->
```python
import argclass
from pathlib import Path
from tempfile import NamedTemporaryFile

class Credentials(argclass.Group):
    username: str = "admin"
    password: str = "secret"

class Endpoint(argclass.Group):
    host: str = "localhost"
    credentials: Credentials = Credentials()

class Parser(argclass.Parser):
    endpoint: Endpoint = Endpoint()

CONFIG = """
[endpoint]
host = api.example.com

[endpoint.credentials]
username = root
password = hunter2
"""

with NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
    f.write(CONFIG)
    config_path = f.name

parser = Parser(config_files=[config_path])
parser.parse_args([])

assert parser.endpoint.host == "api.example.com"
assert parser.endpoint.credentials.username == "root"
assert parser.endpoint.credentials.password == "hunter2"

Path(config_path).unlink()
```

### `prefix=` and nested groups

`Group(prefix=...)` overrides only the CLI/ENV segment for that group. It
does **not** affect the INI/TOML section name — config sections always
follow the attribute path. This keeps section names predictable and
prevents CLI prefixes from silently desyncing from config layout.

### Group fields with type annotations

A group attribute can be declared with a type annotation. When the
annotation refers to a `Group` subclass, argclass enforces these rules
at class definition time:

| Form                                | Behaviour                       |
|-------------------------------------|---------------------------------|
| `g: G`                              | Auto-instantiated as `G()`      |
| `g: G = G()`                        | Uses the provided instance      |
| `g: G = ...` (Ellipsis sentinel)    | Auto-instantiated as `G()`      |
| `g = G()` (no annotation)           | Uses the provided instance      |
| `g: G \| None = None`               | **Rejected** (Group can't be None) |
| `g: G = None`                       | **Rejected** (Group can't be None) |
| `g: G = G2()` (wrong Group class)   | **Rejected**                    |
| `g: G = "anything-not-a-G"`         | **Rejected**                    |

<!--- name: test_groups_annotation_auto_instantiate --->
```python
import argclass

class DatabaseGroup(argclass.Group):
    host: str = "localhost"
    port: int = 5432

class Parser(argclass.Parser):
    # No explicit default — argclass instantiates DatabaseGroup() for you
    database: DatabaseGroup

parser = Parser()
parser.parse_args(["--database-host", "db.example.com"])

assert parser.database.host == "db.example.com"
assert parser.database.port == 5432
```

Rejected forms raise `ArgumentDefinitionError` immediately when the
parser class is defined, with a hint suggesting the correct form.

### Reusing a group instance

Group instances in a class body are prototypes — every parser
instance works on its own copies, so the same `Group` instance may be
bound to several attributes and each binding keeps independent parsed
state. Separate instances per attribute remain the clearest style
(and are required when the attributes need different `title`/`prefix`
options):

<!--- name: test_groups_nested_separate_instances --->
```python
import argclass

class Credentials(argclass.Group):
    username: str = "admin"

class Auth(argclass.Group):
    primary: Credentials = Credentials()      # separate instance
    secondary: Credentials = Credentials()    # separate instance

class Parser(argclass.Parser):
    auth: Auth = Auth()

parser = Parser()
parser.parse_args([
    "--auth-primary-username", "alice",
    "--auth-secondary-username", "bob",
])

assert parser.auth.primary.username == "alice"
assert parser.auth.secondary.username == "bob"
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
