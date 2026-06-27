from langchain_core.documents import Document
from langchain_neo4j import Neo4jGraph


def write_documents(graph: Neo4jGraph, documents: list[Document], company_id: str) -> None:
    """Write chunked documents to Neo4j as (Company)-[:HAS_DOCUMENT]->(Document)-[:HAS_CHUNK]->(Chunk).

    Also computes and stores embeddings on each Chunk node.
    """
    raise NotImplementedError
