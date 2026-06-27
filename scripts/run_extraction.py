"""Module 4 — run LLM-based entity and relationship extraction over all Chunk nodes."""

from financial_advisor.clients import get_graph
from financial_advisor.extraction.entities import extract_entities
from financial_advisor.extraction.relationships import write_extraction_to_graph

BATCH_SIZE = 50


def main() -> None:
    graph = get_graph()
    result = graph.query("MATCH (c:Chunk) WHERE c.extracted IS NULL RETURN c.id AS id, c.text AS text")

    for i, row in enumerate(result):
        print(f"[{i+1}/{len(result)}] Extracting from chunk {row['id']}")
        from langchain_core.documents import Document
        doc = Document(page_content=row["text"], metadata={"id": row["id"]})
        extraction = extract_entities(doc)
        write_extraction_to_graph(graph, extraction, chunk_id=row["id"])
        graph.query("MATCH (c:Chunk {id: $id}) SET c.extracted = true", params={"id": row["id"]})


if __name__ == "__main__":
    main()
