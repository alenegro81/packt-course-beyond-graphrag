from collections import defaultdict

from langchain_core.documents import Document

from financial_advisor.services.neo4j_service import neo4j_service


def document_exists(company_id: str, doc_name: str) -> bool:
    """Check whether a document has already been ingested for this company.

    Call this before the (expensive) PDF parsing + embedding steps, so already-ingested
    filings can be skipped without re-parsing them.
    """
    doc_id = f"{company_id}/{doc_name}"
    existing = neo4j_service.run_query(
        "MATCH (d:Document {id: $id}) RETURN d.id AS id LIMIT 1",
        {"id": doc_id},
    )
    return bool(existing)


def write_documents(documents: list[Document], company_id: str) -> None:
    """Write chunked documents to Neo4j as (Company)-[:HAS_DOCUMENT]->(Document)-[:HAS_CHUNK]->(Chunk).

    Idempotent: documents already present in the graph are skipped.
    Chunk.embedding is populated when metadata["embedding"] is present (see
    ingestion.document_loader.add_embeddings), otherwise left unset.
    """
    by_doc: dict[str, list[Document]] = defaultdict(list)
    for doc in documents:
        by_doc[doc.metadata["doc_name"]].append(doc)

    for doc_name, chunks in by_doc.items():
        doc_id = f"{company_id}/{doc_name}"

        if document_exists(company_id, doc_name):
            print(f"  Skipping {doc_name} — already in graph")
            continue

        first = chunks[0].metadata
        neo4j_service.run_query(
            """
            MERGE (c:Company {id: $company_id})
            MERGE (d:Document {id: $doc_id})
            ON CREATE SET
                d.doc_name    = $doc_name,
                d.title       = $title,
                d.source      = $source,
                d.format      = $format,
                d.total_pages = $total_pages,
                d.author      = $author,
                d.year        = $year,
                d.company_id  = $company_id
            MERGE (c)-[:HAS_DOCUMENT]->(d)
            """,
            {
                "company_id": company_id,
                "doc_id": doc_id,
                "doc_name": doc_name,
                "title": first.get("title"),
                "source": first.get("source"),
                "format": first.get("format", "pdf"),
                "total_pages": first.get("total_pages"),
                "author": first.get("author"),
                "year": first.get("year"),
            },
        )

        rows = [
            {
                "id": f"{doc_id}/{chunk.metadata['chunk_index']}",
                "text": chunk.page_content,
                "idx": chunk.metadata["chunk_index"],
                "pages": chunk.metadata.get("pages", []),
                "doc_id": doc_id,
                "company_id": company_id,
                "year": chunk.metadata.get("year"),
                "embedding": chunk.metadata.get("embedding"),
            }
            for chunk in chunks
        ]

        neo4j_service.run_query(
            """
            UNWIND $rows AS row
            CALL (row) {
                MATCH (d:Document {id: row.doc_id})
                CREATE (ch:Chunk {
                    id:         row.id,
                    text:       row.text,
                    idx:        row.idx,
                    pages:      row.pages,
                    doc_id:     row.doc_id,
                    company_id: row.company_id,
                    year:       row.year,
                    embedding:  row.embedding
                })
                CREATE (d)-[:HAS_CHUNK]->(ch)
            } IN TRANSACTIONS OF 100 ROWS
            """,
            {"rows": rows},
        )
        print(f"  Wrote {len(rows)} chunks for {doc_name}")
