from langchain_neo4j import Neo4jGraph


def get_schema_description(graph: Neo4jGraph) -> str:
    """Return a formatted description of the current graph schema for use in prompts."""
    return graph.schema
