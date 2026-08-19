"""Module 3 — extend the graph with structured data: executives and news."""

from financial_advisor.enrichment.graph_writer import write_executives, write_news
from financial_advisor.enrichment.loaders import load_executives, load_news
from financial_advisor.ingestion.schema import apply_enrichment_schema

COMPANIES = ["3M", "APPLE"]


def main() -> None:
    apply_enrichment_schema()

    for company_id in COMPANIES:
        print(f"Enriching {company_id} ...")

        executives = load_executives(company_id)
        write_executives(company_id, executives)
        print(f"  {len(executives)} executives")

        articles = load_news(company_id, start_date="2018-01-01", end_date="2018-12-31")
        write_news(company_id, articles)
        print(f"  {len(articles)} articles")


if __name__ == "__main__":
    main()
