# Slides — Claude Code Guide

This directory contains all Marp slide decks for the Packt course
**Beyond GraphRAG**. Read this file before generating or editing any slides.

## Tool: Marp

Slides are plain Markdown files rendered by [Marp](https://marp.app/).
The CLI is installed at `/opt/homebrew/bin/marp`.

Every deck must start with this front matter (copy exactly):

```yaml
---
marp: true
theme: course-negro
size: 16:9
paginate: true
footer: "Beyond GraphRAG · Packt · Alessandro Negro"
---
```

The theme name `course-negro` is resolved via `.vscode/settings.json`
(`markdown.marp.themes`) for VS Code preview and via `.marprc.yml` for CLI builds.
Both point to `slides/themes/course-negro.css`.

## Directory structure

```
slides/
├── CLAUDE.md                ← this file
├── SLIDES_GUIDE.md          ← full human-readable reference with examples
├── _template.md             ← copy-paste source for every layout
├── themes/
│   └── course-negro.css     ← custom CSS theme (do not rename)
├── assets/
│   ├── images/              ← screenshots, photos (PNG/JPG)
│   ├── icons/               ← SVG icons
│   └── diagrams/            ← architecture diagrams (export at 2× = 2560×1440 px)
└── modules/
    ├── module_00_intro.md
    ├── module_01_ingestion.md
    └── …
```

Output always goes to `slides/dist/` (created automatically by Marp).

## Build commands

Always run from the **project root**. Always include `--allow-local-files`
so images from `slides/assets/` are embedded.

```bash
# Single deck → HTML (primary sharing format, self-contained)
marp slides/modules/module_00_intro.md \
  --theme slides/themes/course-negro.css \
  --allow-local-files \
  --output slides/dist/module_00_intro.html

# Single deck → PDF
marp slides/modules/module_00_intro.md \
  --theme slides/themes/course-negro.css \
  --allow-local-files \
  --pdf \
  --output slides/dist/module_00_intro.pdf

# Single deck → PPTX (slides render as images — text not editable in PowerPoint)
marp slides/modules/module_00_intro.md \
  --theme slides/themes/course-negro.css \
  --allow-local-files \
  --pptx \
  --output slides/dist/module_00_intro.pptx

# All decks → HTML
marp slides/modules/ \
  --theme slides/themes/course-negro.css \
  --allow-local-files \
  --output slides/dist/

# Live preview (opens browser, auto-reloads on save)
marp --watch slides/modules/module_00_intro.md \
  --theme slides/themes/course-negro.css \
  --allow-local-files
```

Preferred export order: **HTML first** (best fidelity, self-contained),
PDF for printing, PPTX only when explicitly requested.

## Slide layouts

Apply a layout to a single slide with `<!-- _class: layout-name -->` (the
leading underscore scopes it to that slide only). Without the underscore it
applies to all subsequent slides.

| Class | When to use |
|---|---|
| `title` | First slide of a deck — dark navy, large heading |
| `divider` | Section break between major topics within a deck |
| `image-full` | Architecture diagram or screenshot that needs the full canvas |
| `split-right` | Prose/bullets left + image right — use `![bg right:45%](path)` |
| `split-left` | Image left + prose/bullets right — use `![bg left:45%](path)` |
| `cols-2` | Two concepts side by side; h1 spans both columns automatically |
| `cols-3` | Three parallel pillars; h1 spans all three columns |
| `code-focus` | Cypher or Python snippet as the main content |
| `quote` | Dark slide with a single large pull-quote |
| `demo` | Transition slide signalling a live-coding or notebook demo |

Full examples for every layout are in `_template.md`.

## Authoring rules

- **One idea per slide.** Slides are separated by `---`.
- **Module deck naming:** `module_XX_<short-topic>.md` — two-digit zero-padded number matching the course module.
- **Images:** reference as relative paths from the deck file, e.g. `../assets/diagrams/foo.png`. Export diagrams at 2× (2560 × 1440 px minimum).
- **Footer and theme** must be identical across all decks (copy from front matter above).
- **Do not edit** `themes/course-negro.css` for per-deck tweaks — use inline directives instead.
- When generating a new module deck, start from `_template.md` and delete unused layout blocks.
