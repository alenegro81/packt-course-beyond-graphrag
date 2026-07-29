# Beyond GraphRAG
### Building an Explainable Financial Advisor with Knowledge Graphs, Neo4j, and LLM Agents

A Packt course companion repository. You will ingest real corporate filings (10-Ks), enrich them with news and executive data, and answer complex financial questions through a LangGraph agentic retrieval loop backed by a Neo4j knowledge graph.

---

## What you will build

| Module | What gets built | New graph elements |
|--------|----------------|-------------------|
| 1 — Baseline | PDF ingestion with Docling → vector RAG baseline | `Company → Document → Chunk` |
| 2 — Agentic RAG | LangGraph ReAct loop, multi-tool retrieval | — |
| 3 — Enrichment | People, events, news articles loaded from external data | `Person`, `Event`, `Article` |
| 4 — LLM Extraction | Named entity + relationship extraction over every chunk | Dynamic entity/rel types |
| 5 — Similarity | Embedding-based chunk linking, entity resolution | `SIMILAR_TO` edges |
| 6 — Text2Cypher | Natural-language → Cypher query tool | — |
| 7 — Evaluation | LLM-as-judge scoring pipeline | — |

Each module has a companion notebook in `notebooks/` and a runnable script in `scripts/`. All modules share the **same Neo4j database**, which grows incrementally — run the scripts in order.

---

## Prerequisites

| Requirement | Minimum version | Notes |
|-------------|----------------|-------|
| Python | 3.11 | 3.12 also works |
| Neo4j | 5.x | Docker image or Neo4j Aura (free tier works) |
| Azure OpenAI | — | You need a deployment for `gpt-4o` and `text-embedding-3-small` (or `ada-002`) |

---

## Setup

### 1. Clone the repository

```bash
git clone <repo-url>
cd packt-course-beyond-graphrag
```

### 2. Create and activate a Python virtual environment

Using the standard library `venv` module:

```bash
python3.11 -m venv .venv
```

Activate it — the command differs by shell and OS:

```bash
# macOS / Linux (bash or zsh)
source .venv/bin/activate

# Windows — Command Prompt
.venv\Scripts\activate.bat

# Windows — PowerShell
.venv\Scripts\Activate.ps1
```

Your prompt should now show `(.venv)` to confirm the environment is active. All subsequent commands in this guide assume the environment is active.

### 3. Install Poetry

Poetry manages the project's dependencies and keeps the package installable as a local library. Install it into the virtual environment you just activated:

```bash
pip install poetry
```

Verify the installation:

```bash
poetry --version
# Poetry (version 2.4.x or newer)
```

> **Why Poetry and not plain `pip install -r requirements.txt`?**  
> The course source code lives in `src/financial_advisor/` and is imported as a proper package across notebooks and scripts. Poetry handles the editable install automatically, so any change you make to the source is immediately available without reinstalling.

### 4. Install project dependencies

```bash
poetry install
```

This reads `pyproject.toml`, resolves all dependencies (LangChain, LangGraph, Docling, Neo4j driver, etc.), and installs them into the active virtual environment. It also installs the `financial_advisor` package itself in editable mode.

The first run may take a few minutes — Docling bundles ML models for PDF layout analysis that are downloaded on first use.

### 5. Configure environment variables

Copy the example file and fill in your credentials:

```bash
cp .env.example .env
```

Open `.env` and replace the placeholder values:

```ini
# Azure OpenAI — find these in the Azure Portal under your OpenAI resource
AZURE_OPENAI_API_KEY=your-api-key-here
AZURE_OPENAI_ENDPOINT=https://your-resource-name.openai.azure.com/
AZURE_OPENAI_API_VERSION=2024-08-01-preview

# The names of the deployments you created in Azure AI Studio
AZURE_OPENAI_CHAT_DEPLOYMENT=gpt-4o
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-small

# Neo4j connection — see the Neo4j section below
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your-password
```

> **Embedding dimensions:** if you use `text-embedding-3-small` or `text-embedding-ada-002` the vector index is pre-configured for 1536 dimensions. If you switch to `text-embedding-3-large` (3072 dimensions) update the `INDEXES_M1` entry in `src/financial_advisor/ingestion/schema.py` before running Module 1.

### 6. Start Neo4j

**Option A — Docker (recommended for local development):**

```bash
docker run \
  --name neo4j-course \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/your-password \
  -e NEO4J_PLUGINS='["apoc"]' \
  neo4j:5
```

The browser UI is available at `http://localhost:7474`. Set `NEO4J_URI=bolt://localhost:7687` in your `.env`.

**Option B — Neo4j Aura (cloud, free tier):**

1. Create a free instance at [console.neo4j.io](https://console.neo4j.io)
2. Download the connection credentials file when prompted
3. Set `NEO4J_URI` to the `bolt+s://` URI shown in the console, and update `NEO4J_USERNAME` / `NEO4J_PASSWORD` accordingly

---

## Running the course

### Place your filings

Put PDF filings in `data/filings/` using the naming convention `{COMPANY}_{YEAR}_10K.pdf`:

```
data/filings/
  APPLE_2018_10K.pdf
  APPLE_2019_10K.pdf
  3M_2018_10K.pdf
```

### Module 1 — Ingest filings and build the document graph

```bash
python scripts/ingest_filings.py data/filings/
```

This applies the baseline Neo4j schema (constraints + vector index), converts each PDF with Docling, splits it into chunks, embeds each chunk with Azure OpenAI, and writes the `Company → Document → Chunk` graph.

### Module 2 — Explore agentic retrieval

Open `notebooks/module_02_agentic.ipynb`. No new ingestion script; the notebook exercises the LangGraph agent against the graph built in Module 1.

### Module 3 — Enrich with people, events, and news

```bash
python scripts/ingest_enrichment.py
```

### Module 4 — LLM entity and relationship extraction

```bash
python scripts/run_extraction.py
```

This is the longest-running step — it calls the LLM once per chunk.

### Module 5 — Similarity linking and entity resolution

```bash
python scripts/run_similarity.py
```

### Modules 6 & 7 — Text2Cypher and Evaluation

Covered entirely in their respective notebooks; no additional scripts needed.

---

## Running the tests

```bash
# Unit tests — no Neo4j required
pytest tests/unit/

# End-to-end tests — requires a running Neo4j instance with ingested data
pytest tests/e2e/ -v

# Single test
pytest tests/unit/test_text2cypher.py::test_disallowed_write_queries -v
```

---

## Linting

```bash
ruff check src/ tests/ scripts/
```

---

## Project layout

```
.
├── data/
│   └── filings/          # Drop 10-K PDFs here
├── notebooks/            # One notebook per module (teaching entry points)
├── scripts/              # Runnable ingestion and processing scripts
├── src/
│   └── financial_advisor/
│       ├── config.py         # Pydantic Settings — reads .env
│       ├── clients.py        # Cached factories: LLM, embeddings, Neo4j
│       ├── ingestion/        # Module 1: PDF → graph
│       ├── retrieval/        # Module 2: vector, keyword, graph traversal
│       ├── enrichment/       # Module 3: people, events, articles
│       ├── extraction/       # Module 4: LLM entity/relationship extraction
│       ├── similarity/       # Module 5: SIMILAR_TO edges, entity merge
│       ├── text2cypher/      # Module 6: NL → Cypher tool
│       └── evaluation/       # Module 7: LLM-as-judge
└── tests/
    ├── unit/             # Fast, no external services
    └── e2e/              # Require Neo4j + ingested data
```
