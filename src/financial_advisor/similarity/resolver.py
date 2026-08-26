from uuid import uuid4

from financial_advisor.clients import get_llm
from financial_advisor.extraction.validators import EntityType
from financial_advisor.services.neo4j_service import neo4j_service
from financial_advisor.similarity.candidates import fetch_candidate_pool, find_fuzzy_candidates, node_match_clause
from financial_advisor.similarity.context import fetch_entity_context
from financial_advisor.similarity.prompts import RESOLUTION_SYSTEM_PROMPT, build_resolution_prompt
from financial_advisor.similarity.validators import CandidateNode, ResolutionResult

# Companies and people first — they carry the richest graph context (ROLE_AT, SUBSIDIARY_OF,
# filing provenance) and have curated Module 1/3 counterparts to reconcile against; the
# remaining types only ever exist as RecognisedEntity mentions extracted in Module 4.
RESOLUTION_ORDER = [
    EntityType.COMPANY,
    EntityType.PERSON,
    EntityType.PRODUCT,
    EntityType.LOCATION,
    EntityType.REGULATION,
    EntityType.RISK,
    EntityType.FINANCIAL_METRIC,
]


def judge_candidates(entity_type: EntityType, target_ctx: dict, candidate_ctxs: list[dict]) -> ResolutionResult:
    model = get_llm()
    return model.with_structured_output(ResolutionResult).invoke(
        [
            {"role": "system", "content": RESOLUTION_SYSTEM_PROMPT},
            {"role": "user", "content": build_resolution_prompt(entity_type, target_ctx, candidate_ctxs)},
        ]
    )


def pick_canonical_name(members: list[CandidateNode]) -> str:
    """Prefer a curated node's name (Wikidata-sourced, already clean) over an extracted mention;
    among ties, the longest string is usually the least abbreviated (e.g. '3M Company' over
    '3M')."""
    curated = [m for m in members if m.label in ("Company", "Person")]
    pool = curated or members
    return max(pool, key=lambda m: len(m.name)).name


def write_entity_group(entity_type: EntityType, members: list[CandidateNode]) -> str:
    """Create one EntityGroup and a SAME_AS edge from every member to it. Idempotent per member
    (MERGE on the edge), but always mints a fresh group id — call this at most once per confirmed
    cluster, not per member."""
    group_id = str(uuid4())
    canonical_name = pick_canonical_name(members)

    neo4j_service.run_query(
        "MERGE (g:EntityGroup {id: $id}) SET g.type = $type, g.canonical_name = $canonical_name",
        {"id": group_id, "type": entity_type.value, "canonical_name": canonical_name},
    )
    for member in members:
        match_clause, params = node_match_clause(member)
        neo4j_service.run_query(
            f"{match_clause} MATCH (g:EntityGroup {{id: $group_id}}) MERGE (n)-[:SAME_AS]->(g)",
            {**params, "group_id": group_id},
        )
    return group_id


def resolve_entity_type(entity_type: EntityType, fuzzy_threshold: float = 78.0, max_candidates: int = 8) -> int:
    """Resolve one entity type end to end: fuzzy-narrow candidates by name, enrich survivors with
    graph context, let the LLM confirm which are true duplicates, write one EntityGroup per
    confirmed cluster. Returns the number of groups created. Idempotent — nodes already under a
    SAME_AS edge are excluded from the pool up front (see candidates.fetch_candidate_pool)."""
    pool = fetch_candidate_pool(entity_type)
    print(f"[resolve:{entity_type.value}] {len(pool)} unresolved node(s)")

    groups_created = 0
    while pool:
        target = pool.pop(0)
        fuzzy_matches = find_fuzzy_candidates(target, pool, threshold=fuzzy_threshold, limit=max_candidates)
        if not fuzzy_matches:
            continue

        print(
            f"[resolve:{entity_type.value}] '{target.name}' ({target.label}) — "
            f"{len(fuzzy_matches)} fuzzy candidate(s): {[c.name for c in fuzzy_matches]}"
        )
        target_ctx = fetch_entity_context(target)
        candidate_ctxs = [fetch_entity_context(c) for c in fuzzy_matches]
        result = judge_candidates(entity_type, target_ctx, candidate_ctxs)

        confirmed = [
            fuzzy_matches[j.index]
            for j in result.judgments
            if j.same_entity and 0 <= j.index < len(fuzzy_matches)
        ]
        if not confirmed:
            print(f"[resolve:{entity_type.value}] '{target.name}' — LLM confirmed none, no group created")
            continue

        group_id = write_entity_group(entity_type, [target] + confirmed)
        groups_created += 1
        print(
            f"[resolve:{entity_type.value}] group {group_id[:8]} = "
            f"{target.name} + {[c.name for c in confirmed]}"
        )
        for c in confirmed:
            pool.remove(c)

    print(f"[resolve:{entity_type.value}] done — {groups_created} group(s) created")
    return groups_created


def resolve_all_entities(fuzzy_threshold: float = 78.0, max_candidates: int = 8) -> dict[str, int]:
    """Run resolve_entity_type for every type in RESOLUTION_ORDER. Returns groups created per type."""
    return {
        t.value: resolve_entity_type(t, fuzzy_threshold=fuzzy_threshold, max_candidates=max_candidates)
        for t in RESOLUTION_ORDER
    }
