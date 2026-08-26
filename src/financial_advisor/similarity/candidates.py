from rapidfuzz import fuzz, process

from financial_advisor.extraction.validators import EntityType
from financial_advisor.services.neo4j_service import neo4j_service
from financial_advisor.similarity.validators import CandidateNode

# Entity types with a curated Module 1/3 counterpart worth reconciling extracted mentions
# against. The others (Product, Location, Regulation, Risk, FinancialMetric) only ever exist as
# RecognisedEntity mentions, so their pool is extraction-only.
_CURATED_LABEL_BY_TYPE = {
    EntityType.COMPANY: "Company",
    EntityType.PERSON: "Person",
}


def node_match_clause(node: CandidateNode, var: str = "n") -> tuple[str, dict]:
    """Cypher MATCH fragment + params that re-selects this exact node from its label/key."""
    if node.label == "RecognisedEntity":
        return (
            f"MATCH ({var}:RecognisedEntity {{string: $string, doc_id: $doc_id}})",
            {"string": node.key["string"], "doc_id": node.key["doc_id"]},
        )
    return f"MATCH ({var}:{node.label} {{id: $id}})", {"id": node.key["id"]}


def fetch_candidate_pool(entity_type: EntityType) -> list[CandidateNode]:
    """All not-yet-resolved nodes of one type: extracted `RecognisedEntity` mentions, plus the
    curated `Company`/`Person` node when this type has one. 'Not yet resolved' means no outgoing
    `SAME_AS` edge to an `EntityGroup` yet, so a rerun only ever picks up new/unresolved nodes."""
    pool: list[CandidateNode] = []

    extracted = neo4j_service.run_query(
        """
        MATCH (e:RecognisedEntity {type: $type})
        WHERE NOT (e)-[:SAME_AS]->(:EntityGroup)
        RETURN e.string AS string, e.doc_id AS doc_id
        """,
        {"type": entity_type.value},
    )
    pool.extend(
        CandidateNode(
            label="RecognisedEntity",
            key={"string": row["string"], "doc_id": row["doc_id"]},
            name=row["string"],
            entity_type=entity_type,
        )
        for row in extracted
    )

    curated_label = _CURATED_LABEL_BY_TYPE.get(entity_type)
    if curated_label:
        curated = neo4j_service.run_query(
            f"""
            MATCH (n:{curated_label})
            WHERE NOT (n)-[:SAME_AS]->(:EntityGroup)
            RETURN n.id AS id, coalesce(n.name, n.id) AS name
            """
        )
        pool.extend(
            CandidateNode(label=curated_label, key={"id": row["id"]}, name=row["name"], entity_type=entity_type)
            for row in curated
        )

    return pool


def find_fuzzy_candidates(
    target: CandidateNode, pool: list[CandidateNode], threshold: float = 78.0, limit: int = 8
) -> list[CandidateNode]:
    """Narrow a same-type pool down to plausible duplicates of `target` by name similarity — the
    cheap filter that runs before the expensive graph-enrichment + LLM-judgment step. `WRatio`
    handles the common variants seen in filings (abbreviations, "Corp" vs "Corporation", word
    order) better than a plain edit-distance ratio."""
    if not pool:
        return []
    choices = {i: node.name for i, node in enumerate(pool)}
    matches = process.extract(target.name, choices, scorer=fuzz.WRatio, limit=limit, score_cutoff=threshold)
    return [pool[i] for _, _score, i in matches]
