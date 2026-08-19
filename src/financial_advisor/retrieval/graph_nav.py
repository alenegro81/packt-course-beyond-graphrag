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


def get_executives(company_id: str) -> list[dict]:
    """Return people with a ROLE_AT the given company, with bio and career history elsewhere.

    career_history covers roles the same person held at *other* companies (board seats, prior
    employers) — this is what fills the gap where a 10-K names its officers but defers their
    biographical/career detail to a proxy statement that was never ingested.
    """
    rows = neo4j_service.run_query(
        """
        MATCH (p:Person)-[r:ROLE_AT]->(c:Company {id: $company_id})
        WITH p, collect({title: r.title, start: r.start, end: r.end}) AS roles
        OPTIONAL MATCH (p)-[r2:ROLE_AT]->(other:Company)
        WHERE other.id <> $company_id
        WITH p, roles, collect(
            CASE WHEN other IS NULL THEN null
                 ELSE {company: other.name, title: r2.title, start: r2.start, end: r2.end} END
        ) AS raw_history
        RETURN p.id AS id, p.name AS name, p.bio AS bio, roles,
               [x IN raw_history WHERE x IS NOT NULL] AS career_history
        """,
        {"company_id": company_id},
    )
    return rows
