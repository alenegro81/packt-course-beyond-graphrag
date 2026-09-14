import re

from neo4j.exceptions import CypherSyntaxError


DISALLOWED_PATTERNS = [
    r"\bDELETE\b",
    r"\bDETACH\b",
    r"\bDROP\b",
    r"\bCREATE\b",
    r"\bMERGE\b",
    r"\bSET\b",
    r"\bREMOVE\b",
]


def validate_cypher(query: str) -> tuple[bool, str]:
    """Return (is_valid, reason). Blocks write operations and checks for dangerous patterns."""
    for pattern in DISALLOWED_PATTERNS:
        if re.search(pattern, query, re.IGNORECASE):
            return False, f"Query contains disallowed operation: {pattern}"
    return True, ""
