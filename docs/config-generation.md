# Generating Config Files

argclass can WRITE config files for a parser, the inverse of the
config-file reading covered in [Config Files](config-files.md).
Use this to scaffold sample configs for users, dump the current
parsed state for debugging, or hand a snapshot off to other tools.

## How it works

A `ConfigGenerator` walks the parser tree, builds a nested dict of
the current state, then renders it to a format-specific string.
argclass ships four generators:

| Class                  | Output  |
|------------------------|---------|
| `INIConfigGenerator`   | INI     |
| `JSONConfigGenerator`  | JSON    |
| `TOMLConfigGenerator`  | TOML    |
| `EnvConfigGenerator`   | `.env`  |

All inherit the same walking + Action wiring; subclasses only
override `render(data, help_map)` (or `dump_to_string(parser)` for
formats that need extra metadata such as env var names).

## Basic usage

<!--- name: test_config_gen_basic --->
```python
import argclass

class Database(argclass.Group):
    host: str = "localhost"
    port: int = 5432

class CLI(argclass.Parser):
    debug: bool = False
    name: str = argclass.Argument(default="app", help="App name")
    db: Database = Database()

parser = CLI()
ini_text = argclass.INIConfigGenerator().dump_to_string(parser)
assert "[DEFAULT]" in ini_text
assert "name = app" in ini_text
assert "[db]" in ini_text
assert "host = localhost" in ini_text
```

## Writing to a file (or stdout)

`dump(parser, dest)` accepts a path, a file-like object, or `"-"`
for stdout:

<!--- name: test_config_gen_dump_file --->
```python
import argclass
from pathlib import Path
from tempfile import NamedTemporaryFile

class CLI(argclass.Parser):
    host: str = "localhost"
    port: int = 8080

with NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
    config_path = f.name

argclass.TOMLConfigGenerator().dump(CLI(), config_path)

# Read it back
loaded = CLI(
    config_files=[config_path],
    config_parser_class=argclass.TOMLDefaultsParser,
)
loaded.parse_args([])
assert loaded.host == "localhost"
assert loaded.port == 8080

Path(config_path).unlink()
```

## The `--generate-config` flag

argclass ships `GenerateConfigAction` — an argparse Action that lets
users dump a config from your CLI:

```python
import argclass

class CLI(argclass.Parser):
    host: str = "localhost"
    port: int = 8080
    generate = argclass.Argument(
        "--generate-config",
        action=argclass.GenerateConfigAction,
        generator=argclass.INIConfigGenerator,
        metavar="FILE",
    )
```

End users run:

```
myapp --generate-config /etc/myapp.ini   # write a file
myapp --generate-config -                # print to stdout
```

The action writes the file (or stdout), then exits with status 0.

You can also pass a generator INSTANCE instead of a class — useful
if your generator needs constructor arguments:

```python
generator=argclass.JSONConfigGenerator()
```

## Sources reflected in the dump

The generator reads the parser's CURRENT state. Whatever argclass
resolved at the moment of dumping is what gets written — defaults,
config-file values, env vars, or CLI overrides. The usual priority
order (`defaults < config < env < CLI`) is preserved, so dumping
after `parse_args` gives you a full snapshot.

<!--- name: test_config_gen_cli_in_dump --->
```python
import argclass

class CLI(argclass.Parser):
    host: str = "localhost"
    port: int = 8080

parser = CLI()
parser.parse_args(["--host", "10.0.0.1", "--port", "9090"])

text = argclass.INIConfigGenerator().dump_to_string(parser)
assert "host = 10.0.0.1" in text
assert "port = 9090" in text
```

## Generating env-var listings

`EnvConfigGenerator` emits a `.env`-style listing — one
`KEY=value` line per argument, using the env var name argclass
would read (explicit `env_var=` or computed from
`auto_env_var_prefix=`). Arguments without a resolvable env var are
skipped — set `auto_env_var_prefix=` on the parser to get full
coverage.

<!--- name: test_config_gen_env --->
```python
import argclass

class Database(argclass.Group):
    host: str = "localhost"
    port: int = 5432

class CLI(argclass.Parser):
    debug: bool = False
    db: Database = Database()

parser = CLI(auto_env_var_prefix="APP_")
text = argclass.EnvConfigGenerator().dump_to_string(parser)
assert "APP_DEBUG=false" in text
assert "APP_DB_HOST=localhost" in text
assert "APP_DB_PORT=5432" in text
```

Lists are emitted as Python literal syntax so argclass can read them
back via `ast.literal_eval`:

```
APP_TAGS=['alpha', 'beta', 'gamma']
```

Strings are quoted only when they contain whitespace, `=`, `#`, or
other characters that would confuse a typical `.env` parser.

## Excluding arguments from dumps

Some arguments make no sense in a config file — `--version`,
`--generate-config` itself, `--check-updates`, anything else that
"fires and exits". Mark such actions with `NonConfigAction`:

<!--- name: test_config_gen_non_config_action --->
```python
import argparse
import argclass

class PingAction(argclass.NonConfigAction):
    def __init__(self, option_strings, dest, **kw):
        kw.setdefault("nargs", 0)
        kw.setdefault("default", argparse.SUPPRESS)
        super().__init__(option_strings, dest, **kw)

    def __call__(self, parser, namespace, values, option_string=None):
        parser.exit(0, "pong\n")

class CLI(argclass.Parser):
    host: str = "localhost"
    ping = argclass.Argument(action=PingAction)

text = argclass.INIConfigGenerator().dump_to_string(CLI())
assert "host = localhost" in text
assert "ping" not in text
```

argparse's built-in `--help` and `--version` actions are recognised
and skipped automatically. Custom actions opt out via the marker
class (or by setting `__emit_config__ = False` directly).

## Custom formats

Subclass `ConfigGenerator` and override `render`:

<!--- name: test_config_gen_custom --->
```python
import argclass
from typing import Any, Dict, Optional
from argclass.emit import HelpMap

class KeyValueGenerator(argclass.ConfigGenerator):
    """Flat KEY=VALUE format with dotted paths for nested groups."""

    extension = ".kv"

    def render(
        self,
        data: Dict[str, Any],
        help_map: Optional[HelpMap] = None,
    ) -> str:
        lines = []
        self._walk(data, (), lines)
        return "\n".join(lines) + "\n"

    def _walk(self, data, path, lines):
        for key, value in data.items():
            if isinstance(value, dict):
                self._walk(value, path + (key,), lines)
            else:
                lines.append(f"{'.'.join(path + (key,))}={value}")

class CLI(argclass.Parser):
    host: str = "localhost"
    port: int = 8080

text = KeyValueGenerator().dump_to_string(CLI())
assert "host=localhost" in text
assert "port=8080" in text
```

For formats that need extra metadata (like env var names), override
`dump_to_string(parser)` directly — `EnvConfigGenerator` is the
reference example.

## Security note

Generators emit values as-is, including those marked
[`Secret()`](secrets.md). A dumped config can therefore contain
credentials. Treat the output file like any credential-bearing file:

- Set restrictive permissions when writing to disk.
- Avoid dumping to shared locations or sending to stdout in
  contexts where logs may be captured.
- Prefer the `EnvConfigGenerator` form when you want to record
  config in a way that's easy to load via a secret-manager wrapper.

## Limitations

- **Subparsers are skipped.** Subparsers represent runtime branches,
  not config-time state. Mixing them into one file blurs the model.
  Each subparser can be dumped separately by passing the subparser
  instance to the generator.
- **JSON has no comments.** Help text is dropped in JSON output;
  INI, TOML, and `.env` formats include it.
- **TOML is emitted by a minimal hand-rolled writer.** It covers
  the types argclass supports (`str`, `int`, `float`, `bool`,
  `list`, `None`). Exotic values fall back to `str()`.
