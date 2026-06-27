from langchain_core.tools import tool

from financial_advisor.retrieval import graph_nav, keyword, vector


@tool
def semantic_search(query: str) -> str:
    """Search for information using semantic similarity over document chunks."""
    raise NotImplementedError


@tool
def fulltext_search(query: str) -> str:
    """Search for information using keyword/fulltext matching over document chunks."""
    raise NotImplementedError


@tool
def get_company_documents(company_id: str) -> str:
    """List all filings available for a given company."""
    raise NotImplementedError


@tool
def get_context_around_chunk(chunk_id: str) -> str:
    """Retrieve the chunks immediately before and after a given chunk for richer context."""
    raise NotImplementedError


# Module 3+ tools added in enrichment/tools.py and text2cypher/chain.py
