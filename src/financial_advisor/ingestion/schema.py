# Graph schema applied incrementally across modules.
# Run apply_schema() after each module introduces new node/relationship types.

from neo4j import Driver

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


def apply_schema(driver: Driver, module: int = 1) -> None:
    constraints = CONSTRAINTS_M1
    indexes = INDEXES_M1
    if module >= 3:
        constraints = constraints + CONSTRAINTS_M3
        indexes = indexes + INDEXES_M3

    with driver.session() as session:
        for stmt in constraints + indexes:
            session.run(stmt)
