from langchain_neo4j import Neo4jGraph

from financial_advisor.clients import get_llm
from financial_advisor.text2cypher.schema_provider import get_schema_description
from financial_advisor.text2cypher.validator import validate_cypher


def text_to_cypher(question: str, graph: Neo4jGraph) -> str:
    """Translate a natural-language question to a Cypher query and execute it.

    Raises ValueError if the generated query fails validation.
    Returns the raw query results as a formatted string.
    """
    raise NotImplementedError
