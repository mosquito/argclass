# Examples Gallery

Copy-pastable examples for common CLI patterns.

## Simple CLI Tool

A minimal CLI with options and flags:

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

Multi-command CLI like git or docker:

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

Full configuration with all three sources:

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

## File Processing Tool

CLI for batch file operations:

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

API client with authentication:

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

Multi-subcommand with shared options:

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

Long-running service with extensive config:

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

### Basic Test

```python
import pytest
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
```

### Testing with Environment

```python
def test_with_env(monkeypatch):
    monkeypatch.setenv("APP_HOST", "test-host")

    class Parser(argclass.Parser):
        host: str = argclass.Argument(env_var="APP_HOST", default="localhost")

    parser = Parser()
    parser.parse_args([])
    assert parser.host == "test-host"
```

### Testing with Config Files

```python
def test_with_config(tmp_path):
    config_file = tmp_path / "config.ini"
    config_file.write_text("[DEFAULT]\nport = 9000\n")

    class Parser(argclass.Parser):
        port: int = 8080

    parser = Parser(config_files=[str(config_file)])
    parser.parse_args([])
    assert parser.port == 9000
```

### Testing Subcommands

```python
def test_subcommand():
    class Sub(argclass.Parser):
        value: int = 1
        def __call__(self): return self.value

    class CLI(argclass.Parser):
        sub = Sub()

    cli = CLI()
    cli.parse_args(["sub", "--value", "42"])
    assert cli() == 42
```
