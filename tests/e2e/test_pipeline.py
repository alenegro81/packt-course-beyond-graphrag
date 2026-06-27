"""End-to-end tests — require a running Neo4j instance and valid .env credentials.

Run with: pytest tests/e2e/ -v
"""

import pytest

from financial_advisor.clients import get_graph


@pytest.fixture(scope="module")
def graph():
    return get_graph()


def test_neo4j_connection(graph):
    result = graph.query("RETURN 1 AS n")
    assert result[0]["n"] == 1


def test_chunk_nodes_exist(graph):
    result = graph.query("MATCH (c:Chunk) RETURN count(c) AS n")
    assert result[0]["n"] > 0, "No Chunk nodes found — run scripts/ingest_filings.py first"
