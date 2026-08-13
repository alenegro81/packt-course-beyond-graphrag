from financial_advisor.services.embedding_service import embedding_service
from financial_advisor.services.neo4j_service import neo4j_service


def semantic_search(query: str, k: int = 5, company_id: str | None = None) -> list[dict]:
    """Top-k Chunk nodes by cosine similarity against the chunk_embedding vector index.

    When company_id is set, over-fetches before filtering since the vector index itself
    can't be pre-filtered by property.
    """
    vector = embedding_service.embed_text(query)
    fetch_k = k * 4 if company_id else k

    where_clause = "WHERE node.company_id = $company_id\n        " if company_id else ""
    rows = neo4j_service.run_query(
        f"""
        CALL db.index.vector.queryNodes('chunk_embedding', $fetch_k, $vector)
        YIELD node, score
        {where_clause}RETURN node.id AS id, node.text AS text, node.doc_id AS doc_id,
               node.company_id AS company_id, node.idx AS idx, node.pages AS pages, score
        ORDER BY score DESC
        LIMIT $k
        """,
        {"fetch_k": fetch_k, "k": k, "vector": vector, "company_id": company_id},
    )
    return rows
