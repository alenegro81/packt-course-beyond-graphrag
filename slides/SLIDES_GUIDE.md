# Slides Guide — Beyond GraphRAG Course

This directory holds all Marp slide decks and supporting assets for the
Packt course **Beyond GraphRAG — Building an Explainable Financial Advisor
with Knowledge Graphs, Neo4j, and LLM Agents**.

---

## Directory layout

```
slides/
├── SLIDES_GUIDE.md          ← you are here
├── themes/
│   └── course-negro.css       ← custom Marp theme
├── assets/
│   ├── images/              ← photos, screenshots
│   ├── icons/               ← SVG icons
│   └── diagrams/            ← exported architecture diagrams
├── modules/
│   ├── module_00_intro.md   ← course intro deck
│   ├── module_01_*.md
│   └── …
└── _template.md             ← master layout reference (start here)
```

---

## Tooling

| Tool | Purpose |
|---|---|
| **Marp CLI** | Convert `.md` → HTML / PDF / PPTX |
| **Marp for VS Code** | Live preview while editing |

### Install

```bash
npm install -g @marp-team/marp-cli
# or via Homebrew
brew install marp-cli
```

### HTML — single deck (primary format, self-contained)

```bash
marp slides/modules/module_00_intro.md \
  --theme slides/themes/course-negro.css \
  --allow-local-files \
  --output slides/dist/module_00_intro.html
```

`--allow-local-files` embeds images from `slides/assets/` into the HTML.
The output is a **single self-contained file** — open it in any browser,
no server needed.

### HTML — all decks at once

```bash
marp slides/modules/ \
  --theme slides/themes/course-negro.css \
  --allow-local-files \
  --output slides/dist/
```

### PDF — single deck

```bash
marp slides/modules/module_00_intro.md \
  --theme slides/themes/course-negro.css \
  --allow-local-files \
  --pdf \
  --output slides/dist/module_00_intro.pdf
```

### PPTX — single deck

> **Note:** PPTX export renders each slide as an image — text will not be
> editable in PowerPoint. Prefer HTML for sharing and PDF for printing.

```bash
marp slides/modules/module_00_intro.md \
  --theme slides/themes/course-negro.css \
  --allow-local-files \
  --pptx \
  --output slides/dist/module_00_intro.pptx
```

### Watch mode (live preview in browser)

```bash
marp --watch slides/modules/module_00_intro.md \
  --theme slides/themes/course-negro.css \
  --allow-local-files
```

---

## Front matter (every deck)

```yaml
---
marp: true
theme: course-negro
size: 16:9
paginate: true
footer: "Beyond GraphRAG · Packt · Alessandro Negro"
---
```

Place the `themes/` path on Marp's theme search path by adding a
`.marprc.yml` at the project root (already provided).

---

## Slide layouts (classes)

Apply a layout with the local directive `<!-- _class: layout-name -->` on
the slide where you want it.  A directive with a leading underscore affects
**only that slide**; without the underscore it applies to all remaining
slides.

| Class | Description |
|---|---|
| `title` | Course / module title card (dark navy background) |
| `divider` | Section break between topics |
| `image-full` | Single full-bleed image (bg fills the entire slide) |
| `split-right` | Text on the left, image on the right (via Marp `![bg right]`) |
| `split-left` | Image on the left, text on the right (via Marp `![bg left]`) |
| `cols-2` | Two equal text columns below a spanning heading |
| `cols-3` | Three equal text columns below a spanning heading |
| `code-focus` | Enlarged code block, minimal prose chrome |
| `quote` | Dark slide with large pull-quote |
| `demo` | Visual cue for a live-coding or demo segment |

---

## Layout usage examples

### `title` — course / module opener

```markdown
<!-- _class: title -->

# Beyond GraphRAG
## Building an Explainable Financial Advisor

---

Alessandro Negro · Packt 2025
```

---

### `divider` — section break

```markdown
<!-- _class: divider -->

# Module 3
## Graph Enrichment
```

---

### `image-full` — full-bleed photo or diagram

```markdown
<!-- _class: image-full -->

![Architecture overview](../assets/diagrams/full-architecture.png)

*Caption shown as overlay at the bottom*
```

---

### `split-right` — content left, image right

```markdown
<!-- _class: split-right -->

![bg right:45%](../assets/images/neo4j-browser.png)

# Vector + Graph Retrieval

- Hybrid search combines semantic similarity with graph traversal
- Reduces hallucination through structured grounding
- Enables multi-hop reasoning across entities
```

---

### `split-left` — image left, content right

```markdown
<!-- _class: split-left -->

![bg left:45%](../assets/diagrams/langgraph-loop.png)

# The ReAct Agent Loop

1. **Reason** — interpret the question
2. **Act** — select the right retrieval tool
3. **Observe** — incorporate graph results
4. **Repeat** until confident
```

---

### `cols-2` — two text columns

```markdown
<!-- _class: cols-2 -->

# GraphRAG vs. Beyond GraphRAG

**Classic GraphRAG**
- Fixed extraction pipeline
- Pre-defined schema
- Retrieval at chunk level

**Beyond GraphRAG**
- Dynamic entity extraction
- Schema-agnostic agents
- Reasoning at graph level
```

---

### `cols-3` — three text columns

```markdown
<!-- _class: cols-3 -->

# Three Retrieval Strategies

### Vector Search
Semantic similarity over embeddings. Fast, fuzzy, works without schema.

### Graph Traversal
Structured paths through entities and relationships. Explainable by design.

### Text-to-Cypher
Natural language → Cypher query via LLM. Handles ad-hoc financial questions.
```

---

### `code-focus` — code spotlight

```markdown
<!-- _class: code-focus -->

# Graph Schema — Module 1 Constraints

```cypher
CREATE CONSTRAINT company_id IF NOT EXISTS
  FOR (c:Company) REQUIRE c.id IS UNIQUE;

CREATE CONSTRAINT chunk_id IF NOT EXISTS
  FOR (ch:Chunk) REQUIRE ch.id IS UNIQUE;

CREATE VECTOR INDEX chunk_embeddings IF NOT EXISTS
  FOR (ch:Chunk) ON (ch.embedding)
  OPTIONS { indexConfig: { `vector.dimensions`: 1536,
                           `vector.similarity_function`: "cosine" }};
```
```

---

### `quote` — pull-quote or key insight

```markdown
<!-- _class: quote -->

> A knowledge graph doesn't just store facts —
> it stores the *relationships* that make facts meaningful.

Alessandro Negro
```

---

### `demo` — live coding / notebook segment

```markdown
<!-- _class: demo -->

# Live Demo

## Notebook: `module_03_enrichment.ipynb`

*Switch to VS Code*
```

---

## Marp background image helpers (built-in, no class needed)

These are standard Marp directives — combine freely with any class above.

```markdown
# Full background
![bg](image.png)

# Right split, width 40%
![bg right:40%](image.png)

# Left split, width 50%
![bg left:50%](image.png)

# Darken a background image for legibility
![bg brightness:0.4](image.png)

# Blur a background image
![bg blur:4px](image.png)

# Multiple background images (tiled left-right)
![bg left:33%](img1.png)
![bg](img2.png)
```

---

## Naming convention for deck files

```
module_00_intro.md
module_01_ingestion.md
module_02_retrieval.md
module_03_enrichment.md
module_04_extraction.md
module_05_similarity.md
module_06_text2cypher.md
module_07_evaluation.md
```

---

## Tips

- Keep slides at **one idea each** — Marp renders one `---` block per slide.
- Use `<!-- _class: ... -->` (underscore) to scope a layout to a single slide only.
- Diagrams go in `assets/diagrams/` as PNGs exported at 2× resolution (2560 × 1440 px).
- Screenshots go in `assets/images/` and should be cropped to the relevant area.
- Prefer SVG for icons (`assets/icons/`) — they scale without blurring.
