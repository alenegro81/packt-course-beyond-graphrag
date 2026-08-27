import re

from financial_advisor.clients import get_llm
from financial_advisor.services.neo4j_service import neo4j_service
from financial_advisor.text2cypher.prompts import TEXT2CYPHER_SYSTEM_PROMPT, build_text2cypher_prompt
from financial_advisor.text2cypher.schema_provider import get_schema_description
from financial_advisor.text2cypher.validator import validate_cypher

_CODE_FENCE = re.compile(r"^```(?:cypher)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)


def _extract_cypher(raw: str) -> str:
    """Strip markdown code fences the LLM sometimes wraps the query in, despite being asked not to."""
    return _CODE_FENCE.sub("", raw).strip()


def generate_cypher(question: str) -> str:
    """Generate a Cypher query for the question, grounded in the current graph schema."""
    schema = get_schema_description()
    response = get_llm().invoke(
        [
            {"role": "system", "content": TEXT2CYPHER_SYSTEM_PROMPT},
            {"role": "user", "content": build_text2cypher_prompt(schema, question)},
        ]
    )
    return _extract_cypher(response.content)


def run_text_to_cypher(question: str) -> tuple[str, list[dict]]:
    """Generate, validate, and execute a Cypher query for the question.

    Raises ValueError if the generated query fails validation. Returns (cypher_query, rows) —
    rows come straight from neo4j_service.run_query, matching every other read path in this
    project.
    """
    cypher = generate_cypher(question)
    ok, reason = validate_cypher(cypher)
    if not ok:
        raise ValueError(f"Generated query failed validation: {reason}\nQuery: {cypher}")
    rows = neo4j_service.run_query(cypher)
    return cypher, rows


def text_to_cypher(question: str) -> str:
    """Translate a natural-language question to a Cypher query and execute it.

    Raises ValueError if the generated query fails validation.
    Returns the query and its results as a formatted string.
    """
    cypher, rows = run_text_to_cypher(question)
    results = "\n".join(str(row) for row in rows[:50]) if rows else "(no results)"
    return f"Query:\n{cypher}\n\nResults:\n{results}"
