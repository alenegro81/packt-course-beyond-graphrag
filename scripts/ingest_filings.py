"""Module 1 — ingest PDF filings, build initial document graph, apply baseline schema."""

import argparse
from pathlib import Path

from financial_advisor.ingestion.document_loader import add_embeddings, load_from_path
from financial_advisor.ingestion.graph_writer import write_documents
from financial_advisor.ingestion.schema import apply_basic_schema, apply_embedding_schema
from financial_advisor.services.embedding_service import embedding_service
from financial_advisor.services.neo4j_service import neo4j_service


def _parse_filing_name(stem: str) -> tuple[str, int] | None:
    """Parse company_id and year from stems like 'APPLE_2018_10K' or '3M_2018_10K'.

    Convention: {COMPANY}_{YEAR}_{...}.pdf — the first 4-digit segment is the year;
    everything before it is the company identifier.
    Returns (company_id, year) or None if the year cannot be found.
    """
    parts = stem.split("_")
    for i, part in enumerate(parts):
        if part.isdigit() and len(part) == 4:
            company_id = "_".join(parts[:i]) or stem
            return company_id, int(part)
    return None


def main(filings_dir: Path) -> None:
    if not filings_dir.is_dir():
        raise SystemExit(f"Directory not found: {filings_dir}")

    print("Applying schema …")
    apply_basic_schema()
    apply_embedding_schema(embedding_service.dimensions)

    pdfs = sorted(filings_dir.glob("**/*.pdf"))
    if not pdfs:
        print("No PDF files found — nothing to ingest.")
        return

    print(f"Found {len(pdfs)} PDF(s) to ingest.\n")

    for pdf in pdfs:
        parsed = _parse_filing_name(pdf.stem)
        if parsed is None:
            print(f"[WARN] Cannot parse company/year from '{pdf.name}', skipping.")
            continue
        company_id, year = parsed

        print(f"[{company_id}] {pdf.name} (year={year})")
        documents = load_from_path(pdf, company_id=company_id, year=year)
        if not documents:
            print(f"  No chunks produced — skipping.")
            continue

        print(f"  {len(documents)} chunks extracted")
        documents = add_embeddings(documents)
        write_documents(documents, company_id=company_id)

    neo4j_service.close()
    print("\nIngestion complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Ingest PDF 10-K filings into Neo4j (Module 1)."
    )
    parser.add_argument(
        "filings_dir",
        type=Path,
        help="Root directory containing company sub-folders with PDF filings.",
    )
    args = parser.parse_args()
    main(args.filings_dir)
