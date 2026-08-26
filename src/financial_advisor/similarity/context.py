from financial_advisor.services.neo4j_service import neo4j_service
from financial_advisor.similarity.candidates import node_match_clause
from financial_advisor.similarity.validators import CandidateNode

# Chunk/Document neighbors are bulky (full text) and low-signal for "is this the same entity" —
# excluded from the generic 1-hop scan; filing provenance is fetched separately instead (below).
_EXCLUDED_NEIGHBOR_LABELS = ["Chunk", "Document"]


def fetch_entity_context(node: CandidateNode) -> dict:
    """Enrich a candidate node into the JSON handed to the LLM: its own properties, its 1-hop
    graph neighborhood (any relationship type, either direction), and — for extracted mentions
    only — a 2-hop bridge to whichever Company's filing it was mentioned in. This is what lets
    the resolution judgment lean on graph context instead of name similarity alone."""
    match_clause, params = node_match_clause(node)

    own_row = neo4j_service.run_query(f"{match_clause} RETURN properties(n) AS props", params)[0]
    own_properties = own_row["props"]
    own_properties.pop("embedding", None)

    neighbors = neo4j_service.run_query(
        f"""
        {match_clause}
        OPTIONAL MATCH (n)-[r]-(m)
        WHERE NOT any(l IN labels(m) WHERE l IN $excluded)
        WITH DISTINCT type(r) AS relationship,
             CASE WHEN startNode(r) = n THEN 'out' ELSE 'in' END AS direction,
             labels(m)[0] AS node_label,
             coalesce(m.string, m.name, m.id) AS name,
             m.type AS node_type
        WHERE relationship IS NOT NULL
        RETURN relationship, direction, node_label, name, node_type
        LIMIT 10
        """,
        {**params, "excluded": _EXCLUDED_NEIGHBOR_LABELS},
    )

    filed_in_filings_of: list[str] = []
    if node.label == "RecognisedEntity":
        filed_in_filings_of = [
            row["company_id"]
            for row in neo4j_service.run_query(
                f"""
                {match_clause}
                MATCH (n)-[:MENTIONED_IN]->(:Chunk)<-[:HAS_CHUNK]-(:Document)<-[:HAS_DOCUMENT]-(c:Company)
                RETURN DISTINCT c.id AS company_id
                LIMIT 3
                """,
                params,
            )
        ]

    return {
        "name": node.name,
        "type": node.entity_type.value,
        "source": node.label,
        "own_properties": own_properties,
        "neighbors": neighbors,
        "filed_in_filings_of": filed_in_filings_of,
    }
