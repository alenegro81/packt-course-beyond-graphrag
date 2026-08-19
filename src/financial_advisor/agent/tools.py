from langchain_core.tools import tool

from financial_advisor.retrieval import graph_nav, keyword, vector


@tool
def semantic_search(
    query: str, k: int = 5, company_id: str | None = None, year: int | None = None
) -> list[dict]:
    """Search Chunk text by semantic similarity (embeddings).

    Best for broad, conceptual, or comparative questions, or when you're unsure of the exact
    wording used in the filing. Set company_id (e.g. "3M", "APPLE") to restrict the search to
    one company's filings once you know which one you need. Set year (e.g. 2024, 2025) to
    restrict to one filing year — combine both when a company has more than one year in the
    corpus and you need to pinpoint a single filing.
    """
    return vector.semantic_search(query, k=k, company_id=company_id, year=year)


@tool
def fulltext_search(
    query: str, k: int = 5, company_id: str | None = None, year: int | None = None
) -> list[dict]:
    """Search Chunk text with Neo4j's Lucene full-text index.

    Best once you know the exact terminology (line items, section titles). Lucene syntax:
    combine terms with AND/OR, use ~ for single-word fuzzy matching (e.g. "research~ AND
    development~"). Phrase fuzzy matching ("some phrase"~) is not supported. Set company_id
    to restrict the search to one company's filings, and/or year (e.g. 2024, 2025) to restrict
    to one filing year — combine both to pinpoint a single filing.
    """
    return keyword.fulltext_search(query, k=k, company_id=company_id, year=year)


@tool
def get_document_pages(doc_id: str, pages: list[int], limit: int = 20) -> list[dict]:
    """Retrieve chunks from specific pages of a document, given its doc_id.

    Use only after doc_id has already been identified from a previous semantic_search or
    fulltext_search result — every returned chunk carries its source doc_id. Useful for
    pulling the full surrounding context around a promising hit.
    """
    return graph_nav.get_document_pages(doc_id, pages, limit=limit)


@tool
def get_executives(company_id: str) -> list[dict]:
    """Look up a company's executives and board members, with bio and career history elsewhere.

    Use for questions about a company's leadership, officers, board composition, or an
    executive's background — the 10-K filings name officers but don't carry biographical detail
    (that's deferred to the proxy statement, which isn't in this corpus). Set company_id (e.g.
    "3M", "APPLE").
    """
    return graph_nav.get_executives(company_id)


TOOLS = [semantic_search, fulltext_search, get_document_pages, get_executives]
TOOLS_BY_NAME = {t.name: t for t in TOOLS}
