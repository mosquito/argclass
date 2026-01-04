# Configuration Files

argclass provides two distinct approaches for working with configuration files,
each designed for different use cases:

## Two Approaches Overview

| Approach | Mechanism | Format | Purpose |
|----------|-----------|--------|---------|
| **Preconfigured Defaults** | `config_files=[...]` in Parser | INI | Preset CLI argument defaults |
| **Config Argument** | `ConfigArgument` / `argclass.Config()` | YAML, TOML, JSON, INI | Load complex structures via `--config` |

### Approach 1: Preconfigured CLI Defaults

Use the `config_files=[...]` parameter in the Parser constructor to preset default
values for CLI arguments from INI files. These defaults are loaded at initialization
and can be overridden by environment variables and command-line arguments.

**Best for:** Site-specific defaults (e.g., `/etc/myapp.ini`), deployment configurations.

### Approach 2: Config File as Argument Value

Use `ConfigArgument` subclasses (`JSONConfig`, `INIConfig`, or custom YAML/TOML parsers)
to add a `--config` argument. The user provides a config file path at runtime, and the
parsed content becomes available as a `MappingProxyType` for your application to use.

**Best for:** Loading complex nested structures, application-specific data, user-provided configs.

---

## Approach 1: Preconfigured CLI Defaults

This approach loads default values for CLI arguments from INI configuration files.

### INI Files

The default format is INI:

<!--- name: test_config_ini --->
```python
import argclass
from pathlib import Path
from tempfile import NamedTemporaryFile

class Parser(argclass.Parser):
    host: str = "localhost"
    port: int = 8080
    debug: bool = False

# Config file content
CONFIG_CONTENT = """
[DEFAULT]
host = example.com
port = 9000
debug = true
"""

with NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
    f.write(CONFIG_CONTENT)
    config_path = f.name

parser = Parser(config_files=[config_path])
parser.parse_args([])

assert parser.host == "example.com"
assert parser.port == 9000
assert parser.debug is True

Path(config_path).unlink()
```

### Config File Search

Specify multiple paths - first found is used:

<!--- name: test_config_search --->
```python
import argclass
from pathlib import Path
from tempfile import NamedTemporaryFile

class Parser(argclass.Parser):
    value: str = "default"

# Config file content
CONFIG_CONTENT = """
[DEFAULT]
value = from_config
"""

with NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
    f.write(CONFIG_CONTENT)
    config_path = f.name

# First existing file is used
parser = Parser(config_files=[
    "/nonexistent/config.ini",
    config_path,
])
parser.parse_args([])

assert parser.value == "from_config"

Path(config_path).unlink()
```

### Dynamic Config Paths

For flexible deployments, use `os.getenv()` to allow users to override config file
locations via environment variables:

```python
import os
import argclass

class Parser(argclass.Parser):
    host: str = "localhost"
    port: int = 8080

parser = Parser(config_files=[
    # Environment variable takes priority if set
    os.getenv("MYAPP_CONFIG", "/etc/myapp/config.ini"),
    # Fallback locations
    "/etc/myapp.ini",
    "~/.config/myapp.ini",
    "./config.ini",
])
```

This pattern allows:
- Operators to override config location: `MYAPP_CONFIG=/custom/path.ini myapp`
- Default system-wide config: `/etc/myapp/config.ini`
- User-specific config: `~/.config/myapp.ini`
- Local development config: `./config.ini`

### Partial Configuration (Multi-File Merging)

When multiple config files are specified, they are **merged together** with later files
overriding earlier ones. This enables a layered configuration approach where each file
only needs to specify the values it wants to override.

**Example: Global defaults with user overrides**

```
# /etc/myapp.ini (global defaults)
[DEFAULT]
log_level = warning
max_connections = 100

[database]
host = db.production.example.com
port = 5432

[server]
host = 0.0.0.0
port = 8080
```

```
# ~/.config/myapp.ini (user overrides - only specify what differs)
[DEFAULT]
log_level = debug

[server]
host = 127.0.0.1
```

```python
import os
import argclass

class DatabaseGroup(argclass.Group):
    host: str = "localhost"
    port: int = 5432

class ServerGroup(argclass.Group):
    host: str = "localhost"
    port: int = 80

class Parser(argclass.Parser):
    log_level: str = "info"
    max_connections: int = 10
    database = DatabaseGroup()
    server = ServerGroup()

parser = Parser(config_files=[
    "/etc/myapp.ini",                # Global defaults
    os.path.expanduser("~/.config/myapp.ini"),  # User overrides
])
parser.parse_args([])

# Results after merging:
# - log_level = "debug"           (user overrides global)
# - max_connections = 100         (from global, not in user config)
# - database.host = "db.production.example.com"  (from global)
# - database.port = 5432          (from global)
# - server.host = "127.0.0.1"     (user overrides global)
# - server.port = 8080            (from global, not in user config)
```

**Key benefits:**
- **Separation of concerns:** Global config in `/etc/` for system-wide defaults,
  user config in `~/.config/` for personal preferences
- **Partial configs:** Each file only needs to define what it wants to change
- **Group isolation:** Configure different groups in different files (e.g., database
  settings managed by DBAs, server settings by developers)

### Config Priority

Values are applied in this order (later overrides earlier):

1. Class defaults
2. Config file values
3. Environment variables
4. Command-line arguments

<!--- name: test_config_priority --->
```python
import argclass
from pathlib import Path
from tempfile import NamedTemporaryFile

class Parser(argclass.Parser):
    port: int = 8080  # Class default

# Config file content
CONFIG_CONTENT = """
[DEFAULT]
port = 9000
"""

with NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
    f.write(CONFIG_CONTENT)
    config_path = f.name

# Config overrides class default
parser1 = Parser(config_files=[config_path])
parser1.parse_args([])
assert parser1.port == 9000

# CLI overrides config
parser2 = Parser(config_files=[config_path])
parser2.parse_args(["--port", "3000"])
assert parser2.port == 3000

Path(config_path).unlink()
```

### Group Sections

Groups map to config sections:

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

### Boolean Values

These strings are recognized as boolean:

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

### CLI Override

Command-line arguments override config file values:

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

---

## Approach 2: Config File as Argument Value

This approach adds a `--config` argument that accepts a file path. The config file
is parsed and its content becomes available as a `MappingProxyType` (immutable dict)
for programmatic use within your application.

Unlike Approach 1 (which sets CLI argument defaults), this approach is for loading
complex structured data that your application logic needs to process.

### Built-in Config Types

argclass provides built-in support for JSON and INI formats:

```python
import argclass

class Parser(argclass.Parser):
    # JSON config file argument
    config: argclass.JSONConfig
```

### Custom Config Parsers

For other formats like YAML or TOML, create custom parsers by extending `ConfigAction`.

#### YAML Parser

```python
from pathlib import Path
from typing import Mapping, Any
import argclass
import yaml

class YAMLConfigAction(argclass.ConfigAction):
    def parse_file(self, file: Path) -> Mapping[str, Any]:
        with file.open("r") as fp:
            return yaml.safe_load(fp)

class YAMLConfig(argclass.ConfigArgument):
    action = YAMLConfigAction

class Parser(argclass.Parser):
    config = argclass.Config(config_class=YAMLConfig)
```

#### TOML Parser

```python
from pathlib import Path
from typing import Mapping, Any
import argclass
import tomllib  # Python 3.11+ or use tomli

class TOMLConfigAction(argclass.ConfigAction):
    def parse_file(self, file: Path) -> Mapping[str, Any]:
        with file.open("rb") as fp:
            return tomllib.load(fp)

class TOMLConfig(argclass.ConfigArgument):
    action = TOMLConfigAction

class Parser(argclass.Parser):
    config = argclass.Config(config_class=TOMLConfig)
```

### Complete Usage Example

Here's how Approach 2 differs from Approach 1 - the config data is accessed
programmatically rather than being mapped to CLI arguments:

```python
import argclass
import json
from pathlib import Path
from tempfile import NamedTemporaryFile

class Parser(argclass.Parser):
    verbose: bool = False
    config: argclass.JSONConfig  # Adds --config argument

# Create a JSON config with complex nested data
config_data = {
    "database": {
        "connections": [
            {"host": "primary.db", "port": 5432},
            {"host": "replica.db", "port": 5432}
        ]
    },
    "features": ["auth", "logging", "metrics"]
}

with NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
    json.dump(config_data, f)
    config_path = f.name

parser = Parser()
parser.parse_args(["--config", config_path, "--verbose"])

# CLI arguments work as normal
assert parser.verbose is True

# Config data is available as MappingProxyType (immutable dict)
assert parser.config["database"]["connections"][0]["host"] == "primary.db"
assert parser.config["features"] == ["auth", "logging", "metrics"]

Path(config_path).unlink()
```

**Key difference:** In Approach 1, config values map directly to CLI argument defaults.
In Approach 2, the entire config structure is available for your application logic
to process however needed.
