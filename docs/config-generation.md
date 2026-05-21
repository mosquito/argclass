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

This makes config generation useful for more than just scaffolding
defaults — you can also use it to:

- **Convert between formats.** Load an existing INI, dump as TOML.
- **Snapshot a deployed configuration.** After `parse_args`, dump to
  inspect what the parser actually resolved (defaults plus
  config file plus env vars plus CLI).
- **Materialise env-based config to a file.** Run the parser with
  env vars set, dump as INI/TOML/JSON, commit the file.

### Including CLI values

CLI arguments parsed by `parse_args` end up in the dump. After parse,
the parser's attributes carry the resolved values; dumping just reads
them out.

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

When `--generate-config` is invoked via `GenerateConfigAction`, the
action also captures CLI arguments that argparse has already
processed at that point in the command line — order matters. Put
overrides BEFORE the generation flag to make sure they reach the
dump.

### Including existing config-file values

A parser configured with `config_files=` loads those values during
`parse_args`. Dump after parse and the source config-file values
appear in the output, which makes converting between formats
trivial:

<!--- name: test_config_gen_format_conversion --->
```python
import argclass
from pathlib import Path
from tempfile import NamedTemporaryFile

class CLI(argclass.Parser):
    host: str = "localhost"
    port: int = 8080

# Pretend the user already ships an INI; convert it to TOML.
with NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
    f.write("[DEFAULT]\nhost = prod.example.com\nport = 9000\n")
    src = f.name

parser = CLI(config_files=[src])
parser.parse_args([])
toml_text = argclass.TOMLConfigGenerator().dump_to_string(parser)

assert 'host = "prod.example.com"' in toml_text
assert "port = 9000" in toml_text

Path(src).unlink()
```

### Including environment variables

When `auto_env_var_prefix=` is set on the parser (or arguments
declare explicit `env_var=`), values from `os.environ` are resolved
just like config or CLI values, and they land in the dump too.

<!--- name: test_config_gen_env_in_dump --->
```python
import os
import argclass

os.environ["APP_HOST"] = "from-env.example.com"
os.environ["APP_PORT"] = "9999"

class CLI(argclass.Parser):
    host: str = "localhost"
    port: int = 8080

parser = CLI(auto_env_var_prefix="APP_")
parser.parse_args([])

ini = argclass.INIConfigGenerator().dump_to_string(parser)
assert "host = from-env.example.com" in ini
assert "port = 9999" in ini

del os.environ["APP_HOST"]
del os.environ["APP_PORT"]
```

The same env-aware behaviour kicks in when the dump runs from
`GenerateConfigAction` mid-parse (i.e. when the user passes
`--generate-config -` on the command line). `os.environ` is consulted
directly at dump time, so you don't need to call `parse_args([])`
first.

## Migrating between config formats

A common need: an app already ships an INI config and you want to
move to TOML (or JSON, or `.env`). Because the same parser class
reads with `AbstractDefaultsParser` and writes with
`ConfigGenerator`, conversion is "load with reader X, dump with
generator Y". The values flow through your typed schema, so the
result is structurally identical even if the syntax changes.

Three ways to do it, depending on context.

### One-shot script (recommended for migration)

Write a small Python script that uses your real parser class. This
catches schema mismatches — if a key in the source config has no
corresponding argument, you'll see it (it's dropped from the dump).

<!--- name: test_config_gen_migrate_oneshot --->
```python
import argclass
from pathlib import Path
from tempfile import NamedTemporaryFile

class Database(argclass.Group):
    host: str = "localhost"
    port: int = 5432

class App(argclass.Parser):
    debug: bool = False
    name: str = "myapp"
    db: Database = Database()

# Existing INI (in real life: shipped with the app).
with NamedTemporaryFile(mode="w", suffix=".ini", delete=False) as f:
    f.write(
        "[DEFAULT]\n"
        "debug = true\n"
        "name = prod\n"
        "\n"
        "[db]\n"
        "host = db.prod.example.com\n"
        "port = 6432\n",
    )
    ini_path = f.name

# Load the existing INI through the same parser class.
parser = App(config_files=[ini_path])
parser.parse_args([])

# Dump as TOML.
toml_path = Path(ini_path).with_suffix(".toml")
argclass.TOMLConfigGenerator().dump(parser, str(toml_path))

# Sanity-check: read the new TOML back through the same parser
# and confirm we got the same resolved state.
reloaded = App(
    config_files=[str(toml_path)],
    config_parser_class=argclass.TOMLDefaultsParser,
)
reloaded.parse_args([])
assert reloaded.debug is True
assert reloaded.name == "prod"
assert reloaded.db.host == "db.prod.example.com"
assert reloaded.db.port == 6432

Path(ini_path).unlink()
toml_path.unlink()
```

This approach is the one to ship in a release note ("run
`python -m myapp.migrate config.ini`") — users get a deterministic,
schema-validated conversion. Add a `--dry-run` flag that prints to
stdout instead of writing if you want to be polite.

### Mid-flight conversion via `--generate-config`

If your app already wires `GenerateConfigAction` (see the
"`--generate-config` flag" section above) and reads `config_files=`,
users can convert in a single command without any extra script:

```
# Read the old INI, write the new TOML, exit.
myapp --config /etc/myapp.ini --generate-toml /etc/myapp.toml

# Inspect first by streaming to stdout.
myapp --config /etc/myapp.ini --generate-toml -
```

The Action runs after argparse has applied env vars and
config-file values to the namespace, so the dump captures the
full resolved state — including any CLI overrides the user typed
before `--generate-toml`.

### Bulk conversion with `tmp_path` / pipelines

For converting many files (e.g. as part of a release migration
script), wrap the one-shot pattern in a loop. Stream straight to
the target file with `dump(parser, dest)` to keep memory flat:

```python
import argclass
from pathlib import Path

for src in Path("configs").glob("*.ini"):
    parser = App(config_files=[src])
    parser.parse_args([])
    dst = src.with_suffix(".toml")
    argclass.TOMLConfigGenerator().dump(parser, str(dst))
```

### Choosing the target format

| If you want…                         | Pick                  |
|--------------------------------------|-----------------------|
| Comments + nested sections           | TOML                  |
| Stdlib-only, simplest legacy fit     | INI                   |
| Programmatic post-processing         | JSON                  |
| `.env` for Docker / systemd / CI     | `EnvConfigGenerator`  |

Notes:

- JSON has no comments — your help text will be lost. INI, TOML,
  and `.env` preserve it as `;`/`#` comment lines.
- Secrets are emitted as plain values (see the "Security note"
  section below). When converting, write the new file
  with restrictive permissions and delete the source if it
  contained credentials.
- Subparsers aren't included in the dump. If your CLI has
  subcommands with their own config-relevant args, dump each
  subparser separately (pass the subparser instance to the
  generator).

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
"fires and exits". argclass needs to know about them so they stay
out of generated configs.

argparse's built-in `--help` and `--version` actions are recognised
and skipped automatically. For your own custom `argparse.Action`
subclasses, pick one of two equivalent opt-outs:

### Option 1 — inherit from `argclass.NonConfigAction`

The cleanest choice if you're writing a new action from scratch.
`NonConfigAction` is a thin `argparse.Action` subclass that just
sets the `__emit_config__ = False` marker for you, and it keeps
intent visible at the class declaration:

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

### Option 2 — set `__emit_config__ = False` on an existing action

Useful when you already inherit from something else (a third-party
`argparse.Action` subclass, your own base, etc.) and would rather not
add another base class. The marker is just a class attribute:

<!--- name: test_config_gen_marker_attribute --->
```python
import argparse
import argclass

class PingAction(argparse.Action):
    __emit_config__ = False   # opt out, equivalent to NonConfigAction

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
assert "ping" not in text
```

Both forms are honoured by the generator the same way — pick
whichever fits your inheritance chain. If you forget both, your
action will end up in dumps as an empty value, which is what tells
you to opt out.

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
