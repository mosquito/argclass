# Config File Syntax

Exact on-disk syntax for the config files argclass reads — how groups map to
sections, which boolean literals are accepted, and how CLI arguments override
file values. For *how to load* config files see
[Configuration Files](config-files.md); for the priority model see
[The configuration model](explanation/configuration-model.md).

## Group Sections

Groups map to INI sections:

<!--- name: test_config_groups --->
```python
import argclass
from pathlib import Path
from tempfile import NamedTemporaryFile

class ServerGroup(argclass.Group):
    host: str = "localhost"
    port: int = 8080

class DatabaseGroup(argclass.Group):
    host: str = "localhost"
    port: int = 5432

class Parser(argclass.Parser):
    verbose: bool = False
    server = ServerGroup()
    database = DatabaseGroup()

# Config file content
CONFIG_CONTENT = """
[DEFAULT]
verbose = true

[server]
host = 0.0.0.0
port = 9000

[database]
host = db.example.com
port = 3306
"""

with NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
    f.write(CONFIG_CONTENT)
    config_path = f.name

parser = Parser(config_files=[config_path])
parser.parse_args([])

assert parser.verbose is True
assert parser.server.host == "0.0.0.0"
assert parser.server.port == 9000
assert parser.database.host == "db.example.com"
assert parser.database.port == 3306

Path(config_path).unlink()
```

## Nested Groups in Config Files

A group inside a group becomes a dotted INI section, a nested JSON/TOML
table, or a child object — depending on the format.

INI uses the dotted section name verbatim:

<!--- name: test_config_nested_ini --->
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

JSON uses natural nesting — each group level is a nested object:

```json
{
  "endpoint": {
    "host": "api.example.com",
    "credentials": {
      "username": "root",
      "password": "hunter2"
    }
  }
}
```

TOML uses dotted table headers, just like INI:

```toml
[endpoint]
host = "api.example.com"

[endpoint.credentials]
username = "root"
password = "hunter2"
```

:::{note}
The section name in config files always follows the attribute path,
even when a group has `prefix=` set. `prefix=` only renames the CLI/env
segment for that group.
:::

## Boolean Values

| True values | False values |
|-------------|--------------|
| `true`, `yes`, `on`, `1`, `enable`, `enabled`, `t`, `y` | Any other value |

:::{note}
For INI files, boolean conversion is case-insensitive (`TRUE`, `True`, `true` all work).
JSON and TOML use native boolean types (`true`/`false`).
:::

<!--- name: test_config_bool --->
```python
import argclass
from pathlib import Path
from tempfile import NamedTemporaryFile

class Parser(argclass.Parser):
    flag1: bool = False
    flag2: bool = False
    flag3: bool = True
    flag4: bool = True

# Config file content
CONFIG_CONTENT = """
[DEFAULT]
flag1 = yes
flag2 = 1
flag3 = no
flag4 = off
"""

with NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
    f.write(CONFIG_CONTENT)
    config_path = f.name

parser = Parser(config_files=[config_path])
parser.parse_args([])

assert parser.flag1 is True
assert parser.flag2 is True
assert parser.flag3 is False
assert parser.flag4 is False

Path(config_path).unlink()
```

## CLI Override

Command-line arguments always override config file values:

<!--- name: test_config_cli_override --->
```python
import argclass
from pathlib import Path
from tempfile import NamedTemporaryFile

class Parser(argclass.Parser):
    host: str = "localhost"
    port: int = 8080

# Config file content
CONFIG_CONTENT = """
[DEFAULT]
host = config.example.com
port = 9000
"""

with NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
    f.write(CONFIG_CONTENT)
    config_path = f.name

parser = Parser(config_files=[config_path])
parser.parse_args(["--port", "3000"])

assert parser.host == "config.example.com"  # From config
assert parser.port == 3000  # From CLI (override)

Path(config_path).unlink()
```

