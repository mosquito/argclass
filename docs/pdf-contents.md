---
orphan: true
---

% LaTeX/PDF master document. The HTML build uses index.md (a rich landing
% page); the PDF uses this minimal root so the four Diátaxis modes render as
% top-level parts instead of being buried under the landing page's headings.
% Keep these toctrees in sync with the ones in index.md.

# argclass Documentation

```{toctree}
:maxdepth: 2
:caption: Tutorials

quickstart
tutorial
```

```{toctree}
:maxdepth: 2
:caption: How-to Guides

examples
groups
subparsers
config-files
config-generation
environment
secrets
integrations
errors
pitfalls
```

```{toctree}
:maxdepth: 2
:caption: Reference

api
arguments
config-file-reference
```

```{toctree}
:maxdepth: 2
:caption: Explanation

explanation/index
```
