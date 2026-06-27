"""Module 1 — ingest PDF filings, build initial document graph, apply baseline schema."""

import argparse
from pathlib import Path

from neo4j import GraphDatabase

from financial_advisor.config import settings
from financial_advisor.ingestion.docling_loader import load_filing
from financial_advisor.ingestion.graph_writer import write_documents
from financial_advisor.ingestion.schema import apply_schema
from financial_advisor.clients import get_graph


def main(filings_dir: Path) -> None:
    driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_username, settings.neo4j_password),
    )
    apply_schema(driver, module=1)
    driver.close()

    graph = get_graph()

    for pdf in sorted(filings_dir.glob("**/*.pdf")):
        company_id = pdf.parent.name
        year = int(pdf.stem.split("_")[-1])
        print(f"Ingesting {pdf} ...")
        documents = load_filing(pdf, company_id=company_id, year=year)
        write_documents(graph, documents, company_id=company_id)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("filings_dir", type=Path)
    args = parser.parse_args()
    main(args.filings_dir)
