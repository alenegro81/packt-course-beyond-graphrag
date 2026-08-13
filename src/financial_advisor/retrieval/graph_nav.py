from financial_advisor.services.neo4j_service import neo4j_service


def get_document_pages(doc_id: str, pages: list[int], limit: int = 20) -> list[dict]:
    """Return chunks from specific pages of a document, ordered by position.

    Use once doc_id has already been identified from a semantic_search or fulltext_search
    hit — every chunk carries its source doc_id.
    """
    rows = neo4j_service.run_query(
        """
        MATCH (ch:Chunk {doc_id: $doc_id})
        WHERE any(p IN $pages WHERE p IN ch.pages)
        RETURN ch.id AS id, ch.text AS text, ch.doc_id AS doc_id,
               ch.company_id AS company_id, ch.idx AS idx, ch.pages AS pages, 1.0 AS score
        ORDER BY ch.idx
        LIMIT $limit
        """,
        {"doc_id": doc_id, "pages": pages, "limit": limit},
    )
    return rows
