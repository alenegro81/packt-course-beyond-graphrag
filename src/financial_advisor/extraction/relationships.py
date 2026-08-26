from langchain_core.documents import Document

from financial_advisor.clients import get_llm
from financial_advisor.extraction.prompts import RELATIONSHIP_SYSTEM_PROMPT, build_relationship_prompt
from financial_advisor.extraction.validators import ExtractedEntity, ExtractedRelationship, RelationshipExtractionResult
from financial_advisor.services.neo4j_service import neo4j_service


def _filter_valid_relationships(
    relationships: list[ExtractedRelationship], known_entities: list[str]
) -> list[ExtractedRelationship]:
    """Drop any relationship whose source/target isn't in the known (settled) entity list —
    a guard against the model naming an entity it wasn't actually given, despite the prompt
    constraint (see adr/0007)."""
    known = {name.lower() for name in known_entities}
    return [r for r in relationships if r.source.lower() in known and r.target.lower() in known]


def extract_relationships(chunk: Document, known_entities: list[str]) -> RelationshipExtractionResult:
    """Extract relationships between already-settled entities (see extraction.entities).
    Passing a closed entity list, rather than letting the model name whatever it likes, is what
    keeps relationships anchored to entities that were actually confirmed to exist."""
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
    """Upsert RecognisedEntity nodes (keyed by string+doc_id, see adr/0007) and generic RELATED_TO
    edges, linked back to their source chunk for provenance. No cross-document merging — that's
    Module 5's entity-resolution job."""
    if entities:
        neo4j_service.run_query(
            """
            MATCH (ch:Chunk {id: $chunk_id})
            UNWIND $entities AS entity
            MERGE (e:RecognisedEntity {string: entity.string, doc_id: $doc_id})
            SET e.type = entity.type, e.description = entity.description
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
