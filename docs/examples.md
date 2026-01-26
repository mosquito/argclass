# Examples Gallery

Copy-pastable examples for common CLI patterns. Each example is self-contained
and demonstrates specific argclass features you can adapt for your own projects.

## Complete Runnable Application

Here's a full, production-ready CLI application you can copy and run immediately.
This example demonstrates the standard structure for argclass applications:

<!--- name: test_example_complete_app --->
```python
#!/usr/bin/env python3
"""A complete CLI application demonstrating argclass best practices."""

import sys
import argclass

class App(argclass.Parser):
    """File greeting utility.

    Reads names from a file and prints personalized greetings.
    """

    input_file: str = argclass.Argument(
        "-i", "--input",
        help="File containing names (one per line)",
        default="-"
    )
    greeting: str = argclass.Argument(
        "-g", "--greeting",
        help="Greeting to use",
        default="Hello"
    )
    uppercase: bool = argclass.Argument(
        "-u", "--uppercase",
        default=False,
        action=argclass.Actions.STORE_TRUE,
        help="Output in uppercase"
    )
    verbose: bool = argclass.Argument(
        "-v", "--verbose",
        default=False,
        action=argclass.Actions.STORE_TRUE,
        help="Enable verbose output"
    )

    def __call__(self) -> int:
        """Execute the application logic."""
        if self.verbose:
            print(f"Reading from: {self.input_file}", file=sys.stderr)

        # Process names (in real app, read from file)
        names = ["World", "argclass"]  # Simulated input

        for name in names:
            message = f"{self.greeting}, {name}!"
            if self.uppercase:
                message = message.upper()
            print(message)

        return 0


def main() -> int:
    """Entry point for the CLI application."""
    app = App()

    try:
        app.parse_args([])  # In production: app.parse_args()
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 1

    return app()


# For testing purposes
app = App()
app.parse_args(["--greeting", "Hi", "--uppercase", "--verbose"])
assert app.greeting == "Hi"
assert app.uppercase is True
assert app.verbose is True
```

**Sample `--help` output:**

```
$ python app.py --help
usage: app.py [-h] [-i INPUT] [-g GREETING] [-u] [-v]

File greeting utility.

Reads names from a file and prints personalized greetings.

options:
  -h, --help            show this help message and exit
  -i, --input INPUT     File containing names (one per line) (default: -)
  -g, --greeting GREETING
                        Greeting to use (default: Hello)
  -u, --uppercase       Output in uppercase (default: False)
  -v, --verbose         Enable verbose output (default: False)
```

**Sample run:**

```
$ python app.py --greeting "Welcome" --uppercase
WELCOME, WORLD!
WELCOME, ARGCLASS!
```

**Key patterns in this example:**
- Docstrings become help text automatically
- `__call__` method implements the main logic
- `main()` function handles parse errors gracefully
- Returns exit codes (0 for success, non-zero for errors)
- Uses `-` as default for stdin input (common Unix pattern)

---

## Simple CLI Tool

This example shows the fundamental building blocks of any CLI application.
It demonstrates how to create a parser class with different argument types:
a required positional-style argument, an optional argument with a default,
and a boolean flag.

**Key features demonstrated:**
- Required arguments (`name: str`)
- Optional arguments with defaults (`count: int = 1`)
- Boolean flags (`loud: bool = False`)
- Short aliases (`-c` for `--count`)
- Implementing `__call__` for executable parsers

<!--- name: test_example_simple --->
```python
import argclass

class Greeter(argclass.Parser):
    """Greet someone."""
    name: str = argclass.Argument(help="Name to greet")
    count: int = argclass.Argument("-c", "--count", default=1, help="Times to greet")
    loud: bool = False

    def __call__(self) -> int:
        greeting = f"Hello, {self.name}!"
        if self.loud:
            greeting = greeting.upper()
        for _ in range(self.count):
            print(greeting)
        return 0

greeter = Greeter()
greeter.parse_args(["--name", "World", "-c", "2", "--loud"])
assert greeter.name == "World"
assert greeter.count == 2
assert greeter.loud is True
```

## Subcommand CLI (git-style)

Many professional CLI tools use subcommands to organize functionality:
`git commit`, `docker run`, `kubectl apply`. This pattern makes complex tools
intuitive by grouping related operations under descriptive command names.

This example shows how to build a project management tool with `init`, `build`,
and `deploy` subcommands. Each subcommand is a separate parser class with its
own arguments, while the parent parser holds global options like `--verbose`.

**Key features demonstrated:**
- Subcommand pattern for multi-command CLIs
- Global options available to all subcommands
- `choices` parameter for constrained values
- `Path` type for file system arguments
- Each subcommand as a callable with its own `__call__` method

<!--- name: test_example_subcommands --->
```python
import argclass
from pathlib import Path

class InitCommand(argclass.Parser):
    """Initialize a new project."""
    name: str = argclass.Argument(help="Project name")
    template: str = argclass.Argument(default="basic", choices=["basic", "full"])

    def __call__(self) -> int:
        print(f"Initializing {self.name} with {self.template} template")
        return 0

class BuildCommand(argclass.Parser):
    """Build the project."""
    output: Path = argclass.Argument("-o", "--output", default=Path("dist"))
    release: bool = False

    def __call__(self) -> int:
        mode = "release" if self.release else "debug"
        print(f"Building to {self.output} ({mode})")
        return 0

class DeployCommand(argclass.Parser):
    """Deploy to production."""
    target: str = argclass.Argument(choices=["staging", "production"])
    dry_run: bool = False

    def __call__(self) -> int:
        if self.dry_run:
            print(f"Would deploy to {self.target}")
        else:
            print(f"Deploying to {self.target}")
        return 0

class CLI(argclass.Parser):
    """Project management tool."""
    verbose: bool = argclass.Argument("-v", "--verbose", default=False,
                                      action=argclass.Actions.STORE_TRUE)
    init = InitCommand()
    build = BuildCommand()
    deploy = DeployCommand()

cli = CLI()
cli.parse_args(["build", "--output", "/tmp/out", "--release"])
assert cli.build.output == Path("/tmp/out")
assert cli.build.release is True
```

## Config + Env + CLI

Real-world applications often need configuration from multiple sources:
config files for deployment defaults, environment variables for container
orchestration, and CLI arguments for ad-hoc overrides. argclass handles
all three with a clear priority order: CLI > environment > config file.

This example demonstrates the complete configuration stack. It shows how
defaults in a config file can be overridden by environment variables, which
can in turn be overridden by command-line arguments. It also demonstrates
secret handling with `argclass.Secret` and the `sanitize_env()` method.

**Key features demonstrated:**
- Config file loading with `config_files` parameter
- Automatic environment variable binding with `auto_env_var_prefix`
- Priority order: CLI arguments override env vars override config
- Secret masking with `argclass.Secret`
- `sanitize_env()` to remove secrets from environment
- Argument groups for organizing related settings

<!--- name: test_example_full_config --->
```python
import os
import argclass
from pathlib import Path
from tempfile import NamedTemporaryFile

class DatabaseGroup(argclass.Group):
    """Database connection settings."""
    host: str = "localhost"
    port: int = 5432
    name: str = "app"
    password: str = argclass.Secret(env_var="DB_PASSWORD")

class ServerGroup(argclass.Group):
    """HTTP server settings."""
    host: str = "127.0.0.1"
    port: int = 8080
    workers: int = 4

class App(argclass.Parser):
    """Application server."""
    debug: bool = False
    log_level: str = argclass.Argument(
        default="info",
        choices=["debug", "info", "warning", "error"]
    )
    database = DatabaseGroup()
    server = ServerGroup()

# Config file (lowest priority)
CONFIG = """
[DEFAULT]
log_level = warning

[database]
host = db.example.com
port = 5432
name = production

[server]
host = 0.0.0.0
port = 80
workers = 8
"""

with NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
    f.write(CONFIG)
    config_path = f.name

# Environment variables (override config)
os.environ["APP_DEBUG"] = "true"
os.environ["APP_SERVER_PORT"] = "9000"
os.environ["DB_PASSWORD"] = "secret123"

app = App(
    config_files=[config_path],
    auto_env_var_prefix="APP_"
)

# CLI arguments (override everything)
app.parse_args(["--log-level", "debug"])

# Sanitize secrets
app.sanitize_env()

# Results
assert app.debug is True                    # From env
assert app.log_level == "debug"             # From CLI
assert app.database.host == "db.example.com"  # From config
assert app.database.port == 5432            # From config
assert str(app.database.password) == "secret123"  # From env
assert app.server.host == "0.0.0.0"         # From config
assert app.server.port == 9000              # From env (overrides config)
assert app.server.workers == 8              # From config

# Cleanup (use pop since sanitize_env may have removed some)
os.environ.pop("APP_DEBUG", None)
os.environ.pop("APP_SERVER_PORT", None)
Path(config_path).unlink()
```

## Configuration Formats

argclass supports multiple configuration file formats out of the box.
Each format can be used to provide default values that are overridden
by environment variables and CLI arguments. Here are examples for each
supported format.

### INI Configuration

INI is the simplest format, ideal for flat configurations. Sections map
to argument groups. Boolean values support various formats: `true/false`,
`yes/no`, `on/off`, `1/0`.

<!--- name: test_example_ini_config --->
```python
import argclass
from pathlib import Path
from tempfile import NamedTemporaryFile

class DatabaseGroup(argclass.Group):
    host: str = "localhost"
    port: int = 5432
    name: str = "mydb"

class Parser(argclass.Parser):
    debug: bool = False
    workers: int = 4
    database = DatabaseGroup()

CONFIG_INI = """
[DEFAULT]
debug = yes
workers = 8

[database]
host = db.example.com
port = 5432
name = production
"""

with NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
    f.write(CONFIG_INI)
    config_path = f.name

parser = Parser(config_files=[config_path])
parser.parse_args([])

assert parser.debug is True
assert parser.workers == 8
assert parser.database.host == "db.example.com"
assert parser.database.name == "production"

Path(config_path).unlink()
```

### JSON Configuration

JSON is useful when you need structured data or when your config is
generated programmatically. Nested objects map to argument groups.

<!--- name: test_example_json_config --->
```python
import argclass
from pathlib import Path
from tempfile import NamedTemporaryFile

class ServerGroup(argclass.Group):
    host: str = "127.0.0.1"
    port: int = 8080

class Parser(argclass.Parser):
    debug: bool = False
    log_level: str = "info"
    server = ServerGroup()

CONFIG_JSON = """
{
    "debug": true,
    "log_level": "debug",
    "server": {
        "host": "0.0.0.0",
        "port": 9000
    }
}
"""

with NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
    f.write(CONFIG_JSON)
    config_path = f.name

parser = Parser(
    config_files=[config_path],
    config_parser_class=argclass.JSONDefaultsParser,
)
parser.parse_args([])

assert parser.debug is True
assert parser.log_level == "debug"
assert parser.server.host == "0.0.0.0"
assert parser.server.port == 9000

Path(config_path).unlink()
```

### TOML Configuration

TOML provides a clean syntax popular in modern Python projects (like
`pyproject.toml`). It has native support for different data types.

:::{note}
TOML requires Python 3.11+ (stdlib `tomllib`) or the `tomli` package
for Python 3.10.
:::

<!--- name: test_example_toml_config --->
```python
import argclass
from pathlib import Path
from tempfile import NamedTemporaryFile

class CacheGroup(argclass.Group):
    enabled: bool = True
    ttl: int = 300
    backend: str = "memory"

class Parser(argclass.Parser):
    name: str = "myapp"
    version: str = "1.0.0"
    cache = CacheGroup()

CONFIG_TOML = """
name = "production-app"
version = "2.1.0"

[cache]
enabled = true
ttl = 3600
backend = "redis"
"""

with NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
    f.write(CONFIG_TOML)
    config_path = f.name

parser = Parser(
    config_files=[config_path],
    config_parser_class=argclass.TOMLDefaultsParser,
)
parser.parse_args([])

assert parser.name == "production-app"
assert parser.version == "2.1.0"
assert parser.cache.enabled is True
assert parser.cache.ttl == 3600
assert parser.cache.backend == "redis"

Path(config_path).unlink()
```

### Multiple Config Files with Fallback

You can specify multiple config files. argclass reads them in order,
with later files overriding earlier ones. Missing files are silently
ignored, making this perfect for layered configuration.

<!--- name: test_example_config_fallback --->
```python
import argclass
from pathlib import Path
from tempfile import NamedTemporaryFile

class Parser(argclass.Parser):
    host: str = "localhost"
    port: int = 8080
    debug: bool = False

# System-wide defaults
SYSTEM_CONFIG = """
[DEFAULT]
host = 0.0.0.0
port = 80
"""

# User overrides
USER_CONFIG = """
[DEFAULT]
port = 8080
debug = true
"""

with NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
    f.write(SYSTEM_CONFIG)
    system_path = f.name

with NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
    f.write(USER_CONFIG)
    user_path = f.name

parser = Parser(config_files=[
    "/etc/myapp/config.ini",  # Missing - ignored
    system_path,               # Provides host=0.0.0.0, port=80
    user_path,                 # Overrides port=8080, adds debug=true
])
parser.parse_args([])

assert parser.host == "0.0.0.0"   # From system config
assert parser.port == 8080        # Overridden by user config
assert parser.debug is True       # From user config

Path(system_path).unlink()
Path(user_path).unlink()
```

## File Processing Tool

File processing utilities are one of the most common CLI applications.
This example shows how to build a tool that accepts multiple input files,
an output directory, and various processing options.

The pattern demonstrated here is useful for any batch processing tool:
image converters, log analyzers, code formatters, or data transformers.
The `--dry-run` flag is a best practice that lets users preview changes
before committing to them.

**Key features demonstrated:**
- Multiple input files with `nargs="+"` and `list[Path]`
- `Path` type for automatic path handling
- `--dry-run` pattern for safe previews
- Boolean flags with explicit `action=STORE_TRUE`
- Combining short (`-n`) and long (`--dry-run`) aliases

<!--- name: test_example_file_processor --->
```python
import argclass
from pathlib import Path

class FileProcessor(argclass.Parser):
    """Process files in batch."""
    input: list[Path] = argclass.Argument(
        "-i", "--input",
        nargs="+",
        help="Input files to process"
    )
    output: Path = argclass.Argument(
        "-o", "--output",
        default=Path("output"),
        help="Output directory"
    )
    pattern: str = argclass.Argument(
        "-p", "--pattern",
        default="*",
        help="Glob pattern to match"
    )
    recursive: bool = False
    dry_run: bool = argclass.Argument(
        "-n", "--dry-run",
        default=False,
        action=argclass.Actions.STORE_TRUE,
        help="Show what would be done"
    )

    def __call__(self) -> int:
        for path in self.input:
            if self.dry_run:
                print(f"Would process: {path}")
            else:
                print(f"Processing: {path}")
        return 0

processor = FileProcessor()
processor.parse_args([
    "-i", "file1.txt", "file2.txt",
    "-o", "/tmp/out",
    "--recursive",
    "--dry-run"
])

assert processor.input == [Path("file1.txt"), Path("file2.txt")]
assert processor.output == Path("/tmp/out")
assert processor.recursive is True
assert processor.dry_run is True
```

## HTTP Client CLI

API clients often need flexible authentication and request configuration.
This example shows how to build a curl-like tool with support for different
HTTP methods, custom headers, request bodies, and authentication options.

The argument groups (`AuthGroup`, `RequestOptions`) keep related settings
organized and make the `--help` output more readable. Using `argclass.Secret`
for tokens and passwords ensures they won't appear in logs or process listings.

**Key features demonstrated:**
- Curl-like interface with `-X`, `-H`, `-d` options
- Multiple headers with `nargs="*"` and `list[str]`
- Optional arguments with `str | None` type
- Secrets for sensitive authentication data
- Grouped settings for better organization
- `choices` for HTTP methods

<!--- name: test_example_http_client --->
```python
import os
import argclass

class AuthGroup(argclass.Group):
    """Authentication settings."""
    token: str = argclass.Secret(env_var="API_TOKEN")
    username: str | None = None
    password: str = argclass.Secret()

class RequestOptions(argclass.Group):
    """Request configuration."""
    timeout: int = 30
    retries: int = 3
    verify_ssl: bool = True

class HTTPClient(argclass.Parser):
    """HTTP API client."""
    base_url: str = argclass.Argument(help="API base URL")
    method: str = argclass.Argument(
        "-X", "--method",
        default="GET",
        choices=["GET", "POST", "PUT", "DELETE", "PATCH"]
    )
    headers: list[str] = argclass.Argument(
        "-H", "--header",
        nargs="*",
        default=[],
        help="Headers in 'Key: Value' format"
    )
    data: str | None = argclass.Argument(
        "-d", "--data",
        default=None,
        help="Request body"
    )
    auth = AuthGroup()
    options = RequestOptions()

os.environ["API_TOKEN"] = "secret_token"

client = HTTPClient()
client.parse_args([
    "--base-url", "https://api.example.com",
    "-X", "POST",
    "-H", "Content-Type: application/json",
    "-d", '{"key": "value"}',
    "--options-timeout", "60"
])
client.sanitize_env()

assert client.base_url == "https://api.example.com"
assert client.method == "POST"
assert client.headers == ["Content-Type: application/json"]
assert client.data == '{"key": "value"}'
assert str(client.auth.token) == "secret_token"
assert client.options.timeout == 60
```

## Database Migration Tool

Database migration tools like Alembic, Flyway, or Django migrations use
subcommands for different operations: applying migrations, rolling back,
checking status. This example shows how to structure such a tool with
argclass.

The parent parser holds connection settings that apply to all subcommands,
while each subcommand has its own specific options. This pattern is ideal
for any tool that performs multiple related operations on a shared resource.

**Key features demonstrated:**
- Multiple subcommands (`up`, `down`, `status`)
- Shared parent options (`--database`, `--migrations`)
- Environment variable fallback with `env_var` parameter
- Optional target specification with `str | None`
- `--fake` flag for marking migrations without running them

<!--- name: test_example_migrations --->
```python
import argclass
from pathlib import Path

class MigrateUp(argclass.Parser):
    """Apply pending migrations."""
    target: str | None = argclass.Argument(
        default=None,
        help="Target migration (default: latest)"
    )
    fake: bool = argclass.Argument(
        default=False,
        action=argclass.Actions.STORE_TRUE,
        help="Mark as applied without running"
    )

    def __call__(self) -> int:
        target = self.target or "latest"
        print(f"Migrating up to {target}")
        return 0

class MigrateDown(argclass.Parser):
    """Rollback migrations."""
    steps: int = argclass.Argument(
        default=1,
        help="Number of migrations to rollback"
    )

    def __call__(self) -> int:
        print(f"Rolling back {self.steps} migration(s)")
        return 0

class MigrateStatus(argclass.Parser):
    """Show migration status."""
    def __call__(self) -> int:
        print("Showing migration status")
        return 0

class MigrateCLI(argclass.Parser):
    """Database migration tool."""
    database_url: str = argclass.Argument(
        "-d", "--database",
        env_var="DATABASE_URL",
        default="sqlite:///app.db"
    )
    migrations_dir: Path = argclass.Argument(
        "-m", "--migrations",
        default=Path("migrations")
    )
    up = MigrateUp()
    down = MigrateDown()
    status = MigrateStatus()

cli = MigrateCLI()
cli.parse_args(["--database", "postgres://localhost/app", "up", "--target", "002"])

assert cli.database_url == "postgres://localhost/app"
assert cli.up.target == "002"
```

## Daemon/Service Configuration

Long-running services like web servers, message brokers, or background
workers need extensive configuration: logging levels, metrics endpoints,
process management options. This example shows how to organize these
settings into logical groups.

The grouped approach (`LoggingGroup`, `MetricsGroup`) makes configuration
manageable and the resulting `--help` output organized by category. This
pattern works well for any application with many configuration options.

**Key features demonstrated:**
- Complex configuration with multiple groups
- Daemon-style options (`--daemonize`, `--pid-file`, `--user`)
- Logging configuration with level and format choices
- Metrics/monitoring endpoint configuration
- `Path | None` for optional file paths
- Short flags for common operations (`-D`, `-c`)

<!--- name: test_example_daemon --->
```python
import argclass
from pathlib import Path

class LoggingGroup(argclass.Group):
    """Logging configuration."""
    level: str = argclass.Argument(
        default="info",
        choices=["debug", "info", "warning", "error"]
    )
    format: str = argclass.Argument(
        default="text",
        choices=["text", "json"]
    )
    file: Path | None = None

class MetricsGroup(argclass.Group):
    """Metrics and monitoring."""
    enabled: bool = True
    port: int = 9090
    path: str = "/metrics"

class Daemon(argclass.Parser):
    """Background service daemon."""
    config: Path | None = argclass.Argument(
        "-c", "--config",
        default=None,
        help="Config file path"
    )
    pid_file: Path = argclass.Argument(
        default=Path("/var/run/myapp.pid")
    )
    daemonize: bool = argclass.Argument(
        "-D", "--daemonize",
        default=False,
        action=argclass.Actions.STORE_TRUE
    )
    user: str | None = None
    group: str | None = None
    logging = LoggingGroup()
    metrics = MetricsGroup()

daemon = Daemon()
daemon.parse_args([
    "--daemonize",
    "--logging-level", "debug",
    "--logging-file", "/var/log/myapp.log",
    "--metrics-port", "8080"
])

assert daemon.daemonize is True
assert daemon.logging.level == "debug"
assert daemon.logging.file == Path("/var/log/myapp.log")
assert daemon.metrics.port == 8080
```

## Testing Your CLI

Testing CLI parsers is straightforward because argclass parsers are just
Python classes. You can instantiate them, call `parse_args()` with test
arguments, and assert on the resulting attribute values.

| Pattern | Use Case |
|---------|----------|
| [Basic Test](#basic-test) | Simple argument parsing verification |
| [Testing with Environment](#testing-with-environment) | Environment variable handling |
| [Testing with Config Files](#testing-with-config-files) | Config file loading |
| [Testing Subcommands](#testing-subcommands) | Subcommand dispatch and arguments |
| [Testing Error Handling](#testing-error-handling) | Invalid input and validation |
| [Testing Required Arguments](#testing-required-arguments) | Missing required args |
| [Testing Groups](#testing-groups) | Argument groups with prefixes |
| [Testing Secrets](#testing-secrets) | Secret masking and sanitization |
| [Testing Priority Order](#testing-priority-order) | Config/env/CLI override behavior |

### Basic Test

The simplest test pattern: create a parser instance, parse known arguments,
and verify the results. This works for any parser and catches regressions
in argument definitions.

<!--- name: test_testing_basic --->
```python
import argclass

class Parser(argclass.Parser):
    name: str
    count: int = 1

def test_parser_defaults():
    parser = Parser()
    parser.parse_args(["--name", "test"])
    assert parser.name == "test"
    assert parser.count == 1

def test_parser_all_args():
    parser = Parser()
    parser.parse_args(["--name", "test", "--count", "5"])
    assert parser.name == "test"
    assert parser.count == 5

# Run the tests
test_parser_defaults()
test_parser_all_args()
```

### Testing with Environment

Use pytest's `monkeypatch` fixture to set environment variables for tests.
This isolates each test and ensures environment changes don't leak between
tests.

<!--- name: test_testing_env --->
```python
import os
import argclass

class Parser(argclass.Parser):
    host: str = argclass.Argument(env_var="TEST_APP_HOST", default="localhost")

# Simulate monkeypatch.setenv
os.environ["TEST_APP_HOST"] = "test-host"

parser = Parser()
parser.parse_args([])
assert parser.host == "test-host"

# Cleanup (monkeypatch does this automatically)
del os.environ["TEST_APP_HOST"]
```

### Testing with Config Files

Use pytest's `tmp_path` fixture to create temporary config files. This
ensures tests are isolated and don't depend on files in your filesystem.

<!--- name: test_testing_config --->
```python
import argclass
from tempfile import NamedTemporaryFile
from pathlib import Path

class Parser(argclass.Parser):
    port: int = 8080

# Simulate tmp_path fixture
with NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
    f.write("[DEFAULT]\nport = 9000\n")
    config_file = f.name

parser = Parser(config_files=[config_file])
parser.parse_args([])
assert parser.port == 9000

Path(config_file).unlink()
```

### Testing Subcommands

Test subcommand dispatch by parsing arguments that include the subcommand
name, then call the parser to execute the selected subcommand.

<!--- name: test_testing_subcommands --->
```python
import argclass

class Sub(argclass.Parser):
    value: int = 1
    def __call__(self): return self.value

class CLI(argclass.Parser):
    sub = Sub()

cli = CLI()
cli.parse_args(["sub", "--value", "42"])
assert cli() == 42
```

### Testing Error Handling

Test that your parser correctly rejects invalid input by catching `SystemExit`:

<!--- name: test_testing_errors --->
```python
import argclass
import sys
from io import StringIO

class Parser(argclass.Parser):
    count: int = argclass.Argument(type=int)

def test_invalid_type():
    parser = Parser()
    # Capture stderr and catch SystemExit
    old_stderr = sys.stderr
    sys.stderr = StringIO()
    try:
        parser.parse_args(["--count", "not-a-number"])
        assert False, "Should have raised SystemExit"
    except SystemExit as e:
        assert e.code == 2  # argparse uses exit code 2 for errors
    finally:
        sys.stderr = old_stderr

test_invalid_type()
```

### Testing Required Arguments

Verify that missing required arguments cause the expected error:

<!--- name: test_testing_required --->
```python
import argclass
import sys
from io import StringIO

class Parser(argclass.Parser):
    required_arg: str  # No default = required

def test_missing_required():
    parser = Parser()
    old_stderr = sys.stderr
    sys.stderr = StringIO()
    try:
        parser.parse_args([])
        assert False, "Should have raised SystemExit"
    except SystemExit as e:
        assert e.code == 2
    finally:
        sys.stderr = old_stderr

test_missing_required()
```

### Parametrized Testing

Test multiple input combinations efficiently:

<!--- name: test_testing_parametrized --->
```python
import argclass

class Parser(argclass.Parser):
    value: int = 0

# Test cases: (args, expected_value)
test_cases = [
    ([], 0),
    (["--value", "10"], 10),
    (["--value", "100"], 100),
    (["--value", "-5"], -5),
]

for args, expected in test_cases:
    parser = Parser()
    parser.parse_args(args)
    assert parser.value == expected, f"Failed for args={args}"
```

### Testing Groups

Test argument groups are correctly parsed and accessible:

<!--- name: test_testing_groups --->
```python
import argclass

class DatabaseGroup(argclass.Group):
    host: str = "localhost"
    port: int = 5432

class Parser(argclass.Parser):
    database = DatabaseGroup()

def test_group_defaults():
    parser = Parser()
    parser.parse_args([])
    assert parser.database.host == "localhost"
    assert parser.database.port == 5432

def test_group_override():
    parser = Parser()
    parser.parse_args(["--database-host", "prod.db", "--database-port", "5433"])
    assert parser.database.host == "prod.db"
    assert parser.database.port == 5433

test_group_defaults()
test_group_override()
```

### Testing Secrets

Verify secret handling and sanitization:

<!--- name: test_testing_secrets --->
```python
import os
import argclass

os.environ["TEST_SECRET"] = "supersecret"

class Parser(argclass.Parser):
    api_key: str = argclass.Secret(env_var="TEST_SECRET")

parser = Parser()
parser.parse_args([])

# Value is accessible for use
assert parser.api_key == "supersecret"

# Value is masked in repr() - safe for logging
assert "supersecret" not in repr(parser.api_key)

# Sanitize removes from environment
parser.sanitize_env()
assert "TEST_SECRET" not in os.environ
```

### Testing Priority Order

Verify config source priority (CLI > env > config > default):

<!--- name: test_testing_priority --->
```python
import os
import argclass
from tempfile import NamedTemporaryFile
from pathlib import Path

class Parser(argclass.Parser):
    value: str = argclass.Argument(env_var="TEST_PRIORITY_VALUE", default="default")

# Create config file
with NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
    f.write("[DEFAULT]\nvalue = from-config\n")
    config_file = f.name

# Test 1: Default wins when nothing else provided
parser1 = Parser()
parser1.parse_args([])
assert parser1.value == "default"

# Test 2: Config overrides default
parser2 = Parser(config_files=[config_file])
parser2.parse_args([])
assert parser2.value == "from-config"

# Test 3: Env overrides config
os.environ["TEST_PRIORITY_VALUE"] = "from-env"
parser3 = Parser(config_files=[config_file])
parser3.parse_args([])
assert parser3.value == "from-env"

# Test 4: CLI overrides everything
parser4 = Parser(config_files=[config_file])
parser4.parse_args(["--value", "from-cli"])
assert parser4.value == "from-cli"

# Cleanup
del os.environ["TEST_PRIORITY_VALUE"]
Path(config_file).unlink()
```

### Mocking External Dependencies

When your CLI calls external services, mock them in tests:

<!--- name: test_testing_mock --->
```python
import argclass

# Simulated external service
class ExternalService:
    def fetch(self, url: str) -> str:
        raise NotImplementedError("Would call real service")

class Parser(argclass.Parser):
    url: str

    def __call__(self, service: ExternalService = None) -> str:
        service = service or ExternalService()
        return service.fetch(self.url)

# Mock service for testing
class MockService(ExternalService):
    def fetch(self, url: str) -> str:
        return f"mocked response for {url}"

parser = Parser()
parser.parse_args(["--url", "https://example.com"])

# Test with mock
result = parser(service=MockService())
assert result == "mocked response for https://example.com"
```
