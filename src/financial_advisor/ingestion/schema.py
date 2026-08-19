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


# Module 2 — agentic retrieval needs to filter by filing year, not just company
def apply_agentic_schema(dimensions: int) -> None:
    """Backfill Chunk.year from Document.year, and upgrade chunk_embedding to a multi-property
    vector index (company_id, year) so semantic_search can pre-filter by both in-index instead
    of over-fetching and filtering in Cypher afterward. Requires Cypher 25 (Neo4j 2026.01+)."""
    result = neo4j_service.run_query(
        """
        MATCH (d:Document)-[:HAS_CHUNK]->(ch:Chunk)
        WHERE ch.year IS NULL
        SET ch.year = d.year
        RETURN count(ch) AS backfilled
        """
    )
    print(f"  [schema] backfilled year on {result[0]['backfilled']} chunk(s)")

    existing = neo4j_service.run_query(
        "SHOW INDEXES YIELD name, properties WHERE name = 'chunk_embedding' RETURN properties"
    )
    if existing and "year" in existing[0]["properties"]:
        print("  [schema] chunk_embedding already has company_id/year filters — skipping rebuild")
        return

    neo4j_service.run_query("DROP INDEX chunk_embedding IF EXISTS")
    neo4j_service.run_query(
        f"""
        CYPHER 25
        CREATE VECTOR INDEX chunk_embedding IF NOT EXISTS
        FOR (n:Chunk) ON n.embedding
        WITH [n.company_id, n.year]
        OPTIONS {{indexConfig: {{`vector.dimensions`: {dimensions},
                                  `vector.similarity_function`: 'cosine'}}}}
        """
    )
    print("  [schema] rebuilt chunk_embedding with company_id/year pre-filters")


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
