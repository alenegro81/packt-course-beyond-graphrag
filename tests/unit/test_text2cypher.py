from unittest.mock import MagicMock, patch

import pytest

from financial_advisor.text2cypher.chain import generate_cypher, run_text_to_cypher, text_to_cypher
from financial_advisor.text2cypher.schema_provider import get_schema_description
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
    "CREATE (n:Malicious {x: 1}) RETURN n",
])
def test_disallowed_write_queries(query):
    ok, _ = validate_cypher(query)
    assert not ok


def _mock_schema_procedures(cypher: str, *_args, **_kwargs):
    if "nodeTypeProperties" in cypher:
        return [
            {"nodeLabels": ["Chunk"], "propertyName": "id", "propertyTypes": ["String"], "mandatory": True},
            {"nodeLabels": ["Chunk"], "propertyName": "embedding", "propertyTypes": ["DoubleArray"], "mandatory": True},
            {"nodeLabels": ["Company"], "propertyName": "id", "propertyTypes": ["String"], "mandatory": True},
            {"nodeLabels": ["Company"], "propertyName": "name", "propertyTypes": ["String"], "mandatory": False},
        ]
    if "relTypeProperties" in cypher:
        return [
            {"relType": ":`ROLE_AT`", "propertyName": "title", "propertyTypes": ["String"], "mandatory": True},
            {"relType": ":`ROLE_AT`", "propertyName": "end", "propertyTypes": ["String"], "mandatory": False},
            {"relType": ":`HAS_CHUNK`", "propertyName": None, "propertyTypes": None, "mandatory": False},
        ]
    if "visualization" in cypher:
        return [
            {
                "relationships": [
                    ({"name": "Person"}, "ROLE_AT", {"name": "Company"}),
                    ({"name": "Document"}, "HAS_CHUNK", {"name": "Chunk"}),
                ]
            }
        ]
    raise AssertionError(f"unexpected schema-introspection query: {cypher}")


@patch("financial_advisor.text2cypher.schema_provider.neo4j_service")
def test_schema_description_excludes_embedding_and_shows_patterns(mock_neo4j):
    mock_neo4j.run_query.side_effect = _mock_schema_procedures

    schema = get_schema_description()

    assert "embedding" not in schema
    assert "(:Chunk {id: String})" in schema
    assert "[:ROLE_AT {title: String, end: String?}]" in schema
    assert "(:Person)-[:ROLE_AT {title: String, end: String?}]->(:Company)" in schema
    assert "(:Document)-[:HAS_CHUNK]->(:Chunk)" in schema


@patch("financial_advisor.text2cypher.schema_provider.neo4j_service")
def test_schema_description_marks_optional_properties(mock_neo4j):
    mock_neo4j.run_query.side_effect = _mock_schema_procedures

    schema = get_schema_description()

    # Company.id is mandatory (present on every sampled Company) — no `?`.
    assert "id: String," in schema
    assert "id: String?" not in schema
    # Company.name and ROLE_AT.end are not mandatory — flagged `?` so the LLM treats them as
    # nullable instead of assuming every node/relationship has them set.
    assert "name: String?" in schema
    assert "end: String?" in schema


def _mock_llm(content: str) -> MagicMock:
    llm = MagicMock()
    llm.invoke.return_value = MagicMock(content=content)
    return llm


@patch("financial_advisor.text2cypher.chain.get_schema_description", return_value="(schema)")
@patch("financial_advisor.text2cypher.chain.get_llm")
def test_generate_cypher_strips_code_fences(mock_get_llm, _mock_schema):
    mock_get_llm.return_value = _mock_llm("```cypher\nMATCH (c:Company) RETURN c.name\n```")
    cypher = generate_cypher("How many companies?")
    assert cypher == "MATCH (c:Company) RETURN c.name"


@patch("financial_advisor.text2cypher.chain.neo4j_service")
@patch("financial_advisor.text2cypher.chain.get_schema_description", return_value="(schema)")
@patch("financial_advisor.text2cypher.chain.get_llm")
def test_run_text_to_cypher_executes_valid_query(mock_get_llm, _mock_schema, mock_neo4j):
    mock_get_llm.return_value = _mock_llm("MATCH (c:Company) RETURN c.name AS name")
    mock_neo4j.run_query.return_value = [{"name": "3M"}, {"name": "Apple"}]

    cypher, rows = run_text_to_cypher("List companies")

    assert cypher == "MATCH (c:Company) RETURN c.name AS name"
    assert rows == [{"name": "3M"}, {"name": "Apple"}]
    mock_neo4j.run_query.assert_called_once_with(cypher)


@patch("financial_advisor.text2cypher.chain.neo4j_service")
@patch("financial_advisor.text2cypher.chain.get_schema_description", return_value="(schema)")
@patch("financial_advisor.text2cypher.chain.get_llm")
def test_run_text_to_cypher_rejects_write_query(mock_get_llm, _mock_schema, mock_neo4j):
    mock_get_llm.return_value = _mock_llm("MATCH (c:Company) DELETE c")

    with pytest.raises(ValueError, match="failed validation"):
        run_text_to_cypher("Delete all companies")

    mock_neo4j.run_query.assert_not_called()


@patch("financial_advisor.text2cypher.chain.run_text_to_cypher")
def test_text_to_cypher_formats_results(mock_run):
    mock_run.return_value = ("MATCH (c:Company) RETURN c.name AS name", [{"name": "3M"}])
    formatted = text_to_cypher("List companies")
    assert "MATCH (c:Company) RETURN c.name AS name" in formatted
    assert "3M" in formatted


@patch("financial_advisor.text2cypher.chain.run_text_to_cypher")
def test_text_to_cypher_handles_no_results(mock_run):
    mock_run.return_value = ("MATCH (c:Company) WHERE c.name = 'Nope' RETURN c", [])
    formatted = text_to_cypher("Find Nope")
    assert "no results" in formatted.lower()
