from langchain_neo4j import Neo4jGraph


def link_similar_chunks(graph: Neo4jGraph, threshold: float = 0.92) -> int:
    """Create (Chunk)-[:SIMILAR_TO {score}]->(Chunk) edges for pairs above the cosine threshold.

    Returns the number of edges created.
    """
    raise NotImplementedError
