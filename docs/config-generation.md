# Generating Config Files

argclass can WRITE config files for a parser — the symmetric inverse
of the [config-file reading](config-files.md) covered elsewhere. The
expected end-user workflow is "run the app with a flag and get a
config file out"; everything else (programmatic dumps, custom
formats) builds on that.

## Add `--generate-config` to your CLI

Most users only need this:

```python
import argclass

class CLI(argclass.Parser):
    host: str = "localhost"
    port: int = 8080
    generate_config = argclass.Argument(
        action=argclass.GenerateConfigAction,
        generator=argclass.INIConfigGenerator,
        metavar="FILE",
    )
```

The attribute name `generate_config` auto-derives `--generate-config`;
end users then run:

```
myapp --generate-config /etc/myapp.ini   # write a file
myapp --generate-config -                # print to stdout
```

The action writes the file (or stdout) and exits with status 0.

If you want to ship multiple formats, declare one attribute per
generator — the flag names follow the attribute names:

```python
class CLI(argclass.Parser):
    host: str = "localhost"

    generate_ini  = argclass.Argument(
        action=argclass.GenerateConfigAction,
        generator=argclass.INIConfigGenerator,
        metavar="FILE",
    )
    generate_toml = argclass.Argument(
        action=argclass.GenerateConfigAction,
        generator=argclass.TOMLConfigGenerator,
        metavar="FILE",
    )
    generate_env  = argclass.Argument(
        action=argclass.GenerateConfigAction,
        generator=argclass.EnvConfigGenerator,
        metavar="FILE",
    )
```

This is exactly the pattern the interactive demo uses; try it with:

```
python -m argclass genconfig --generate-ini -
python -m argclass genconfig --generate-toml -
DEMO_HOST=prod python -m argclass genconfig --generate-env -
```

## Picking a format

| Generator                | Output  | Help comments | Pick when…                                  |
|--------------------------|---------|---------------|---------------------------------------------|
| `INIConfigGenerator`     | INI     | `; ...`       | legacy ecosystems, stdlib-only stack        |
| `TOMLConfigGenerator`    | TOML    | `# ...`       | comments + nested sections, modern default  |
| `JSONConfigGenerator`    | JSON    | (dropped)     | machine consumption / pipelines             |
| `EnvConfigGenerator`     | `.env`  | `# ...`       | Docker, systemd, CI, secret managers        |

All four are interchangeable from the user's perspective — switch
`generator=...` and rerun.

(defaults-are-commented)=
## Defaults are commented — the output is a template

For the comment-aware formats (INI, TOML, `.env`) the generated file
reads like a config a human would hand-write. Every argument still
sitting at its **declared default** is written **commented-out**, with
its help text as a comment above it, and a blank line between entries.
Only the values you actually changed (via CLI, env, or a loaded config
file) come out active. So a fresh dump documents every knob and its
default without turning any of them on.

INI uses two comment markers so the help prose and a disabled value
never blur together — help is `;`, a commented-out default is `#`
(configparser treats both as comments, so either round-trips):

```ini
[DEFAULT]
; Enable debug logging
# debug = false

; Application name
# name = app

[db]
; Database host
# host = localhost

; Database port
# port = 5432
```

TOML and `.env` have a single comment character, so both kinds use `#`:

```toml
# Enable debug logging
# debug = false

# Application name
# name = "app"
```

Override something and it flips to an active line, while the untouched
neighbours stay commented for reference:

<!--- name: test_config_gen_template --->
```python
import argclass

class CLI(argclass.Parser):
    host: str = argclass.Argument(default="localhost", help="Server host")
    port: int = argclass.Argument(default=8080, help="Server port")

parser = CLI()
parser.parse_args(["--port=9090"])          # change only the port

ini = argclass.INIConfigGenerator().dump_to_string(parser)

# host untouched → commented reference line ('#' for a disabled value,
# ';' would be its help prose)
assert "# host = localhost" in ini
# port overridden → active
assert "\nport = 9090" in ini
assert "# port = 9090" not in ini
```

This makes generated files safe to ship as `config.example.ini`: a
reader sees the full set of options and their defaults, and only the
lines someone deliberately set are live.

Want a full snapshot instead — every field active, defaults included?
Pass `comment_defaults=False` to the generator:

<!--- name: test_config_gen_no_comment_defaults --->
```python
import argclass

class CLI(argclass.Parser):
    host: str = "localhost"
    port: int = 8080

ini = argclass.INIConfigGenerator(
    comment_defaults=False,
).dump_to_string(CLI())

assert "host = localhost" in ini
assert "; host = localhost" not in ini
```

JSON has no comment syntax, so `JSONConfigGenerator` always emits every
field and ignores `comment_defaults`.

## What lands in the dump

The dump reflects the parser's CURRENT resolved state at the moment
`--generate-config` fires. argclass's usual priority applies
(`defaults < config files < env vars < CLI args`), so all four
sources can shape the output.

:::{seealso}
Why generation follows the same priority chain as reading, and how that makes a
parser a format converter:
[The configuration model → The same chain shapes generated config](explanation/configuration-model.md#the-same-chain-shapes-generated-config).
:::

### CLI flags

CLI args parsed BEFORE `--generate-config` end up in the dump
(argparse processes flags left-to-right; the action exits before
later flags are seen):

```
myapp --host=10.0.0.1 --port=9090 --generate-config -
```

produces a config with `host = 10.0.0.1` and `port = 9090`. Putting
`--generate-config` last is the safe convention.

### Environment variables

When the parser uses `auto_env_var_prefix=` (or arguments declare
explicit `env_var=`), values from `os.environ` reach the dump too:

```
APP_HOST=prod.example.com APP_PORT=9999 myapp --generate-config -
```

writes `host = prod.example.com`, `port = 9999`.

### Config-file defaults

A parser instantiated with `config_files=[…]` loads those values
during `parse_args`. Whatever the file contained ends up in the
dump alongside any CLI overrides. This is the building block for
**format conversion** (next section).

## Converting between config formats

Format conversion happens through your own parser class — load
through reader X, dump through generator Y. There's no built-in
`--config` flag in argclass that loads a config file, so this is
best expressed as a small script (or a `__main__` entry point):

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

# Existing INI (shipped with the app in real life).
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

# Load through the same parser class.
parser = App(config_files=[ini_path])
parser.parse_args([])

# Dump as TOML.
toml_path = Path(ini_path).with_suffix(".toml")
argclass.TOMLConfigGenerator().dump(parser, toml_path)

# Round-trip check: reload the TOML, confirm the same state.
reloaded = App(
    config_files=[toml_path],
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

Bulk conversion is the same in a loop:

```python
import argclass
from pathlib import Path

for src in Path("configs").glob("*.ini"):
    parser = App(config_files=[src])
    parser.parse_args([])
    dst = src.with_suffix(".toml")
    argclass.TOMLConfigGenerator().dump(parser, dst)
```

The conversion is **schema-validated**: keys in the source that have
no corresponding argument in the parser are silently dropped from
the output, and missing keys fall back to argument defaults. That's
usually what you want for a migration script — anything weird in
the source surfaces as a missing field in the dump.

## Generating env-var listings

`EnvConfigGenerator` emits one `KEY=value` line per argument, using
the env var name argclass would read (explicit `env_var=` or computed
from `auto_env_var_prefix=`). Arguments without a resolvable env var
are skipped — set `auto_env_var_prefix=` on the parser to cover
everything. As with the other comment-aware formats, entries still at
their default come out commented-out (see [Defaults are
commented](#defaults-are-commented)); the
example below reads them as substrings, so it matches whether a line is
active or a `# `-prefixed reference.

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

Lists serialise to Python literal syntax so argclass can
`ast.literal_eval` them on read:

```
APP_TAGS=['alpha', 'beta', 'gamma']
```

Strings get quoted only when they contain whitespace, `=`, `#`,
control chars, or other shell-significant characters; newlines and
tabs are escaped (`\n`, `\t`) so each entry stays on one line.

## Excluding arguments from dumps

Some arguments make no sense in a config file — `--version`,
`--generate-config` itself, `--check-updates`, anything else that
"fires and exits". argclass needs to know about them so they stay
out of generated configs.

argparse's built-in `--help` and `--version` actions are recognised
and skipped automatically. For your own custom `argparse.Action`
subclasses, pick one of two equivalent opt-outs:

### Option 1 — inherit from `argclass.NonConfigAction`

The cleanest choice for a new action. `NonConfigAction` sets
`__emit_config__ = False` for you and keeps intent visible at the
class declaration:

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

Useful when you already inherit from a third-party `argparse.Action`
and would rather not add another base class:

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

Both forms are honoured the same way. If you forget both, the
action shows up in dumps as an empty value — that's the smell test
that tells you to opt out.

## Dumping from code

The CLI-level `--generate-config` flag is the right entry point for
end users. If you're writing tests, a migration script, or a hook
that uses the generators directly, use `dump_to_string(parser)` or
`dump(parser, dest)`:

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

`dump(parser, dest)` accepts a path (`str` or `pathlib.Path`), a
file-like object, or the string `"-"` for stdout:

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

loaded = CLI(
    config_files=[config_path],
    config_parser_class=argclass.TOMLDefaultsParser,
)
loaded.parse_args([])
assert loaded.host == "localhost"
assert loaded.port == 8080

Path(config_path).unlink()
```

You can also pass a generator INSTANCE instead of a class when you
need to construct it with extra arguments (e.g.
`generator=argclass.JSONConfigGenerator()`).

## Custom formats

A `ConfigGenerator` walks the parser tree once and yields
`ConfigField` records (one per leaf argument) containing the
current value, attribute path, help text, and env var metadata.
Subclasses consume that stream and produce text — that's the only
thing you need to override:

<!--- name: test_config_gen_custom --->
```python
import argclass
from typing import Sequence

class KeyValueGenerator(argclass.ConfigGenerator):
    """Flat KEY=VALUE format with dotted paths for nested groups."""

    extension = ".kv"

    def render(self, fields: Sequence[argclass.ConfigField]) -> str:
        lines = []
        for field in fields:
            if field.value is None:
                continue
            key = ".".join(field.attr_path)
            lines.append(f"{key}={field.value}")
        return "\n".join(lines) + "\n"

class CLI(argclass.Parser):
    host: str = "localhost"
    port: int = 8080

text = KeyValueGenerator().dump_to_string(CLI())
assert "host=localhost" in text
assert "port=8080" in text
```

Field records already carry env var names, so even `.env`-style
formats are typically a one-method override. See
`argclass.ConfigField` in the [API reference](api.md) for the full
record shape.

## Security note

Generators emit values as-is, including those marked
[`Secret()`](secrets.md). A dumped config can therefore contain
credentials. Treat the output file like any credential-bearing file:

- Set restrictive permissions when writing to disk.
- Avoid dumping to shared locations or to stdout in contexts where
  logs may be captured.
- Prefer `EnvConfigGenerator` when you want to record config in a
  way that's easy to load via a secret-manager wrapper.

## Limitations

- **Subparsers are skipped.** They represent runtime branches, not
  config-time state. Dump each subparser separately by passing its
  instance to the generator.
- **JSON has no comments.** Help text is dropped in JSON output;
  INI, TOML, and `.env` formats include it.
- **Mid-parse ordering.** CLI flags appearing AFTER
  `--generate-config` are not reflected in the dump — argparse
  invokes the action synchronously and the action exits. Put
  overrides before the generation flag.
- **TOML is emitted by a minimal hand-rolled writer.** It covers
  the types argclass supports (`str`, `int`, `float`, `bool`,
  `list`, `None`). Exotic values fall back to `str()`.
