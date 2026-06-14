# Types & Custom Actions

argclass turns type annotations into argument behavior, and lets you drop down to
raw `argparse` when you need to. This page explains the two mechanisms behind that
— the value-conversion pipeline and argparse passthrough. For the catalogue of
supported types and options, see [Arguments](../arguments.md).

## The conversion pipeline: `type` vs `converter`

A value flows through two distinct stages, and `type` and `converter` hook into
different ones:

- **`type`** is called for **each input string** as it is parsed, before values
  are collected. It is the per-item conversion (e.g. `int` on every element of a
  `nargs="+"` list).
- **`converter`** is called **once on the final collected result**, after parsing.
  It post-processes the whole value (e.g. turning a parsed list into a `set`).

So `Argument(nargs="+", type=int, converter=set)` parses each token with `int`,
then hands the resulting list to `set`. Reach for `type` when each value needs
the same conversion, and `converter` when the *aggregate* needs reshaping. See
[Type vs Converter](../arguments.md#type-vs-converter) for runnable examples.

## Argparse passthrough: the escape hatch

argclass deliberately does not model every `argparse` feature. Instead,
`Argument()` (and `ArgumentSingle()` / `ArgumentSequence()`) accept arbitrary
extra keyword arguments and forward them **as-is** to
`argparse.ArgumentParser.add_argument()`. Extra kwargs are stored as an immutable
`MappingProxyType` on the argument and merged in at parser-construction time.

This passthrough is what lets you ship a custom `argparse.Action` subclass that
takes its own constructor parameters: whatever extra kwargs you pass through
`Argument(...)` arrive directly in the action's `__init__`. The most common use
is the `version=` parameter for `Actions.VERSION`. argclass strips `type=` for the
actions argparse rejects it on (`VERSION`, `HELP`, `STORE_TRUE`, `STORE_FALSE`,
`COUNT`).

## Why "fire and exit" actions opt out of config dumps

Some custom actions — `--version`, `--check-updates`, `--health` — print
something and call `parser.exit()` rather than storing a value. These would
otherwise show up as noisy empty entries in a generated config, so argclass's
generators skip them. An action signals this with the `__emit_config__ = False`
marker, either by inheriting from `argclass.NonConfigAction` or by setting the
attribute directly. Built-in `--help` / `--version` are recognised automatically;
stateful actions (counters, accumulators) are *kept* in dumps — only fire-and-exit
actions need to opt out. See
[Custom Actions and config generation](../arguments.md#custom-actions-and-config-generation).
