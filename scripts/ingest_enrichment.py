"""Module 3 — extend the graph with structured data: executives, events, news."""

from neo4j import GraphDatabase

from financial_advisor.clients import get_graph
from financial_advisor.config import settings
from financial_advisor.enrichment.graph_writer import write_executives, write_news
from financial_advisor.enrichment.loaders import load_executives, load_news
from financial_advisor.ingestion.schema import apply_schema

COMPANIES = []  # populate with company IDs before running


def main() -> None:
    driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_username, settings.neo4j_password),
    )
    apply_schema(driver, module=3)
    driver.close()

    graph = get_graph()

    for company_id in COMPANIES:
        print(f"Enriching {company_id} ...")
        executives = load_executives(company_id)
        write_executives(graph, company_id, executives)

        articles = load_news(company_id, start_date="2018-01-01", end_date="2024-12-31")
        write_news(graph, company_id, articles)


if __name__ == "__main__":
    main()
