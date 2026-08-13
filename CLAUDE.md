# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Packt course: **Beyond GraphRAG — Building an Explainable Financial Advisor with Knowledge Graphs, Neo4j, and LLM Agents**. The project ingests corporate filings (10-Ks), news, and executive data into a Neo4j knowledge graph, then answers complex financial questions via a LangGraph agentic retrieval loop.

## Setup

```bash
poetry install
cp .env.example .env   # fill in Azure OpenAI and Neo4j credentials
```

`.env.example` ships with placeholder Azure OpenAI values (`your-api-key`, `https://your-resource.openai.azure.com/`). Embeddings are fully local (see Stack below) so they work with placeholders still in place, but anything that calls the chat LLM (`clients.get_llm()` — the QA/agent answer-generation step) will fail with a DNS-lookup `ConnectError` until `AZURE_OPENAI_ENDPOINT` / `AZURE_OPENAI_API_KEY` / `AZURE_OPENAI_CHAT_DEPLOYMENT` are set to real values.

The local embedding model (`BAAI/bge-m3`, ~2.3GB) downloads from Hugging Face on first use of `embedding_service` — the first cell that touches it in each notebook session will be slow.

## Common commands

```bash
# Unit tests (no Neo4j required)
pytest tests/unit/

# End-to-end tests (requires running Neo4j with ingested data)
pytest tests/e2e/ -v

# Run a single test
pytest tests/unit/test_text2cypher.py::test_disallowed_write_queries -v

# Lint
ruff check src/ tests/ scripts/

# Ingest filings (run once, Module 1)
python scripts/ingest_filings.py data/filings/

# Enrich graph (run once, Module 3)
python scripts/ingest_enrichment.py

# Run LLM extraction over all chunks (long-running, Module 4)
python scripts/run_extraction.py

# Similarity linking + entity resolution (Module 5)
python scripts/run_similarity.py
```

## Architecture

The codebase is a single Poetry package (`src/financial_advisor/`) with subpackages that map 1-to-1 to course modules. Each module's notebook (`notebooks/module_0X_*.ipynb`) is the teaching entry point; the implementation lives in the package.

**Data flow across modules:**
```
PDFs → ingestion/ → Neo4j (Company→Document→Chunk, embedded)   [Module 1]
                 → qa/baseline.py (one-shot RAG demo)            [Module 1]
                 → retrieval/ + agent/ (agentic LangGraph loop)  [Module 2]
                 → enrichment/ (Person, Event, Article)          [Module 3]
                 → extraction/ (LLM entities/rels)               [Module 4]
                 → similarity/ (SIMILAR_TO, merge)                [Module 5]
                 → text2cypher/ (NL→Cypher tool)                  [Module 6]
                 → evaluation/ (LLM-as-judge)                     [Module 7]
```

All modules operate on the **same Neo4j database**, which grows incrementally. Run scripts in order; intermediate results are persisted so long-running steps don't need to be repeated.

**Key files:**
- [src/financial_advisor/config.py](src/financial_advisor/config.py) — Pydantic Settings loading `.env`
- [src/financial_advisor/clients.py](src/financial_advisor/clients.py) — cached factories for `AzureChatOpenAI` (chat only) and `Neo4jGraph`
- [src/financial_advisor/services/embedding_service.py](src/financial_advisor/services/embedding_service.py) — local `sentence-transformers` singleton (`BAAI/bge-m3`, 1024-dim); `.dimensions` drives the vector index size, never hardcode it
- [src/financial_advisor/ingestion/document_loader.py](src/financial_advisor/ingestion/document_loader.py) — `load_from_path` (PDF → chunked `Document`s) + `add_embeddings` (batched, sets `metadata["embedding"]`)
- [src/financial_advisor/ingestion/schema.py](src/financial_advisor/ingestion/schema.py) — Cypher `CREATE CONSTRAINT` / `CREATE INDEX` statements, one `apply_*_schema()` function per module (`apply_basic_schema`, `apply_embedding_schema(dimensions)`, ...); all idempotent (`IF NOT EXISTS`)
- [src/financial_advisor/qa/baseline.py](src/financial_advisor/qa/baseline.py) — Module 1's one-shot RAG baseline (`embed_question` → `retrieve_chunks` → `build_context` → `generate_answer`); kept separate from `retrieval/`/`agent/` as the "before" side of the Module 2 comparison
- [src/financial_advisor/agent/graph.py](src/financial_advisor/agent/graph.py) — `build_agent()`: compiles the Module 2 agentic retrieval loop (5-node `StateGraph`: `retriever_strategy` → `call_tools` → `evaluate_retrieval` ⇄ retry, then `generate_answer` → `evaluate_answer` ⇄ retry-answer/retry-retrieval/end). `agent/nodes.py` holds the node functions (each callable standalone), `agent/state.py` the `AgentState` TypedDict plus the `RetrievalGrade`/`AnswerGrade` structured-output schemas, `agent/tools.py` the three retrieval tools (`semantic_search`, `fulltext_search`, `get_document_pages`) wrapping `retrieval/vector.py`/`keyword.py`/`graph_nav.py` — all on `services.neo4j_service`/`embedding_service`, matching Module 1
- [src/financial_advisor/extraction/validators.py](src/financial_advisor/extraction/validators.py) — Pydantic output schemas shared across extraction and tests
- [src/financial_advisor/text2cypher/validator.py](src/financial_advisor/text2cypher/validator.py) — write-operation guardrails for generated Cypher

**Graph schema (cumulative):**
- Module 1: `Company`, `Document`, `Chunk` (with `Chunk.embedding`) + fulltext index (`apply_basic_schema`) + vector index on `Chunk.embedding` sized to `embedding_service.dimensions` (`apply_embedding_schema`). A vector index's dimension can't change in place — switching embedding models means dropping `chunk_embedding` before recreating it (see the guard cell in `notebooks/module_01_baseline.ipynb`, section 2).
- Module 3 adds: `Person`, `Event`, `Article`; relationships `ROLE_AT`, `MENTIONED_IN` (constants exist in `schema.py` as `CONSTRAINTS_M3`/`INDEXES_M3`, not yet wired into an `apply_enrichment_schema()`)
- Module 4 adds: dynamically extracted entities and relationships (types vary)
- Module 5 adds: `SIMILAR_TO` edges between `Chunk` nodes

## Slides

Course slides are authored in **Marp** (Markdown-to-slides) and live in `slides/`.
See [slides/CLAUDE.md](slides/CLAUDE.md) for the full authoring guide: theme, layouts, build commands, and naming conventions.

Quick reference:
- Theme file: `slides/themes/course-negro.css`
- Module decks: `slides/modules/module_0X_*.md`
- Copy-paste template: `slides/_template.md`
- Build to `slides/dist/`: `marp slides/modules/<file>.md --theme slides/themes/course-negro.css --allow-local-files --output slides/dist/<file>.html`

## Stack

- **LLM:** Azure OpenAI via `langchain-openai` (`AzureChatOpenAI`), through `clients.get_llm()`
- **Embeddings:** local, via `sentence-transformers` (`BAAI/bge-m3`, 1024-dim) — no external API call. Chosen over smaller models (e.g. `all-MiniLM-L6-v2`) because those cap out at 256-token inputs, well under the chunker's 4096-token chunks, and would silently truncate most chunk text.
- **Agent:** LangGraph `StateGraph`, tools defined with `@tool` decorator (see Architecture note above for the Module 2 node layout)
- **Graph DB:** Neo4j 5.x via `langchain-neo4j` and `neo4j` driver
- **PDF processing:** Docling (`HybridChunker`, `chunk_max_tokens=4096`)
- **Config:** `pydantic-settings` + `.env`

**Dev environment note:** Poetry isn't available in some sandboxed dev environments used for this project; when that's the case, verify dependency changes with `pip install` directly into `.venv` and hand-edit `pyproject.toml`, but flag that `poetry.lock` is stale and needs `poetry lock` run wherever Poetry is actually available.
