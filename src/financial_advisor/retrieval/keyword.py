from financial_advisor.services.neo4j_service import neo4j_service


def fulltext_search(query: str, k: int = 5, company_id: str | None = None) -> list[dict]:
    """Top-k Chunk nodes via the chunk_text Lucene fulltext index.

    `query` uses Lucene syntax (AND/OR, ~ for single-word fuzzy matching). When company_id
    is set, over-fetches before filtering since the fulltext index can't be pre-filtered
    by property either.
    """
    fetch_k = k * 4 if company_id else k

    where_clause = "WHERE node.company_id = $company_id\n        " if company_id else ""
    rows = neo4j_service.run_query(
        f"""
        CALL db.index.fulltext.queryNodes('chunk_text', $query, {{limit: $fetch_k}})
        YIELD node, score
        {where_clause}RETURN node.id AS id, node.text AS text, node.doc_id AS doc_id,
               node.company_id AS company_id, node.idx AS idx, node.pages AS pages, score
        ORDER BY score DESC
        LIMIT $k
        """,
        {"query": query, "fetch_k": fetch_k, "k": k, "company_id": company_id},
    )
    return rows
