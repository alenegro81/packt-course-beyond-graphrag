from financial_advisor.services.embedding_service import embedding_service
from financial_advisor.services.neo4j_service import neo4j_service


def semantic_search(
    query: str, k: int = 5, company_id: str | None = None, year: int | None = None
) -> list[dict]:
    """Top-k Chunk nodes by cosine similarity against the chunk_embedding vector index.

    company_id/year are pre-filtered inside the index itself (chunk_embedding is a
    multi-property vector index — see ingestion.schema.apply_agentic_schema), not
    over-fetched and filtered afterward in Cypher.
    """
    vector = embedding_service.embed_text(query)
    conditions: list[str] = []
    params: dict[str, object] = {"vector": vector, "k": k}
    if company_id:
        conditions.append("n.company_id = $company_id")
        params["company_id"] = company_id
    if year:
        conditions.append("n.year = $year")
        params["year"] = year
    where = f"WHERE {' AND '.join(conditions)}\n            " if conditions else ""

    rows = neo4j_service.run_query(
        f"""
        CYPHER 25
        MATCH (n)
        SEARCH n IN (
            VECTOR INDEX chunk_embedding FOR $vector
            {where}LIMIT $k
        ) SCORE AS score
        RETURN n.id AS id, n.text AS text, n.doc_id AS doc_id, n.company_id AS company_id,
               n.year AS year, n.idx AS idx, n.pages AS pages, score
        ORDER BY score DESC
        """,
        params,
    )
    return rows
