import pytest

from financial_advisor.text2cypher.validator import validate_cypher


@pytest.mark.parametrize("query", [
    "MATCH (c:Company) RETURN c.name",
    "MATCH (p:Person)-[:CEO_OF]->(c:Company) RETURN p.name, c.name LIMIT 10",
])
def test_valid_read_queries(query):
    ok, reason = validate_cypher(query)
    assert ok, reason


@pytest.mark.parametrize("query", [
    "MATCH (c:Company) DELETE c",
    "MERGE (p:Person {name: 'Test'})",
    "MATCH (c:Company) SET c.revenue = 0",
])
def test_disallowed_write_queries(query):
    ok, _ = validate_cypher(query)
    assert not ok
