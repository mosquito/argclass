# Parsers, Groups & Subparsers

This page explains the model behind the three building blocks you assign in a
parser class body. The task-oriented pages — [Argument Groups](../groups.md) and
[Subparsers](../subparsers.md) — show *how* to use them; this one explains *what
they are* and why they behave the way they do.

## A Group instance is a declaration, not a parser

A `Group()` you assign on a parser class — `db = DatabaseGroup()` or
`db: DatabaseGroup = DatabaseGroup(defaults={...})` — is a **declaration of
structure and per-instance defaults**, not a runtime parser. You don't call
methods on it; you don't use it to read CLI arguments. Its job at
class-definition time is to:

- name a slot in the parsed result (`parser.db`),
- describe which arguments belong to that slot (via its annotations),
- optionally override defaults for this particular slot (`defaults=`, `title=`,
  `prefix=`).

When you call `Parser().parse_args(...)`, argclass walks these declarations,
builds an `argparse` parser from them, parses the command line, and then writes
the parsed values back into the group instance so you can read them as
`parser.db.host`. The instance is a **write target** during parsing, not an
active participant in it.

The practical consequence: **don't call parser methods on a `Group` instance.**
It has no `parse_args()`. Groups are not standalone parsers.

## Instances are prototypes; each parser gets its own copy

Group and subparser instances written in a class body are **prototypes**. Every
`Parser` instance works on its own deep copies of them, so two parser instances
never share parsed state, and one instance's `parse_args()` can't leak values
into another.

This is also why assigning the *same* class-body instance to several attributes
is safe — each binding becomes an independent copy with its own parsed state:

<!--- name: test_concept_group_instance_copy --->
```python
import argclass

class Credentials(argclass.Group):
    username: str = "admin"

shared = Credentials()

class Parser(argclass.Parser):
    primary = shared
    secondary = shared    # fine: each binding gets its own copy

parser = Parser()
parser.parse_args(["--primary-username", "alice", "--secondary-username", "bob"])

assert parser.primary.username == "alice"
assert parser.secondary.username == "bob"
```

`parser.primary` and `parser.secondary` parse independently. The copies do
inherit the prototype's `title`, `description`, and `prefix`, so a reused
instance with an explicit `prefix=` would produce conflicting CLI flags — give
each attribute its own instance when they need different options.

The only forbidden shape is a **cycle** — a group that directly or indirectly
contains itself — which raises `ArgclassError` at parser construction time.

## Groups vs. subparsers

The "instance-is-a-declaration" rule is specific to `Group`. **Subparsers are
different**: a subparser is a `Parser` subclass instance assigned to an attribute
(e.g. `serve = Serve()`), and at runtime the *selected* subparser really does
parse its own slice of `sys.argv` — it has a working `parse_args()`, its own
`__call__`, and its own subparsers. Subparsers are real parsers chosen by name
from the CLI; groups are namespaced collections of arguments declared upfront.

If you want a runnable sub-command, use a subparser. If you want to bundle
related options under a prefix, use a group.

## Why subparsers are designed this way

Many CLI tools need multiple related commands under a single entry point.
Instead of separate scripts (`myapp-init`, `myapp-build`, `myapp-deploy`),
subparsers let you organize them as `myapp init`, `myapp build`, `myapp deploy`.
argclass's subparser design rests on a few deliberate principles:

- **Composition over inheritance** — each subcommand is a standalone `Parser`
  class that can be tested and reused independently.
- **Type-safe access** — parsed values are read as typed attributes, not
  dictionary lookups.
- **Hierarchical structure** — subcommands can have their own subcommands,
  enabling deep command trees like `kubectl get pods`.
- **Shared context** — parent-parser arguments (like `--verbose`) are reachable
  from a subcommand via `__parent__`.
- **Callable dispatch** — implement `__call__` on a subcommand to define its
  behavior; calling the root parser automatically dispatches to the selected
  subcommand.

See [Subparsers](../subparsers.md) for the runtime contract and worked examples.
