# Concepts

These pages explain **how argclass works and why** — the mental models behind
the API, rather than step-by-step instructions. Read them when you want to
understand the design, not to accomplish a specific task. For tasks, see the
[Quick Start](../quickstart.md), [Tutorial](../tutorial.md), and the How-to
Guides; for exact signatures, see the [API Reference](../api.md).

```{toctree}
:maxdepth: 1

parsers-and-groups
configuration-model
type-system
security
```

- **[Parsers, groups & subparsers](parsers-and-groups.md)** — what a class-body
  declaration actually is, why groups are not parsers, and how instances become
  per-parser copies.
- **[The configuration model](configuration-model.md)** — the single priority
  chain that governs defaults, config files, environment, and CLI, and how it
  shapes both reading and generating config.
- **[Types & custom actions](type-system.md)** — how values flow through the
  `type` → `converter` pipeline and how argparse passthrough lets you ship
  custom actions.
- **[Security model](security.md)** — the threat model for secrets and
  environment sanitization, and what argclass does and does not protect.
