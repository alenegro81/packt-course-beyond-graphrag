# Graph schema applied incrementally across modules.
# Run apply_schema() after each module introduces new node/relationship types.

from financial_advisor.services.neo4j_service import neo4j_service


# Module 1 — document graph baseline
CONSTRAINTS_M1 = [
    "CREATE CONSTRAINT company_id IF NOT EXISTS FOR (n:Company) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT document_id IF NOT EXISTS FOR (n:Document) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT chunk_id IF NOT EXISTS FOR (n:Chunk) REQUIRE n.id IS UNIQUE",
]

INDEXES_M1 = [
    "CREATE FULLTEXT INDEX chunk_text IF NOT EXISTS FOR (n:Chunk) ON EACH [n.text]",
    (
        "CREATE VECTOR INDEX chunk_embedding IF NOT EXISTS FOR (n:Chunk) ON n.embedding "
        "OPTIONS {indexConfig: {`vector.dimensions`: 1536, `vector.similarity_function`: 'cosine'}}"
    ),
]

# Module 3 — people, events, news
CONSTRAINTS_M3 = [
    "CREATE CONSTRAINT person_id IF NOT EXISTS FOR (n:Person) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT event_id IF NOT EXISTS FOR (n:Event) REQUIRE n.id IS UNIQUE",
    "CREATE CONSTRAINT article_id IF NOT EXISTS FOR (n:Article) REQUIRE n.id IS UNIQUE",
]

INDEXES_M3 = [
    "CREATE FULLTEXT INDEX article_text IF NOT EXISTS FOR (n:Article) ON EACH [n.title, n.text]",
]


def apply_schema(module: int = 1) -> None:
    constraints = CONSTRAINTS_M1
    indexes = INDEXES_M1
    if module >= 3:
        constraints = constraints + CONSTRAINTS_M3
        indexes = indexes + INDEXES_M3

    statements = constraints + indexes
    ok: int = 0
    failed: list[str] = []

    for stmt in statements:
        name = stmt.split("IF NOT EXISTS")[0].strip().split()[-1]
        try:
            neo4j_service.run_query(stmt)  # type: ignore[arg-type]
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
