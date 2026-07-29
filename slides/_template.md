---
marp: true
theme: course-negro
size: 16:9
paginate: true
footer: "Beyond GraphRAG · Packt · Alessandro Negro"
---

<!--
  _template.md — Master layout reference
  =======================================
  Copy-paste any slide block below into your module deck.
  Delete slides you don't need; keep this file intact as a reference.
  Every slide starts with three dashes (---) as a separator.
-->

<!-- _class: title -->

# Beyond GraphRAG
## Building an Explainable Financial Advisor
### with Knowledge Graphs, Neo4j, and LLM Agents

---

Alessandro Negro · Packt 2025

---

<!--
  ┌─────────────────────────────────────────────┐
  │  LAYOUT: divider                             │
  │  Purpose: section break between topics       │
  └─────────────────────────────────────────────┘
-->

<!-- _class: divider -->

# Module X
## Section Title Here

---

<!--
  ┌─────────────────────────────────────────────┐
  │  LAYOUT: default (plain content)             │
  │  Purpose: most body slides                   │
  └─────────────────────────────────────────────┘
-->

# Slide Title

- First bullet point — keep it short
- Second bullet point
  - Sub-point in smaller text
- Third bullet point

> Use a blockquote for a key takeaway or definition.

---

<!--
  ┌─────────────────────────────────────────────┐
  │  LAYOUT: image-full                          │
  │  Purpose: architecture diagram, screenshot   │
  │  that needs the full slide                   │
  └─────────────────────────────────────────────┘
  Replace the src below with your actual image path.
  Caption is optional — omit the last paragraph if not needed.
-->

<!-- _class: image-full -->

![Full-bleed diagram](../assets/diagrams/full-architecture.png)

*Optional caption shown as an overlay*

---

<!--
  ┌─────────────────────────────────────────────┐
  │  LAYOUT: split-right                         │
  │  Purpose: text on the left, image on right   │
  │  Marp handles the split via ![bg right:XX%]  │
  └─────────────────────────────────────────────┘
  Adjust the percentage (40–55%) to balance content vs image.
-->

<!-- _class: split-right -->

![bg right:45%](../assets/images/placeholder.png)

# Slide Title

- First key point about what the image shows
- Second key point
- Third key point

**Bold text** draws attention to the most important idea.

---

<!--
  ┌─────────────────────────────────────────────┐
  │  LAYOUT: split-left                          │
  │  Purpose: image on the left, text on right   │
  └─────────────────────────────────────────────┘
-->

<!-- _class: split-left -->

![bg left:45%](../assets/images/placeholder.png)

# Slide Title

1. Numbered list for sequential steps
2. Second step
3. Third step

*Italic text for supplementary notes or caveats.*

---

<!--
  ┌─────────────────────────────────────────────┐
  │  LAYOUT: cols-2                              │
  │  Purpose: compare two concepts side-by-side  │
  │  NOTE: heading spans both columns            │
  └─────────────────────────────────────────────┘
  The heading (h1) automatically spans both columns.
  Everything after is placed left-column first, then right.
-->

<!-- _class: cols-2 -->

# Comparing Two Approaches

**Left Column Heading**
- Point A
- Point B
- Point C

**Right Column Heading**
- Point D
- Point E
- Point F

---

<!--
  ┌─────────────────────────────────────────────┐
  │  LAYOUT: cols-3                              │
  │  Purpose: three parallel concepts / pillars  │
  └─────────────────────────────────────────────┘
-->

<!-- _class: cols-3 -->

# Three Core Pillars

### Pillar One
Short description of this concept. Keep it to 2–3 sentences max.

### Pillar Two
Short description of this concept. Keep it to 2–3 sentences max.

### Pillar Three
Short description of this concept. Keep it to 2–3 sentences max.

---

<!--
  ┌─────────────────────────────────────────────┐
  │  LAYOUT: code-focus                          │
  │  Purpose: show a code or Cypher snippet      │
  └─────────────────────────────────────────────┘
-->

<!-- _class: code-focus -->

# Code / Cypher Example

```cypher
MATCH (c:Company)-[:HAS_DOCUMENT]->(d:Document)-[:HAS_CHUNK]->(ch:Chunk)
WHERE c.ticker = $ticker
CALL db.index.vector.queryNodes(
  'chunk_embeddings', 10, $embedding
) YIELD node AS similar, score
RETURN similar.text AS text, score
ORDER BY score DESC
```

Brief annotation of what the query does and why it matters.

---

<!--
  ┌─────────────────────────────────────────────┐
  │  LAYOUT: quote                               │
  │  Purpose: key insight, memorable statement   │
  └─────────────────────────────────────────────┘
-->

<!-- _class: quote -->

> The graph is not just a database.
> It is the reasoning substrate of your agent.

Author Name, Context

---

<!--
  ┌─────────────────────────────────────────────┐
  │  LAYOUT: demo                                │
  │  Purpose: transition slide into live coding  │
  └─────────────────────────────────────────────┘
-->

<!-- _class: demo -->

# Live Demo

## Notebook: `module_0X_title.ipynb`

*Switch to VS Code / Jupyter*

---

<!--
  ┌─────────────────────────────────────────────┐
  │  MISC HELPERS — no class needed              │
  └─────────────────────────────────────────────┘
-->

# Background Image Helpers

```markdown
![bg](image.png)                    ← full background
![bg right:40%](image.png)          ← right split 40 %
![bg left:50%](image.png)           ← left split 50 %
![bg brightness:0.35](image.png)    ← darken for legibility
![bg blur:4px](image.png)           ← blur background
```

These are Marp built-ins — combine freely with any `_class` above.

---

# Summary Slide

- **Key point 1** — one-line recap
- **Key point 2** — one-line recap
- **Key point 3** — one-line recap

**Next:** Module X+1 — *Next Module Title*
