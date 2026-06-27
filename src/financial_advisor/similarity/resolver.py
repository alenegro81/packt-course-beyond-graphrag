from langchain_neo4j import Neo4jGraph


def resolve_entities(graph: Neo4jGraph) -> int:
    """Merge duplicate entity nodes (same name, compatible type) into a canonical node.

    Returns the number of nodes merged.
    """
    raise NotImplementedError
