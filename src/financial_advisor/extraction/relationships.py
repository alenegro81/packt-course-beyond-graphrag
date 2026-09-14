import re

from langchain_core.documents import Document

from financial_advisor.clients import get_llm
from financial_advisor.extraction.prompts import RELATIONSHIP_SYSTEM_PROMPT, build_relationship_prompt
from financial_advisor.extraction.validators import ExtractedEntity, ExtractedRelationship, RelationshipExtractionResult
from financial_advisor.services.neo4j_service import neo4j_service

# Matches a leading list/bullet marker: "-"/"•"/"*", or a short numbered/lettered prefix like
# "1.", "(a)", "1)". Requires trailing punctuation ("." or ")") for the alnum case specifically
# so an ordinary name that happens to start with 1-2 letters/digits (e.g. "3M Company") is never
# mistaken for one — nothing here matches "3M " on its own.
_LEADING_MARKER_RE = re.compile(r"^\s*(?:[-•*]|\(?[0-9a-zA-Z]{1,2}[.)])\s+")


def _normalize_entity_name(name: str) -> str:
    """Strip a leading list/bullet marker and surrounding whitespace, then lowercase, before
    comparing entity names. Extraction is now told not to capture a table/list row's bullet
    marker as part of an entity's name (extraction.prompts.EXTRACTION_SCOPE), but this is the
    same prompt-plus-code-backstop shape used elsewhere in this pipeline: if one slips through
    anyway (e.g. "- 3M Company" extracted as an entity's literal `string`, while the model later
    writes a relationship against the clean "3M Company"), the cosmetic mismatch alone shouldn't
    cause an otherwise-correct relationship to be dropped as referencing an unknown entity."""
    return _LEADING_MARKER_RE.sub("", name).strip().lower()


def _filter_valid_relationships(
    relationships: list[ExtractedRelationship], known_entities: list[str]
) -> list[ExtractedRelationship]:
    """Drop any relationship whose source/target isn't in the known (settled) entity list —
    a guard against the model naming an entity it wasn't actually given, despite the prompt
    constraint (see adr/0007)."""
    known = {_normalize_entity_name(name) for name in known_entities}
    return [
        r
        for r in relationships
        if _normalize_entity_name(r.source) in known and _normalize_entity_name(r.target) in known
    ]


def extract_relationships(chunk: Document, known_entities: list[str]) -> RelationshipExtractionResult:
    """Extract relationships between already-settled entities (see extraction.entities).
    Passing a closed entity list, rather than letting the model name whatever it likes, is what
    keeps relationships anchored to entities that were actually confirmed to exist.

    known_entities should be RESOLVED names (`ExtractedEntity.resolved_string`, not `.string`) —
    passing literal mentions here would let a relationship reference e.g. "the Company" as a
    source/target, which write_extraction_to_graph can no longer match (RecognisedEntity is now
    keyed by resolved_string). Resolved names also naturally deduplicate the list the model sees
    (a coreferenced mention and its canonical form no longer appear as two separate choices)."""
    if not known_entities:
        print("[extract-relationships] no known entities — skipping")
        return RelationshipExtractionResult()

    model = get_llm()
    result: RelationshipExtractionResult = model.with_structured_output(
        RelationshipExtractionResult
    ).invoke(
        [
            {"role": "system", "content": RELATIONSHIP_SYSTEM_PROMPT},
            {"role": "user", "content": build_relationship_prompt(chunk.page_content, known_entities)},
        ]
    )

    valid = _filter_valid_relationships(result.relationships, known_entities)
    dropped = len(result.relationships) - len(valid)
    if dropped:
        print(f"[extract-relationships] dropped {dropped} relationship(s) referencing unknown entities")
    print(f"[extract-relationships] {len(valid)} relationship(s) found")

    return RelationshipExtractionResult(relationships=valid)


def write_extraction_to_graph(
    entities: list[ExtractedEntity],
    relationships: list[ExtractedRelationship],
    chunk_id: str,
    doc_id: str,
) -> None:
    """Upsert RecognisedEntity nodes (keyed by resolved_string+doc_id, see adr/0007) and generic
    RELATED_TO edges, linked back to their source chunk for provenance. No cross-document
    merging — that's Module 5's entity-resolution job.

    A node is keyed by `resolved_string`, not the literal `string` each ExtractedEntity carries
    — this is what collapses a coreferenced mention (e.g. "the Company") onto the same node as
    every other mention of the same entity within this doc_id, rather than creating a separate
    node per literal surface form. Every distinct literal form actually seen is kept on
    `e.mentions` so the coreference is auditable, not silently discarded — see
    extraction.prompts.REFLECTION_COREFERENCE_GUIDANCE for where resolution happens."""
    if entities:
        neo4j_service.run_query(
            """
            MATCH (ch:Chunk {id: $chunk_id})
            UNWIND $entities AS entity
            MERGE (e:RecognisedEntity {string: entity.resolved_string, doc_id: $doc_id})
            SET e.type = entity.type, e.description = entity.description
            SET e.mentions = CASE
                WHEN entity.string IN coalesce(e.mentions, []) THEN e.mentions
                ELSE coalesce(e.mentions, []) + entity.string
            END
            MERGE (e)-[:MENTIONED_IN]->(ch)
            """,
            {
                "chunk_id": chunk_id,
                "doc_id": doc_id,
                "entities": [e.model_dump(mode="json") for e in entities],
            },
        )

    if relationships:
        neo4j_service.run_query(
            """
            UNWIND $relationships AS rel
            MATCH (a:RecognisedEntity {string: rel.source, doc_id: $doc_id})
            MATCH (b:RecognisedEntity {string: rel.target, doc_id: $doc_id})
            MERGE (a)-[r:RELATED_TO {type: rel.type}]->(b)
            SET r.evidence = rel.evidence, r.chunk_id = $chunk_id
            """,
            {
                "doc_id": doc_id,
                "chunk_id": chunk_id,
                "relationships": [r.model_dump(mode="json") for r in relationships],
            },
        )
