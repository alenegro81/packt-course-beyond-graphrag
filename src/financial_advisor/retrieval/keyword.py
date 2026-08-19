from financial_advisor.services.neo4j_service import neo4j_service


def fulltext_search(
    query: str, k: int = 5, company_id: str | None = None, year: int | None = None
) -> list[dict]:
    """Top-k Chunk nodes via the chunk_text Lucene fulltext index.

    `query` uses Lucene syntax (AND/OR, ~ for single-word fuzzy matching). When company_id
    and/or year are set, over-fetches before filtering — full-text (Lucene) indexes don't
    support in-index pre-filtering by property the way the vector index does.
    """
    conditions: list[str] = []
    params: dict[str, object] = {"query": query, "k": k}
    if company_id:
        conditions.append("node.company_id = $company_id")
        params["company_id"] = company_id
    if year:
        conditions.append("node.year = $year")
        params["year"] = year
    fetch_k = k * 4 if conditions else k
    where = f"WHERE {' AND '.join(conditions)}\n        " if conditions else ""
    params["fetch_k"] = fetch_k

    rows = neo4j_service.run_query(
        f"""
        CALL db.index.fulltext.queryNodes('chunk_text', $query, {{limit: $fetch_k}})
        YIELD node, score
        {where}RETURN node.id AS id, node.text AS text, node.doc_id AS doc_id,
               node.company_id AS company_id, node.year AS year, node.idx AS idx,
               node.pages AS pages, score
        ORDER BY score DESC
        LIMIT $k
        """,
        params,
    )
    return rows
