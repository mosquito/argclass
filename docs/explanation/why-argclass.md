# Why argclass?

argclass exists to fill a specific gap: the space between raw `argparse` (powerful
but verbose and untyped) and decorator-based frameworks like Click or Typer
(ergonomic but opinionated and dependency-heavy). This page explains the design
choices behind that position — read it to understand *why* the API looks the way
it does, not how to use it.

## The gap it fills

Unlike raw `argparse`, argclass gives you **type safety and IDE support**: you
declare arguments as annotated class attributes, and your editor knows their
types. Unlike decorator-based frameworks, argclass uses **plain OOP** — your
parsers are real classes, so inheritance, composition, and unit testing all work
the way they already do in the rest of your code. And it ships with **zero
dependencies**, staying close to the standard library.

| Feature                 | argclass | argparse | click/typer |
|-------------------------|----------|----------|-------------|
| Type hints → arguments  | Yes      | No       | Yes         |
| Class-based (OOP)       | Yes      | No       | Decorators  |
| IDE autocompletion      | Yes      | No       | Yes         |
| Config file support     | Built-in | No       | No          |
| Environment variables   | Built-in | No       | Plugin      |
| Secret masking          | Built-in | No       | No          |
| Argument groups         | Reusable | Limited  | No          |
| Dependencies            | stdlib   | stdlib   | Many        |

## Why classes instead of decorators

A decorator-based CLI couples the parser definition to a function. argclass keeps
the parser a **first-class object**: a `Parser` subclass is a value you can
instantiate, subclass, compose out of [groups](parsers-and-groups.md), and pass
around in tests without touching `sys.argv`. The same mechanism that makes a
group reusable makes a whole parser reusable — there is no separate "command
object" concept to learn, just Python classes.

## Why zero dependencies

argclass is a thin declarative layer over the standard library's `argparse`. That
is a deliberate constraint, not an accident: it means argclass works anywhere
Python does, adds nothing to your dependency-audit surface, and degrades to plain
`argparse` semantics whenever you reach past what it models (see
[argparse passthrough](type-system.md#argparse-passthrough-the-escape-hatch)).
The built-in config-file, environment-variable, and secret-masking support is all
implemented on top of stdlib primitives rather than pulled in from third parties.
