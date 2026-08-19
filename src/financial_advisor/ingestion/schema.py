# Graph schema applied incrementally across modules.
# Each module gets its own apply_*_schema() function; call the ones for the
# modules you've reached so far (they're all safe to re-run, IF NOT EXISTS).

from financial_advisor.services.neo4j_service import neo4j_service


def _run_statements(statements: list[str]) -> None:
    ok: int = 0
    failed: list[str] = []

    for stmt in statements:
        name = stmt.split("IF NOT EXISTS")[0].strip().split()[-1]
        try:
            neo4j_service.run_query(stmt)
            print(f"  [schema] OK  {name}")
            ok += 1
        except Exception as exc:
            print(f"  [schema] ERR {name}: {exc}")
            failed.append(name)

    print(f"[schema] {ok}/{len(statements)} statements applied", end="")
    if failed:
        print(f" — {len(failed)} failed: {failed}")
    else:
        print(" — all good")


# Module 1 — document graph baseline
CONSTRAINTS_M1 = [
    "CREATE CONSTRAINT company_id IF NOT EXISTS FOR (n:Company) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT document_id IF NOT EXISTS FOR (n:Document) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT chunk_id IF NOT EXISTS FOR (n:Chunk) REQUIRE n.id IS UNIQUE",
]

INDEXES_M1 = [
    "CREATE FULLTEXT INDEX chunk_text IF NOT EXISTS FOR (n:Chunk) ON EACH [n.text]",
]


def apply_basic_schema() -> None:
    """Constraints + fulltext index for the Module 1 document graph."""
    _run_statements(CONSTRAINTS_M1 + INDEXES_M1)


def apply_embedding_schema(dimensions: int) -> None:
    """Vector index on Chunk.embedding, sized to the embedding model in use."""
    statement = (
        "CREATE VECTOR INDEX chunk_embedding IF NOT EXISTS FOR (n:Chunk) ON n.embedding "
        f"OPTIONS {{indexConfig: {{`vector.dimensions`: {dimensions}, "
        "`vector.similarity_function`: 'cosine'}}"
    )
    _run_statements([statement])


# Module 3 — people, events, news
CONSTRAINTS_M3 = [
    "CREATE CONSTRAINT person_id IF NOT EXISTS FOR (n:Person) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT event_id IF NOT EXISTS FOR (n:Event) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT article_id IF NOT EXISTS FOR (n:Article) REQUIRE n.id IS UNIQUE",
]

INDEXES_M3 = [
    "CREATE FULLTEXT INDEX article_text IF NOT EXISTS FOR (n:Article) ON EACH [n.title, n.text]",
]


def apply_enrichment_schema() -> None:
    """Constraints + fulltext index for the Module 3 people/events/news additions."""
    _run_statements(CONSTRAINTS_M3 + INDEXES_M3)
