# Configuration Files

argclass can load default values from configuration files.

## INI Files

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

# Create config file
with NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
    f.write("[DEFAULT]\n")
    f.write("host = example.com\n")
    f.write("port = 9000\n")
    f.write("debug = true\n")
    config_path = f.name

parser = Parser(config_files=[config_path])
parser.parse_args([])

assert parser.host == "example.com"
assert parser.port == 9000
assert parser.debug is True

Path(config_path).unlink()
```

## Config File Search

Specify multiple paths - first found is used:

<!--- name: test_config_search --->
```python
import argclass
from pathlib import Path
from tempfile import NamedTemporaryFile

class Parser(argclass.Parser):
    value: str = "default"

# Create config file
with NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
    f.write("[DEFAULT]\n")
    f.write("value = from_config\n")
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

## Config Priority

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

# Create config with different value
with NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
    f.write("[DEFAULT]\nport = 9000\n")
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

## Group Sections

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

# Create config
with NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
    f.write("[DEFAULT]\n")
    f.write("verbose = true\n\n")
    f.write("[server]\n")
    f.write("host = 0.0.0.0\n")
    f.write("port = 9000\n\n")
    f.write("[database]\n")
    f.write("host = db.example.com\n")
    f.write("port = 3306\n")
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

## Boolean Values

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

with NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
    f.write("[DEFAULT]\n")
    f.write("flag1 = yes\n")
    f.write("flag2 = 1\n")
    f.write("flag3 = no\n")
    f.write("flag4 = off\n")
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

Command-line arguments override config file values:

<!--- name: test_config_cli_override --->
```python
import argclass
from pathlib import Path
from tempfile import NamedTemporaryFile

class Parser(argclass.Parser):
    host: str = "localhost"
    port: int = 8080

with NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
    f.write("[DEFAULT]\n")
    f.write("host = config.example.com\n")
    f.write("port = 9000\n")
    config_path = f.name

parser = Parser(config_files=[config_path])
parser.parse_args(["--port", "3000"])

assert parser.host == "config.example.com"  # From config
assert parser.port == 3000  # From CLI (override)

Path(config_path).unlink()
```
