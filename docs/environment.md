# Environment Variables

argclass can read default values from environment variables.

:::{warning}
**Security Risk:** Environment variables are inherited by all child processes.
Any subprocess your application spawns (shell commands, external tools, other
scripts) can read secrets from environment variables. Always call `sanitize_env()`
after parsing to remove sensitive values. See [Sanitizing Environment](#sanitizing-environment).
:::

## Per-Argument Environment Variables

Specify an environment variable for a single argument:

<!--- name: test_env_per_argument --->
```python
import os
import argclass

os.environ["DATABASE_URL"] = "postgres://localhost/db"
os.environ["API_KEY"] = "secret123"

class Parser(argclass.Parser):
    database_url: str = argclass.Argument(
        env_var="DATABASE_URL",
        default="sqlite:///app.db"
    )
    api_key: str = argclass.Argument(env_var="API_KEY")

parser = Parser()
parser.parse_args([])

assert parser.database_url == "postgres://localhost/db"
assert parser.api_key == "secret123"

del os.environ["DATABASE_URL"]
del os.environ["API_KEY"]
```

## Auto Environment Prefix

Automatically create environment variables for all arguments:

<!--- name: test_env_auto_prefix --->
```python
import os
import argclass

os.environ["APP_HOST"] = "0.0.0.0"
os.environ["APP_PORT"] = "9000"
os.environ["APP_DEBUG"] = "true"

class Parser(argclass.Parser):
    host: str = "localhost"
    port: int = 8080
    debug: bool = False

parser = Parser(auto_env_var_prefix="APP_")
parser.parse_args([])

assert parser.host == "0.0.0.0"
assert parser.port == 9000
assert parser.debug is True

del os.environ["APP_HOST"]
del os.environ["APP_PORT"]
del os.environ["APP_DEBUG"]
```

## Group Environment Variables

Groups use their prefix in environment variable names:

<!--- name: test_env_groups --->
```python
import os
import argclass

os.environ["APP_DATABASE_HOST"] = "db.example.com"
os.environ["APP_DATABASE_PORT"] = "3306"

class DatabaseGroup(argclass.Group):
    host: str = "localhost"
    port: int = 5432

class Parser(argclass.Parser):
    database = DatabaseGroup()

parser = Parser(auto_env_var_prefix="APP_")
parser.parse_args([])

assert parser.database.host == "db.example.com"
assert parser.database.port == 3306

del os.environ["APP_DATABASE_HOST"]
del os.environ["APP_DATABASE_PORT"]
```

## Priority

Environment variables override config files but are overridden by CLI arguments:

1. Class defaults
2. Config file values
3. **Environment variables**
4. Command-line arguments

<!--- name: test_env_priority --->
```python
import os
import argclass
from pathlib import Path
from tempfile import NamedTemporaryFile

# Create config file
with NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
    f.write("[DEFAULT]\n")
    f.write("port = 9000\n")
    config_path = f.name

os.environ["APP_PORT"] = "9500"

class Parser(argclass.Parser):
    port: int = 8080  # Default

# CLI wins over env
parser1 = Parser(
    config_files=[config_path],
    auto_env_var_prefix="APP_"
)
parser1.parse_args(["--port", "3000"])
assert parser1.port == 3000

# Without CLI, env wins over config
parser2 = Parser(
    config_files=[config_path],
    auto_env_var_prefix="APP_"
)
parser2.parse_args([])
assert parser2.port == 9500

del os.environ["APP_PORT"]

# Without env, config wins over default
parser3 = Parser(config_files=[config_path])
parser3.parse_args([])
assert parser3.port == 9000

Path(config_path).unlink()
```

## Sanitizing Environment

:::{danger}
**Child processes inherit environment variables.** When your application runs
shell commands, spawns subprocesses, or calls external tools, those processes
receive a copy of all environment variables - including your secrets.

**Example attack scenario:**
1. Your app reads `DB_PASSWORD` from environment
2. Your app runs `subprocess.run(["backup-tool", ...])`
3. `backup-tool` (or malicious code in it) reads `DB_PASSWORD`
4. Your secret is compromised

**Solution:** Call `parser.sanitize_env()` immediately after parsing to remove
sensitive environment variables before spawning any child processes.
:::

Remove sensitive variables after parsing:

<!--- name: test_env_sanitize --->
```python
import os
import argclass

os.environ["API_KEY"] = "secret_key"
os.environ["DB_PASSWORD"] = "secret_pass"

class Parser(argclass.Parser):
    api_key: str = argclass.Secret(env_var="API_KEY")
    password: str = argclass.Secret(env_var="DB_PASSWORD")

parser = Parser()
parser.parse_args([])

# Values are parsed
assert str(parser.api_key) == "secret_key"
assert str(parser.password) == "secret_pass"

# Remove used environment variables
parser.sanitize_env()

# These are now unset
assert "API_KEY" not in os.environ
assert "DB_PASSWORD" not in os.environ
```

## Boolean Environment Variables

These values are recognized as `True`:
- `y`, `yes`, `true`, `t`
- `enable`, `enabled`
- `1`, `on`

These values are recognized as `False`:
- `n`, `no`, `false`, `f`
- `disable`, `disabled`
- `0`, `off`

<!--- name: test_env_bool --->
```python
import os
import argclass

class Parser(argclass.Parser):
    flag1: bool = False
    flag2: bool = False
    flag3: bool = True
    flag4: bool = True

os.environ["APP_FLAG1"] = "yes"
os.environ["APP_FLAG2"] = "1"
os.environ["APP_FLAG3"] = "no"
os.environ["APP_FLAG4"] = "off"

parser = Parser(auto_env_var_prefix="APP_")
parser.parse_args([])

assert parser.flag1 is True
assert parser.flag2 is True
assert parser.flag3 is False
assert parser.flag4 is False

del os.environ["APP_FLAG1"]
del os.environ["APP_FLAG2"]
del os.environ["APP_FLAG3"]
del os.environ["APP_FLAG4"]
```

## Combining with Config Files

Use environment variables to point to config files:

<!--- name: test_env_config_path --->
```python
import os
import argclass
from pathlib import Path
from tempfile import NamedTemporaryFile

# Create config file
with NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
    f.write("[DEFAULT]\n")
    f.write("host = config.example.com\n")
    f.write("port = 9000\n")
    config_path = f.name

os.environ["APP_CONFIG"] = config_path

class Parser(argclass.Parser):
    host: str = "localhost"
    port: int = 8080

config_file = os.environ.get("APP_CONFIG", "config.ini")
parser = Parser(config_files=[config_file])
parser.parse_args([])

assert parser.host == "config.example.com"
assert parser.port == 9000

del os.environ["APP_CONFIG"]
Path(config_path).unlink()
```
