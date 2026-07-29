---
marp: true
theme: course-negro
size: 16:9
paginate: true
footer: "Beyond GraphRAG · Packt · Alessandro Negro"
---

<!-- _class: title -->

# Beyond GraphRAG
## Building an Explainable Financial Advisor
### with Knowledge Graphs, Neo4j, and LLM Agents

---

Alessandro Negro · Packt 2025

---

<!-- _class: divider -->

# About This Course
## What you will build — and why it matters

---

# The Problem with Standard RAG

- **Chunk retrieval** loses the relationships between facts
- **Hallucination** increases when context is flat and disconnected
- **Explainability** is near-zero — why did the agent say that?

> Financial advice requires *traceable* reasoning, not just plausible text.

---

<!-- _class: cols-2 -->

# RAG vs. Beyond GraphRAG

**Standard RAG**
- Text chunks in a vector store
- Cosine similarity only
- No entity awareness
- Black-box retrieval

**Beyond GraphRAG**
- Knowledge graph + vectors
- Structured + semantic search
- Entities, roles, events
- Explainable agent traces

---

<!-- _class: image-full -->

![bg](../assets/diagrams/full-architecture.png)

*End-to-end architecture — from 10-K PDFs to explainable answers*

---

# What You Will Build

1. **Ingest** corporate 10-K filings into a Neo4j knowledge graph
2. **Enrich** the graph with executives, events, and news articles
3. **Extract** entities and relationships with LLM pipelines
4. **Link** similar content with vector-based similarity edges
5. **Query** the graph in natural language via Text-to-Cypher
6. **Evaluate** answer quality with an LLM-as-judge harness

---

<!-- _class: cols-3 -->

# Three Retrieval Strategies

### Vector Search
Semantic similarity over chunk embeddings.
Fast, fuzzy, no schema required.

### Graph Traversal
Structured paths through entities and relationships.
Explainable by design.

### Text-to-Cypher
Natural language → Cypher query via LLM.
Handles ad-hoc financial questions.

---

<!-- _class: split-right -->

![bg right:45%](../assets/images/neo4j-browser.png)

# The Technology Stack

- **Neo4j 5.x** — property graph + vector index
- **LangGraph** — agentic ReAct loop
- **Azure OpenAI** — GPT-4o + `text-embedding-3-small`
- **Docling** — PDF extraction
- **LangChain** — tool wrappers and chain utilities
- **Pydantic** — schema validation throughout

---

<!-- _class: quote -->

> A knowledge graph doesn't just store facts —
> it stores the *relationships* that make facts meaningful.

Alessandro Negro

---

<!-- _class: divider -->

# Module 1
## Graph Ingestion — From PDFs to Knowledge Graph

---

# Module Overview

| Module | Topic |
|---|---|
| 1 | Graph ingestion — Companies, Documents, Chunks |
| 2 | Hybrid retrieval + LangGraph agent |
| 3 | Graph enrichment — Persons, Events, Articles |
| 4 | LLM entity & relationship extraction |
| 5 | Similarity linking & entity resolution |
| 6 | Text-to-Cypher with safety guardrails |
| 7 | LLM-as-judge evaluation framework |

---

<!-- _class: demo -->

# Let's Start

## Notebook: `module_00_intro.ipynb`

*Switch to VS Code*
