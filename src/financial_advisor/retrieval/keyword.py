from langchain_core.documents import Document
from langchain_neo4j import Neo4jGraph


def keyword_search(graph: Neo4jGraph, query: str, k: int = 5) -> list[Document]:
    """Full-text search over Chunk.text using the Neo4j Lucene index."""
    raise NotImplementedError
