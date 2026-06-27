# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Packt course: **Beyond GraphRAG — Building an Explainable Financial Advisor with Knowledge Graphs, Neo4j, and LLM Agents**. The project ingests corporate filings (10-Ks), news, and executive data into a Neo4j knowledge graph, then answers complex financial questions via a LangGraph agentic retrieval loop.

## Setup

```bash
poetry install
cp .env.example .env   # fill in Azure OpenAI and Neo4j credentials
```

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
PDFs → ingestion/ → Neo4j (Company→Document→Chunk)   [Module 1]
                 → retrieval/ + agent/                 [Module 2]
                 → enrichment/ (Person, Event, Article) [Module 3]
                 → extraction/ (LLM entities/rels)      [Module 4]
                 → similarity/ (SIMILAR_TO, merge)      [Module 5]
                 → text2cypher/ (NL→Cypher tool)        [Module 6]
                 → evaluation/ (LLM-as-judge)           [Module 7]
```

All modules operate on the **same Neo4j database**, which grows incrementally. Run scripts in order; intermediate results are persisted so long-running steps don't need to be repeated.

**Key files:**
- [src/financial_advisor/config.py](src/financial_advisor/config.py) — Pydantic Settings loading `.env`
- [src/financial_advisor/clients.py](src/financial_advisor/clients.py) — cached factories for `AzureChatOpenAI`, `AzureOpenAIEmbeddings`, `Neo4jGraph`
- [src/financial_advisor/ingestion/schema.py](src/financial_advisor/ingestion/schema.py) — all Cypher `CREATE CONSTRAINT` / `CREATE INDEX` statements, versioned by module
- [src/financial_advisor/agent/graph.py](src/financial_advisor/agent/graph.py) — LangGraph `StateGraph` definition (ReAct loop)
- [src/financial_advisor/extraction/validators.py](src/financial_advisor/extraction/validators.py) — Pydantic output schemas shared across extraction and tests
- [src/financial_advisor/text2cypher/validator.py](src/financial_advisor/text2cypher/validator.py) — write-operation guardrails for generated Cypher

**Graph schema (cumulative):**
- Module 1: `Company`, `Document`, `Chunk` + vector index on `Chunk.embedding`
- Module 3 adds: `Person`, `Event`, `Article`; relationships `ROLE_AT`, `MENTIONED_IN`
- Module 4 adds: dynamically extracted entities and relationships (types vary)
- Module 5 adds: `SIMILAR_TO` edges between `Chunk` nodes

## Stack

- **LLM / embeddings:** Azure OpenAI via `langchain-openai` (`AzureChatOpenAI`, `AzureOpenAIEmbeddings`)
- **Agent:** LangGraph `StateGraph` (ReAct pattern), tools defined with `@tool` decorator
- **Graph DB:** Neo4j 5.x via `langchain-neo4j` and `neo4j` driver
- **PDF processing:** Docling
- **Config:** `pydantic-settings` + `.env`
