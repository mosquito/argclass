# Configuration Files

Load default values for CLI arguments from configuration files. Useful for
site-specific defaults, deployment configurations, and separating configuration
from code.

argclass has three separate config mechanisms. Two of them happen to use a
`--config` flag in their examples, so pick by what you actually want:

| I want to…                                              | Use (→ API)                                           | Read more                                                                     |
| ------------------------------------------------------- | ----------------------------------------------------- | ----------------------------------------------------------------------------- |
| load defaults from files **I (the developer) choose**   | {py:class}`config_files=[...] <argclass.Parser>`        | [Quick Start](#quick-start) below                                             |
| let the **end user** point at a file of defaults        | {py:class}`config_argument="--config" <argclass.Parser>` | [User-Supplied Config File](#user-supplied-config-file-config_argument) below  |
| read **arbitrary data** from a file into one attribute  | {py:func}`argclass.Config() <argclass.Config>`         | [`Config` reference](api.md#config)                                           |

The first two feed defaults to your other arguments; `Config()` is unrelated —
it loads a whole file into a single attribute and touches nothing else.

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

## User-Supplied Config File (`config_argument`)

`config_files=` is chosen by the developer at construction time. To
let the **end user** point at a config file, pass
`config_argument="--config"` — argclass adds the flag and uses the
file's values as defaults for your other arguments. The file is read
before the defaults are fixed, so even `--help` shows the values it
supplies:

<!--- name: test_config_argument --->
```python
import argclass
from pathlib import Path
from tempfile import NamedTemporaryFile

class Parser(argclass.Parser):
    host: str = "localhost"
    port: int = 8080

with NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
    f.write("[DEFAULT]\nhost = example.com\nport = 9000\n")
    config_path = f.name

parser = Parser(config_argument="--config")
parser.parse_args(["--config", config_path, "--port", "1234"])

assert parser.host == "example.com"   # default from the file
assert parser.port == 1234            # CLI still wins

Path(config_path).unlink()
```

What you need to know:

- **Priority.** The chain extends naturally: declared defaults <
  `config_files` < `config_argument` file < env vars < CLI args.
- **Missing or broken file is an error.** A path the user passes
  explicitly that does not exist or cannot be parsed raises
  `ConfigurationError` — unlike `config_files`, which is a lenient
  search list.
- **Required arguments** are satisfied by a value from the file.

Fine print:

- The file format is the shared `config_parser_class` (INI by
  default; pass `JSONDefaultsParser` / `TOMLDefaultsParser` for other
  formats).
- Several aliases are accepted: `config_argument=("-c", "--config")`.
- `parser.loaded_config_files` reports which files were applied, in
  priority order.
- The flag is resolved by the parser whose `parse_args()` you call,
  so put it before any subcommand on the command line.

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

All parsers validate that config values match expected types. If a value doesn't match
(e.g., a string where a list is expected), `UnexpectedConfigValue` is raised.

### INI Complex Types

All INI values are strings. For lists, use Python literal syntax:

```ini
[DEFAULT]
ports = [8080, 8081, 8082]
hosts = ["primary.example.com", "backup.example.com"]
```

These are parsed using `ast.literal_eval` when the argument type requires it.

### Type Conversion

Type converters specified with `type=` are automatically applied to values
loaded from config files. This ensures config values are converted the same
way as CLI arguments:

<!--- name: test_config_type_conversion_doc --->
```python
import argclass
from pathlib import Path
from tempfile import NamedTemporaryFile

class Parser(argclass.Parser):
    # type=Path converts config string to Path object
    data_dir: Path = argclass.Argument(type=Path)

    # type applies to each list item
    ports: list = argclass.Argument(
        nargs=argclass.Nargs.ONE_OR_MORE,
        type=int,
    )

CONFIG_CONTENT = """
[DEFAULT]
data_dir = /var/data
ports = ["8080", "8081", "8082"]
"""

with NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
    f.write(CONFIG_CONTENT)
    config_path = f.name

parser = Parser(config_files=[config_path])
parser.parse_args([])

assert isinstance(parser.data_dir, Path)
assert parser.data_dir == Path("/var/data")
assert parser.ports == [8080, 8081, 8082]
assert all(isinstance(p, int) for p in parser.ports)

Path(config_path).unlink()
```

**Type vs Converter:**

| Parameter | Applied to | Use Case |
|-----------|-----------|----------|
| `type` | Each value (CLI or config) | Convert int, float, Path, URL |
| `converter` | Final result after parsing | Convert list→set, aggregate |

**Error handling:** Type conversion errors propagate immediately:

```python
# Config: port = "not_a_number"
# Raises: ValueError: invalid literal for int() with base 10
```

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

:::{note}
TOML support uses the standard library `tomllib` module (Python 3.11+).
For Python 3.10, install the `tomli` package as a fallback:

```console
pip install tomli
```

argclass automatically uses `tomllib` when available, falling back to `tomli`.
:::

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
from typing import Any, Mapping

class YAMLDefaultsParser(argclass.AbstractDefaultsParser):
    def parse(self) -> Mapping[str, Any]:
        import yaml
        result: dict[str, Any] = {}
        for path in self._filter_readable_paths():
            with path.open() as f:
                data = yaml.safe_load(f)
                if isinstance(data, dict):
                    result.update(data)
            self._loaded_files = (path,)
        self._values = result  # Required for get_value() to work
        return result

class Parser(argclass.Parser):
    host: str = "localhost"

parser = Parser(
    config_files=["config.yaml"],
    config_parser_class=YAMLDefaultsParser,
)
```

#### Type-Aware Value Loading

The `AbstractDefaultsParser` provides a `get_value()` method that handles type
conversion and validation based on `ValueKind`:

| ValueKind | Description | INI Behavior | JSON/TOML Behavior |
|-----------|-------------|--------------|-------------------|
| `STRING` | Default, no conversion | Return as-is | Return as-is |
| `SEQUENCE` | Lists/tuples or any iterable | `ast.literal_eval` | Validate is list |
| `BOOL` | Boolean values | String → bool | Validate is bool |

For formats with native types (JSON, TOML, YAML), the base class validates
that the value matches the expected kind. For string-based formats (INI),
override `_convert()` to parse strings:

```python
import ast
import argclass
from typing import Any, Mapping

class CustomParser(argclass.AbstractDefaultsParser):
    def parse(self) -> Mapping[str, Any]:
        result: dict[str, Any] = {}
        # ... load data into result dict ...
        self._values = result
        return result

    def _convert(
        self, key: str, value: Any, kind: argclass.ValueKind,
    ) -> Any:
        """Convert string values based on expected kind."""
        if not isinstance(value, str):
            return value  # Already correct type

        if kind == argclass.ValueKind.SEQUENCE:
            return ast.literal_eval(value)
        if kind == argclass.ValueKind.BOOL:
            return value.lower() in ('true', 'yes', '1')

        return value
```

If a value doesn't match the expected kind after conversion, `UnexpectedConfigValue`
is raised automatically by the base class.

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

Values are applied least-specific to most-specific — class defaults < config
files < environment variables < CLI arguments — so each source overrides the
ones before it. The two examples below show the chain in action.

:::{seealso}
The full priority chain (including `config_argument`), the override matrix, and
why generation follows the same order:
[The configuration model](explanation/configuration-model.md).
:::

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

The exact on-disk syntax — group-to-section mapping, nested groups, accepted
boolean literals, and CLI override — lives in the
[Config File Syntax](config-file-reference.md) reference page.

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

:::{note}
Requires `tomllib` (Python 3.11+) or `tomli` package for Python 3.10.
:::

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

<!--- name: test_config_custom_yaml_action --->
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
