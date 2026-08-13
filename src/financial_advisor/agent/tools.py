from langchain_core.tools import tool

from financial_advisor.retrieval import graph_nav, keyword, vector


@tool
def semantic_search(query: str, k: int = 5, company_id: str | None = None) -> list[dict]:
    """Search Chunk text by semantic similarity (embeddings).

    Best for broad, conceptual, or comparative questions, or when you're unsure of the exact
    wording used in the filing. Set company_id (e.g. "3M", "APPLE") to restrict the search to
    one company's filings once you know which one you need.
    """
    return vector.semantic_search(query, k=k, company_id=company_id)


@tool
def fulltext_search(query: str, k: int = 5, company_id: str | None = None) -> list[dict]:
    """Search Chunk text with Neo4j's Lucene full-text index.

    Best once you know the exact terminology (line items, section titles). Lucene syntax:
    combine terms with AND/OR, use ~ for single-word fuzzy matching (e.g. "research~ AND
    development~"). Phrase fuzzy matching ("some phrase"~) is not supported. Set company_id
    to restrict the search to one company's filings.
    """
    return keyword.fulltext_search(query, k=k, company_id=company_id)


@tool
def get_document_pages(doc_id: str, pages: list[int], limit: int = 20) -> list[dict]:
    """Retrieve chunks from specific pages of a document, given its doc_id.

    Use only after doc_id has already been identified from a previous semantic_search or
    fulltext_search result — every returned chunk carries its source doc_id. Useful for
    pulling the full surrounding context around a promising hit.
    """
    return graph_nav.get_document_pages(doc_id, pages, limit=limit)


TOOLS = [semantic_search, fulltext_search, get_document_pages]
TOOLS_BY_NAME = {t.name: t for t in TOOLS}
