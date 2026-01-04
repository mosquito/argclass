# Common Pitfalls

Quick reference for common mistakes and their solutions.

---

## Boolean Flags

| Syntax | Behavior |
|--------|----------|
| `flag: bool = False` | `--flag` sets to `True` (recommended) |
| `flag: bool = True` | `--flag` sets to `False` (toggles) |
| `Argument(default=False)` without action | Expects value like `--flag true` (wrong) |
| `Argument(default=False, action=Actions.STORE_TRUE)` | Works as flag |

**Rule:** Use simple `bool = False` syntax. Avoid `Argument()` for booleans unless you need extra options.

<!--- name: test_pitfall_bool_true --->
```python
import argclass

class Parser(argclass.Parser):
    feature: bool = True  # --feature toggles to False

parser = Parser()
parser.parse_args(["--feature"])
assert parser.feature is False
```

---

## Environment Variables

| Issue | Solution |
|-------|----------|
| Boolean strings | See table below (case-insensitive) |
| Spaces preserved | Trim in application logic: `value.strip()` |
| Type errors | Same rules as CLI — invalid values exit with code 2 |

### Boolean String Parsing

| Parsed as `True` | Parsed as `False` |
|------------------|-------------------|
| `1`, `y`, `yes`, `t`, `true` | Everything else |
| `on`, `enable`, `enabled` | `0`, `n`, `no`, `f`, `false`, `off`, `disable`, etc. |

<!--- name: test_pitfall_env_bool --->
```python
import os
import argclass

os.environ["TEST_FLAG"] = "yes"  # Also: true, 1, on, enable

class Parser(argclass.Parser):
    flag: bool = argclass.Argument(env_var="TEST_FLAG", default=False)

parser = Parser()
parser.parse_args([])
assert parser.flag is True

del os.environ["TEST_FLAG"]
```

<!--- name: test_pitfall_env_bool_false --->
```python
import os
import argclass

os.environ["TEST_FLAG"] = "no"  # Also: false, 0, off, disable, or any other string

class Parser(argclass.Parser):
    flag: bool = argclass.Argument(env_var="TEST_FLAG", default=False)

parser = Parser()
parser.parse_args([])
assert parser.flag is False

os.environ.pop("TEST_FLAG", None)
```

---

## Lists

| Issue | Solution |
|-------|----------|
| `--files` without values errors | Use `nargs="*"` for zero-or-more |
| Comma-separated values | CLI uses spaces: `--files a.txt b.txt` |
| Default `[]` with `nargs="+"` | Requires at least one value when flag is used |

<!--- name: test_pitfall_list_nargs --->
```python
import argclass

class Parser(argclass.Parser):
    files: list[str] = argclass.Argument(nargs="*", default=[])

parser = Parser()
parser.parse_args(["--files"])  # Zero values OK with nargs="*"
assert parser.files == []
```

---

## Type Hints

| Hint | Behavior |
|------|----------|
| `name: str` | Required argument |
| `name: str = "default"` | Optional with default |
| `name: str \| None` | Optional, defaults to `None` |
| `name: Path` | Auto-converts string to `Path` |

<!--- name: test_pitfall_optional --->
```python
import argclass

class Parser(argclass.Parser):
    config: str | None  # Implies default=None, NOT required

parser = Parser()
parser.parse_args([])
assert parser.config is None
```

---

## Config Files (INI)

| Issue | Solution |
|-------|----------|
| Section name mismatch | Section must match group attribute name (lowercase) |
| Lists as comma-separated | Use Python literal: `ports = [8080, 8081]` |
| Strings in lists | Quote them: `hosts = ["a.com", "b.com"]` |

```ini
# Group attribute: database = DatabaseGroup()

[database]        # RIGHT - matches attribute name
host = db.example.com

[Database]        # WRONG - case mismatch
```

---

## Groups

Group arguments are prefixed with the group name:

```text
class Parser(argclass.Parser):
    database = DatabaseGroup()  # prefix is "database"

# CLI usage:
--database-host value    # RIGHT
--host value             # WRONG - no such argument
```

---

## Subcommands

Only the selected subcommand is populated:

<!--- name: test_pitfall_subparser --->
```python
import argclass

class Serve(argclass.Parser):
    port: int = 8080

class Build(argclass.Parser):
    output: str = "dist"

class CLI(argclass.Parser):
    serve = Serve()
    build = Build()

cli = CLI()
cli.parse_args(["serve", "--port", "9000"])
assert cli.serve.port == 9000
# cli.build.output is still default
```

Use `cli.current_subparsers` to check which subcommand was selected.
