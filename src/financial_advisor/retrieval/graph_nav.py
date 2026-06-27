from langchain_neo4j import Neo4jGraph


def get_company_filings(graph: Neo4jGraph, company_id: str) -> list[dict]:
    """Return all Document nodes linked to a Company."""
    raise NotImplementedError


def get_chunks_around(graph: Neo4jGraph, chunk_id: str, window: int = 2) -> list[dict]:
    """Return chunks adjacent (by position) to a given chunk — useful for context expansion."""
    raise NotImplementedError
