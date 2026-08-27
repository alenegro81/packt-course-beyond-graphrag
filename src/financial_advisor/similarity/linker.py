from financial_advisor.services.neo4j_service import neo4j_service


def link_similar_chunks(threshold: float = 0.92, k: int = 10) -> int:
    """Create (Chunk)-[:SIMILAR_TO {score}]->(Chunk) edges between chunks whose cosine
    similarity — via the chunk_embedding vector index — is at or above `threshold`.

    Searches the whole index per chunk, not scoped to one company/document: that's what
    surfaces cross-document and cross-company duplicates (shared SEC boilerplate, the same
    paragraph repeated across a company's own filing years), not just repeats within one filing.

    `c.id < n.id` keeps exactly one directed edge per unordered pair — SIMILAR_TO is
    conceptually undirected, so query it with an undirected pattern (`(a)-[:SIMILAR_TO]-(b)`).
    Idempotent (MERGE): safe to rerun after new chunks are ingested.
    """
    rows = neo4j_service.run_query(
        """
        CYPHER 25
        MATCH (c:Chunk)
        CALL (c) {
            MATCH (n:Chunk)
            SEARCH n IN (
                VECTOR INDEX chunk_embedding FOR c.embedding
                LIMIT $k
            ) SCORE AS score
            WHERE n <> c AND score >= $threshold AND c.id < n.id
            RETURN n, score
        }
        MERGE (c)-[r:SIMILAR_TO]->(n)
        SET r.score = score
        RETURN count(r) AS n
        """,
        {"k": k, "threshold": threshold},
    )
    return rows[0]["n"]
