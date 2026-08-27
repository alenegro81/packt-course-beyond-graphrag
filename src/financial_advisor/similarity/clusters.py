import uuid

from financial_advisor.services.neo4j_service import neo4j_service


def detect_topic_clusters(threshold: float = 0.75, k: int = 15) -> list[dict]:
    """Louvain community detection over an ephemeral, denser similarity graph.

    Deliberately NOT the precomputed SIMILAR_TO edges from linker.py — those are thresholded
    for near-duplicate detection (0.92), and a graph built at that threshold is sparse enough
    that Louvain communities collapse to plain connected components (empirically confirmed in
    module_05's notebook: both find the same 450 components/communities). This function builds
    its own lower-threshold graph via Neo4j GDS's Cypher projection, runs Louvain on it, and
    drops the projection when done — nothing is written to the stored graph.

    Returns one row per community: id, size, member company_id(s), and member chunk ids, largest
    first. Exploratory only — not wired into retrieval; see adr/0009 for the full rationale and
    what a production version would need.
    """
    graph_name = f"chunk-topics-{uuid.uuid4().hex[:8]}"
    try:
        neo4j_service.run_query(
            """
            CYPHER 25
            MATCH (c:Chunk)
            CALL (c) {
                MATCH (n:Chunk)
                SEARCH n IN (
                    VECTOR INDEX chunk_embedding FOR c.embedding
                    LIMIT $k
                ) SCORE AS score
                WHERE n <> c AND score >= $threshold AND c.id < n.id
                RETURN n, score
            }
            WITH gds.graph.project(
                $graph_name, c, n,
                {relationshipProperties: {score: score}},
                {undirectedRelationshipTypes: ['*']}
            ) AS g
            RETURN g.graphName AS graphName
            """,
            {"k": k, "threshold": threshold, "graph_name": graph_name},
        )

        return neo4j_service.run_query(
            """
            CALL gds.louvain.stream($graph_name, {relationshipWeightProperty: 'score'})
            YIELD nodeId, communityId
            WITH communityId, gds.util.asNode(nodeId) AS n
            WITH communityId,
                 count(*) AS size,
                 collect(DISTINCT n.company_id) AS companies,
                 collect(n.id) AS chunk_ids
            RETURN communityId AS id, size, companies, chunk_ids
            ORDER BY size DESC
            """,
            {"graph_name": graph_name},
        )
    finally:
        neo4j_service.run_query(
            "CALL gds.graph.drop($graph_name, false) YIELD graphName RETURN graphName",
            {"graph_name": graph_name},
        )
