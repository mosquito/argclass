# The Configuration Model

argclass reads configuration from several places — class defaults, config files,
a user-supplied config file, environment variables, and the command line. They
are not independent features: they are layers of **one priority chain**, and the
same chain governs both reading config and generating it. This page explains that
model. For how to actually load files see [Configuration Files](../config-files.md);
for writing them see [Generating Config Files](../config-generation.md).

## One priority chain

Every value is resolved by applying sources in order, where each later source
overrides the earlier ones:

:::{card}
1. **Class defaults** → 2. **Config files** (`config_files=`) →
3. **User config** (`config_argument`) → 4. **Environment variables** →
5. **CLI arguments**
:::

| Source | Overrides | Overridden by |
|--------|-----------|---------------|
| Class default | — | Config, User config, Env, CLI |
| Config file (`config_files=`) | Class default | User config, Env, CLI |
| User config (`config_argument`) | Class default, Config | Env, CLI |
| Environment variable | Class default, Config, User config | CLI |
| CLI argument | All | — |

The mental model is "least specific to most specific": values baked into the code
are the weakest, values typed at the prompt for this one invocation are the
strongest, and everything else sits in between. This single ordering is the
reason the features compose without surprises — there is nothing to learn
per-source beyond *where it sits in the chain*.

`parser.loaded_config_files` reports which files actually contributed, in
priority order.

## The same chain shapes generated config

Config generation (`--generate-config`, the `*ConfigGenerator` classes) is the
inverse of reading, and it reads from the **same** resolved state. A dump reflects
the parser's *current* values at the moment generation fires — so all five
sources above can shape the output, not just class defaults.

Because argparse processes flags left-to-right and the generate action exits
before later flags are seen, CLI values parsed *before* `--generate-config` land
in the dump while later ones don't. Putting `--generate-config` last is the safe
convention. The practical payoff: a parser loaded from one format and dumped
through another generator is a **format converter** — load through reader X, dump
through generator Y. The conversion is schema-validated against the parser, so
keys with no matching argument are dropped and missing keys fall back to defaults.

See [What lands in the dump](../config-generation.md#what-lands-in-the-dump) for
the per-source breakdown and a runnable conversion example.

## Two unrelated things both spelled `config`

A recurring source of confusion: a `--config` flag can mean two different things.

- **`config_argument="--config"`** and **`config_files=`** feed the priority
  chain above — they supply *defaults for your other arguments*.
- **`argclass.Config()`** is unrelated — it loads a whole file into a single
  attribute as raw data and touches nothing else.

The [navigator table](../config-files.md) at the top of the Configuration Files
guide picks the right one for a given goal.
