"""Module 4 — run LLM-based entity and relationship extraction over all Chunk nodes.

Two-phase pipeline per chunk (see docs/adr/0007-extraction-generic-recognisedentity.md):
entities (+ one reflection pass) -> relationships constrained to the settled entity list ->
upsert as generic RecognisedEntity nodes / RELATED_TO edges.
"""

from langchain_core.documents import Document

from financial_advisor.extraction.entities import extract_entities
from financial_advisor.extraction.relationships import extract_relationships, write_extraction_to_graph
from financial_advisor.services.neo4j_service import neo4j_service


def main() -> None:
    rows = neo4j_service.run_query(
        "MATCH (c:Chunk) WHERE c.extracted IS NULL RETURN c.id AS id, c.text AS text, c.doc_id AS doc_id"
    )
    print(f"[run-extraction] {len(rows)} chunk(s) to process")

    for i, row in enumerate(rows, start=1):
        print(f"[{i}/{len(rows)}] chunk {row['id']}")
        doc = Document(page_content=row["text"], metadata={"id": row["id"]})

        entity_result = extract_entities(doc)
        known_entities = sorted({e.resolved_string for e in entity_result.entities})
        relationship_result = extract_relationships(doc, known_entities)
        write_extraction_to_graph(
            entity_result.entities,
            relationship_result.relationships,
            chunk_id=row["id"],
            doc_id=row["doc_id"],
        )
        neo4j_service.run_query("MATCH (c:Chunk {id: $id}) SET c.extracted = true", {"id": row["id"]})


if __name__ == "__main__":
    main()
