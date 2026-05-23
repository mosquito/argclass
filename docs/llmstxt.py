"""Sphinx extension: generate llms.txt and llms-full.txt on HTML build."""

from __future__ import annotations

import re
from pathlib import Path

from sphinx.application import Sphinx

# (stem, title, description, optional)
_PAGES: list[tuple[str, str, str, bool]] = [
    (
        "quickstart",
        "Quick Start",
        "5-minute overview of essential concepts",
        False,
    ),
    (
        "tutorial",
        "Tutorial",
        "30-minute guide building a complete CLI application",
        False,
    ),
    (
        "arguments",
        "Arguments",
        "Typed arguments, defaults, nargs, enums, boolean flags",
        False,
    ),
    ("groups", "Groups", "Reusable argument groups with prefix support", False),
    (
        "subparsers",
        "Subparsers",
        "Hierarchical subcommands and nested parsers",
        False,
    ),
    (
        "config-files",
        "Config Files",
        "INI, JSON, and TOML configuration file support",
        False,
    ),
    (
        "config-generation",
        "Generating Config Files",
        "Writing INI/JSON/TOML/.env from a parser",
        False,
    ),
    (
        "environment",
        "Environment Variables",
        "Automatic env var binding with prefixes",
        False,
    ),
    (
        "secrets",
        "Secrets",
        "Secret masking to prevent accidental exposure in logs",
        False,
    ),
    (
        "api",
        "API Reference",
        "Full API documentation with all classes and functions",
        False,
    ),
    (
        "examples",
        "Examples Gallery",
        "Ready-to-use patterns from simple CLIs to multi-command tools",
        True,
    ),
    ("errors", "Error Handling", "Error types and handling strategies", True),
    (
        "pitfalls",
        "Common Pitfalls",
        "Frequent mistakes and how to avoid them",
        True,
    ),
    ("integrations", "Integrations", "Using argclass with other tools", True),
    ("security", "Security", "Security policy and best practices", True),
]


def _page_link(stem: str, title: str, description: str, base_url: str) -> str:
    # API page has no plain-text source (autodoc-generated); link to HTML
    url = (
        f"{base_url}api.html"
        if stem == "api"
        else f"{base_url}_sources/{stem}.md.txt"
    )
    return f"- [{title}]({url}): {description}"


def _links_block(pages: list[tuple[str, str, str, bool]], base_url: str) -> str:
    essential = [(s, t, d) for s, t, d, opt in pages if not opt]
    optional = [(s, t, d) for s, t, d, opt in pages if opt]

    lines = [
        "## Docs markdown files split by topic for"
        " easier navigation and LLM processing:",
        "",
        "The links below point to the **raw Markdown source** of each",
        "documentation page (`/_sources/<topic>.md.txt` on docs.argclass.com),",
        "not the rendered HTML. Prefer these for LLM consumption: they are the",
        "exact authored text — no HTML scaffolding, no navigation chrome, no",
        "JavaScript — so you can read them directly without HTML parsing or",
        "content extraction.",
        "",
        *(_page_link(s, t, d, base_url) for s, t, d in essential),
    ]
    if optional:
        lines += [
            "",
            "## Optional",
            "",
            *(_page_link(s, t, d, base_url) for s, t, d in optional),
        ]
    return "\n".join(lines)


def _on_build_finished(app: Sphinx, exception: Exception | None) -> None:
    if exception or app.builder.name != "html":
        return

    src_dir = Path(app.srcdir)
    out_dir = Path(app.outdir)
    base_url: str = app.config.html_baseurl or ""
    pages: list[tuple[str, str, str, bool]] = app.config.llms_pages

    # --- llms.txt ---
    # Replace the auto-generated links block; keep the hand-crafted body
    # (everything from the first top-level blockquote onward).
    source = (src_dir / "llms.txt").read_text(encoding="utf-8")
    m = re.search(r"\n\n> ", source)
    body = source[m.start() :] if m else ""
    llms_txt = (
        f"# {app.config.project}\n\n{_links_block(pages, base_url)}{body}"
    )
    (out_dir / "llms.txt").write_text(llms_txt, encoding="utf-8")

    # --- llms-full.txt ---
    # Concatenate every markdown source in page order.
    parts: list[str] = []
    for stem, *_ in pages:
        md = src_dir / f"{stem}.md"
        if md.exists():
            parts.append(md.read_text(encoding="utf-8"))
    (out_dir / "llms-full.txt").write_text(
        "\n\n---\n\n".join(parts), encoding="utf-8"
    )


def setup(app: Sphinx) -> dict[str, object]:
    app.add_config_value("llms_pages", _PAGES, "html")
    app.connect("build-finished", _on_build_finished)
    return {
        "version": "0.1",
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
