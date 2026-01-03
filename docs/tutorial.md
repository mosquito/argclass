# Tutorial

This tutorial walks through building a complete CLI application with argclass.

## Building a File Backup Tool

We'll build a backup utility that demonstrates all major argclass features.

### Basic Structure

Start with a simple parser:

<!--- name: test_tutorial_basic --->
```python
import argclass
from pathlib import Path

class BackupTool(argclass.Parser):
    """Backup files to a destination directory."""
    source: Path
    destination: Path

backup = BackupTool()
backup.parse_args(["--source", "/data", "--destination", "/backup"])

assert backup.source == Path("/data")
assert backup.destination == Path("/backup")
```

### Adding Options

Add optional arguments with defaults:

<!--- name: test_tutorial_options --->
```python
import argclass
from pathlib import Path

class BackupTool(argclass.Parser):
    """Backup files to a destination directory."""
    source: Path
    destination: Path
    compress: bool = False
    verbose: bool = False
    max_size: int = 100  # MB

backup = BackupTool()
backup.parse_args([
    "--source", "/data",
    "--destination", "/backup",
    "--compress",
    "--max-size", "500"
])

assert backup.source == Path("/data")
assert backup.compress is True
assert backup.max_size == 500
```

Note: `bool = False` is a shortcut that creates a flag-style argument (using
`action="store_true"` internally). The flag `--compress` sets the value to `True`.

### Help Text and Aliases

Make the CLI user-friendly.

**Important:** When using `argclass.Argument()` for booleans, you must explicitly
specify the `action` parameter. Without it, the argument would expect a value
like `--compress true` instead of working as a flag:

<!--- name: test_tutorial_help_aliases --->
```python
import argclass
from pathlib import Path

class BackupTool(argclass.Parser):
    """Backup files to a destination directory."""
    source: Path = argclass.Argument(help="Source directory to backup")
    destination: Path = argclass.Argument(
        "-d", "--destination",
        help="Destination directory"
    )
    compress: bool = argclass.Argument(
        "-c", "--compress",
        default=False,
        action=argclass.Actions.STORE_TRUE,
        help="Compress backup files"
    )
    verbose: bool = argclass.Argument(
        "-v", "--verbose",
        default=False,
        action=argclass.Actions.STORE_TRUE,
        help="Enable verbose output"
    )

backup = BackupTool()
backup.parse_args(["--source", "/data", "-d", "/backup", "-c", "-v"])

assert backup.source == Path("/data")
assert backup.destination == Path("/backup")
assert backup.compress is True
assert backup.verbose is True
```

### Using Argument Groups

Organize related options into groups:

<!--- name: test_tutorial_groups --->
```python
import argclass
from pathlib import Path

class CompressionOptions(argclass.Group):
    """Compression settings."""
    enabled: bool = False
    level: int = argclass.Argument(default=6, help="Compression level (1-9)")
    format: str = argclass.Argument(
        default="gzip",
        choices=["gzip", "bzip2", "lzma"],
        help="Compression format"
    )

class BackupTool(argclass.Parser):
    """Backup files to a destination directory."""
    source: Path
    destination: Path
    verbose: bool = False
    compression = CompressionOptions()

backup = BackupTool()
backup.parse_args([
    "--source", "/data",
    "--destination", "/backup",
    "--compression-enabled",
    "--compression-level", "9",
    "--compression-format", "lzma"
])

assert backup.source == Path("/data")
assert backup.compression.enabled is True
assert backup.compression.level == 9
assert backup.compression.format == "lzma"
```

### Adding Subcommands

Create a multi-command CLI:

<!--- name: test_tutorial_subcommands --->
```python
import argclass
from pathlib import Path

class BackupCommand(argclass.Parser):
    """Create a new backup."""
    source: Path
    destination: Path
    compress: bool = False

    def __call__(self) -> int:
        return 0

class RestoreCommand(argclass.Parser):
    """Restore from a backup."""
    backup: Path
    destination: Path
    overwrite: bool = False

    def __call__(self) -> int:
        return 0

class BackupTool(argclass.Parser):
    """Backup management tool."""
    verbose: bool = False
    backup = BackupCommand()
    restore = RestoreCommand()

tool = BackupTool()
tool.parse_args(["backup", "--source", "/data", "--destination", "/backup", "--compress"])

assert tool.verbose is False
assert tool.backup.source == Path("/data")
assert tool.backup.destination == Path("/backup")
assert tool.backup.compress is True
assert tool() == 0
```

### Configuration Files

Load defaults from a config file:

<!--- name: test_tutorial_config_file --->
```python
import argclass
from pathlib import Path
from tempfile import NamedTemporaryFile

class BackupTool(argclass.Parser):
    source: Path | None = None
    destination: Path | None = None
    compress: bool = False
    max_size: int = 100

# Create a temporary config file
with NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
    f.write("[DEFAULT]\n")
    f.write("destination = /backup\n")
    f.write("compress = true\n")
    f.write("max_size = 500\n")
    config_path = f.name

tool = BackupTool(config_files=[config_path])
tool.parse_args([])

assert tool.destination == Path("/backup")
assert tool.compress is True
assert tool.max_size == 500

# Cleanup
Path(config_path).unlink()
```

### Environment Variables

Add environment variable support:

<!--- name: test_tutorial_env_vars --->
```python
import os
import argclass
from pathlib import Path

os.environ["BACKUP_DESTINATION"] = "/backup"
os.environ["BACKUP_COMPRESS"] = "true"

class BackupTool(argclass.Parser):
    source: Path | None = None
    destination: Path = argclass.Argument(
        env_var="BACKUP_DESTINATION",
        default=Path("/default")
    )
    compress: bool = argclass.Argument(
        env_var="BACKUP_COMPRESS",
        default=False
    )

tool = BackupTool()
tool.parse_args([])

assert tool.destination == Path("/backup")
assert tool.compress is True

# Cleanup
del os.environ["BACKUP_DESTINATION"]
del os.environ["BACKUP_COMPRESS"]
```

### Complete Example

Here's a complete backup tool:

<!--- name: test_tutorial_complete --->
```python
import argclass
from pathlib import Path

class CompressionGroup(argclass.Group):
    enabled: bool = False
    level: int = 6
    format: str = argclass.Argument(
        default="gzip",
        choices=["gzip", "bzip2", "lzma"]
    )

class BackupCommand(argclass.Parser):
    """Create a new backup."""
    source: Path = argclass.Argument(help="Source directory")
    destination: Path = argclass.Argument(help="Destination directory")
    exclude: list[str] = argclass.Argument(
        nargs="*",
        default=[],
        help="Patterns to exclude"
    )
    compression = CompressionGroup()

    def __call__(self) -> int:
        return 0

class RestoreCommand(argclass.Parser):
    """Restore from a backup."""
    backup: Path = argclass.Argument(help="Backup file to restore")
    destination: Path = argclass.Argument(help="Restore destination")
    overwrite: bool = False

    def __call__(self) -> int:
        return 0

class BackupTool(argclass.Parser):
    """Backup management tool."""
    verbose: bool = False
    backup = BackupCommand()
    restore = RestoreCommand()

tool = BackupTool()
tool.parse_args([
    "--verbose",
    "backup",
    "--source", "/data",
    "--destination", "/backup",
    "--exclude", "*.tmp", "*.log",
    "--compression-enabled",
    "--compression-level", "9"
])

assert tool.verbose is True
assert tool.backup.source == Path("/data")
assert tool.backup.destination == Path("/backup")
assert tool.backup.exclude == ["*.tmp", "*.log"]
assert tool.backup.compression.enabled is True
assert tool.backup.compression.level == 9
assert tool() == 0
```

## Next Steps

- [Arguments](arguments.md) - All argument options
- [Groups](groups.md) - Organizing arguments
- [Subparsers](subparsers.md) - Multi-command CLIs
- [Config Files](config-files.md) - Configuration file formats
