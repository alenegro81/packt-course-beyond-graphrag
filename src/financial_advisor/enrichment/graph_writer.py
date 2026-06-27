from langchain_neo4j import Neo4jGraph


def write_executives(graph: Neo4jGraph, company_id: str, executives: list[dict]) -> None:
    """Upsert Person nodes and (Person)-[:ROLE_AT {title, start, end}]->(Company) relationships."""
    raise NotImplementedError


def write_news(graph: Neo4jGraph, company_id: str, articles: list[dict]) -> None:
    """Upsert Article nodes and link them to the relevant Company."""
    raise NotImplementedError
