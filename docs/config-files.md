# Configuration Files

Load default values for CLI arguments from configuration files. Useful for
site-specific defaults, deployment configurations, and separating configuration
from code.

---

## Quick Start

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

---

## Supported Formats

::::{grid} 3
:gutter: 3

:::{grid-item-card} INI (Default)
:class-card: sd-rounded-3

```ini
[DEFAULT]
host = localhost
port = 8080
```

Use `INIDefaultsParser` (default)
:::

:::{grid-item-card} JSON
:class-card: sd-rounded-3

```json
{
  "host": "localhost",
  "port": 8080
}
```

Use `JSONDefaultsParser`
:::

:::{grid-item-card} TOML
:class-card: sd-rounded-3

```toml
host = "localhost"
port = 8080
```

Use `TOMLDefaultsParser`
:::

::::

### Format Comparison

| Format | Complex Types | Native Types | Parser Class |
|--------|--------------|--------------|--------------|
| **INI** | `ast.literal_eval` syntax | All strings | `INIDefaultsParser` |
| **JSON** | Native arrays/objects | int, float, bool, null | `JSONDefaultsParser` |
| **TOML** | Native arrays/tables | int, float, bool, datetime | `TOMLDefaultsParser` |

### INI Complex Types

All INI values are strings. For lists, use Python literal syntax:

```ini
[DEFAULT]
ports = [8080, 8081, 8082]
hosts = ["primary.example.com", "backup.example.com"]
```

These are parsed using `ast.literal_eval` when the argument type requires it.

### Using JSON

<!--- name: test_config_json_defaults --->
```python
import argclass
import json
from pathlib import Path
from tempfile import NamedTemporaryFile

class Parser(argclass.Parser):
    host: str = "localhost"
    port: int = 8080
    debug: bool = False

CONFIG_DATA = {
    "host": "json.example.com",
    "port": 9000,
    "debug": True
}

with NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
    json.dump(CONFIG_DATA, f)
    config_path = f.name

parser = Parser(
    config_files=[config_path],
    config_parser_class=argclass.JSONDefaultsParser,
)
parser.parse_args([])

assert parser.host == "json.example.com"
assert parser.port == 9000
assert parser.debug is True

Path(config_path).unlink()
```

### Using TOML

Requires Python 3.11+ (stdlib `tomllib`) or `tomli` package.

<!--- name: test_config_toml_defaults --->
```python
import argclass
from pathlib import Path
from tempfile import NamedTemporaryFile

class Parser(argclass.Parser):
    host: str = "localhost"
    port: int = 8080
    debug: bool = False

CONFIG_CONTENT = '''
host = "toml.example.com"
port = 9000
debug = true
'''

with NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
    f.write(CONFIG_CONTENT)
    config_path = f.name

parser = Parser(
    config_files=[config_path],
    config_parser_class=argclass.TOMLDefaultsParser,
)
parser.parse_args([])

assert parser.host == "toml.example.com"
assert parser.port == 9000
assert parser.debug is True

Path(config_path).unlink()
```

### Custom Format

Subclass `AbstractDefaultsParser` for other formats (e.g., YAML):

```python
import argclass

class YAMLDefaultsParser(argclass.AbstractDefaultsParser):
    def parse(self):
        import yaml
        result = {}
        for path in self._filter_readable_paths():
            with path.open() as f:
                data = yaml.safe_load(f)
                if isinstance(data, dict):
                    result.update(data)
            self._loaded_files = (path,)
        return result

class Parser(argclass.Parser):
    host: str = "localhost"

parser = Parser(
    config_files=["config.yaml"],
    config_parser_class=YAMLDefaultsParser,
)
```

### Strict Mode

Use `strict_config=True` to raise errors on configuration problems:

<!--- name: test_config_strict_mode --->
```python
import argclass
from pathlib import Path
from tempfile import NamedTemporaryFile

class Parser(argclass.Parser):
    host: str = "localhost"

# Config with duplicate keys (invalid in strict mode)
CONFIG_CONTENT = """
[DEFAULT]
host = first.example.com
host = second.example.com
"""

with NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
    f.write(CONFIG_CONTENT)
    config_path = f.name

# Non-strict mode (default): last value wins, no error
parser1 = Parser(config_files=[config_path], strict_config=False)
parser1.parse_args([])
assert parser1.host == "second.example.com"

# Strict mode: raises DuplicateOptionError
try:
    parser2 = Parser(config_files=[config_path], strict_config=True)
    assert False, "Should have raised"
except Exception as e:
    assert "DuplicateOptionError" in type(e).__name__

Path(config_path).unlink()
```

**Behavior by format:**

| Format | `strict_config=False` (default) | `strict_config=True` |
|--------|--------------------------------|---------------------|
| **INI** | Duplicate keys: last wins | Raises `DuplicateOptionError` |
| **JSON** | Parse errors: silently skipped | Raises `JSONDecodeError` |
| **TOML** | Parse errors: silently skipped | Raises parse exception |

:::{tip}
Use `strict_config=True` in development to catch configuration errors early.
Use `strict_config=False` (default) in production for resilience.
:::

---

## Loading Behavior

### File Search

Specify multiple paths - all readable files are merged:

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

### Dynamic Paths

Use `os.getenv()` to allow users to override config file locations:

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

**This pattern allows:**

| Location | Purpose |
|----------|---------|
| `$MYAPP_CONFIG` | Operator override |
| `/etc/myapp.ini` | System-wide defaults |
| `~/.config/myapp.ini` | User preferences |
| `./config.ini` | Local development |

### Multi-File Merging

Multiple config files are **merged together** - later files override earlier ones:

:::{card} Example: Global + User Config
```ini
# /etc/myapp.ini (global defaults)
[DEFAULT]
log_level = warning
max_connections = 100

[database]
host = db.production.example.com
```

```ini
# ~/.config/myapp.ini (user overrides)
[DEFAULT]
log_level = debug
```

**Result:** `log_level = debug`, `max_connections = 100`, `database.host = db.production.example.com`
:::

```python
import os
import argclass

class DatabaseGroup(argclass.Group):
    host: str = "localhost"
    port: int = 5432

class Parser(argclass.Parser):
    log_level: str = "info"
    max_connections: int = 10
    database = DatabaseGroup()

parser = Parser(config_files=[
    "/etc/myapp.ini",
    os.path.expanduser("~/.config/myapp.ini"),
])
```

### Value Priority

Values are applied in order (later overrides earlier):

:::{card}
1. **Class defaults** → 2. **Config files** → 3. **Environment variables** → 4. **CLI arguments**
:::

**Override Matrix:**

| Source | Overrides | Overridden by |
|--------|-----------|---------------|
| Class default | — | Config, Env, CLI |
| Config file | Class default | Env, CLI |
| Environment variable | Class default, Config | CLI |
| CLI argument | All | — |

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

**End-to-end example with all sources:**

<!--- name: test_config_priority_full --->
```python
import os
import argclass
from pathlib import Path
from tempfile import NamedTemporaryFile

class Parser(argclass.Parser):
    host: str = "default-host"      # 1. Class default
    port: int = 8080                # 1. Class default
    debug: bool = False             # 1. Class default
    timeout: int = 30               # 1. Class default

# 2. Config file sets host and port
CONFIG_CONTENT = """
[DEFAULT]
host = config-host
port = 9000
"""

with NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
    f.write(CONFIG_CONTENT)
    config_path = f.name

# 3. Environment sets port and debug
os.environ["APP_PORT"] = "9500"
os.environ["APP_DEBUG"] = "true"

parser = Parser(
    config_files=[config_path],
    auto_env_var_prefix="APP_"
)

# 4. CLI sets only timeout
parser.parse_args(["--timeout", "60"])

# Final values:
assert parser.host == "config-host"    # From config (no env/cli)
assert parser.port == 9500             # From env (overrides config)
assert parser.debug is True            # From env (overrides default)
assert parser.timeout == 60            # From CLI (overrides default)

# Cleanup
del os.environ["APP_PORT"]
del os.environ["APP_DEBUG"]
Path(config_path).unlink()
```

---

## Syntax Reference

### Group Sections

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

### Boolean Values

| True values | False values |
|-------------|--------------|
| `true`, `yes`, `on`, `1` | `false`, `no`, `off`, `0` |

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

---

## Config as Argument Value

:::{note}
This is a **separate feature** from `config_files`. Instead of presetting CLI argument
defaults, this adds a `--config` argument that loads structured data for your
application to use programmatically.
:::

Useful when your application needs complex nested structures, arrays, or
application-specific data that doesn't map to CLI arguments.

### Built-in Config Types

```python
import argclass

class Parser(argclass.Parser):
    # JSON config file argument
    json_config = argclass.Config(config_class=argclass.JSONConfig)

    # INI config file argument
    ini_config = argclass.Config(config_class=argclass.INIConfig)

    # TOML config file argument (Python 3.11+ or tomli package)
    toml_config = argclass.Config(config_class=argclass.TOMLConfig)
```

### JSON Example

<!--- name: test_config_json_argument --->
```python
import argclass
import json
from pathlib import Path
from tempfile import NamedTemporaryFile

class Parser(argclass.Parser):
    config = argclass.Config(config_class=argclass.JSONConfig)

# Config file content
CONFIG_DATA = {
    "database": {
        "host": "localhost",
        "port": 5432,
        "replicas": ["replica1.db", "replica2.db"]
    },
    "features": ["auth", "logging"]
}

with NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
    json.dump(CONFIG_DATA, f)
    config_path = f.name

parser = Parser()
parser.parse_args(["--config", config_path])

# Access nested data
assert parser.config["database"]["host"] == "localhost"
assert parser.config["database"]["replicas"] == ["replica1.db", "replica2.db"]
assert parser.config["features"] == ["auth", "logging"]

Path(config_path).unlink()
```

### TOML Example

<!--- name: test_config_toml_argument --->
```python
import argclass
from pathlib import Path
from tempfile import NamedTemporaryFile

class Parser(argclass.Parser):
    config = argclass.Config(config_class=argclass.TOMLConfig)

# Config file content
CONFIG_CONTENT = """
[database]
host = "localhost"
port = 5432
replicas = ["replica1.db", "replica2.db"]

[features]
enabled = ["auth", "logging"]
"""

with NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
    f.write(CONFIG_CONTENT)
    config_path = f.name

parser = Parser()
parser.parse_args(["--config", config_path])

# Access nested data
assert parser.config["database"]["host"] == "localhost"
assert parser.config["database"]["replicas"] == ["replica1.db", "replica2.db"]
assert parser.config["features"]["enabled"] == ["auth", "logging"]

Path(config_path).unlink()
```

### Custom Config Parsers

For other formats like YAML, extend `ConfigAction`:

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

### Key Difference

| Feature | `config_files=[...]` | `argclass.Config()` |
|---------|---------------------|---------------------|
| **Purpose** | Preset CLI argument defaults | Load structured data |
| **Access** | Via parser attributes | Via dict-like access |
| **Use case** | Site configuration | Application data |
