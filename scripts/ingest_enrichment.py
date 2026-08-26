"""Module 3 — extend the graph with structured data: profile, executives, financials, events, news."""

from financial_advisor.enrichment.graph_writer import (
    write_company_profile,
    write_events,
    write_executives,
    write_financials,
    write_news,
    write_sector_classification,
)
from financial_advisor.enrichment.loaders import (
    load_company_profile,
    load_corporate_actions,
    load_executives,
    load_fundamentals,
    load_news,
    load_sector_classification,
)
from financial_advisor.ingestion.schema import apply_enrichment_schema

COMPANIES = ["3M", "APPLE"]


def main() -> None:
    apply_enrichment_schema()

    for company_id in COMPANIES:
        print(f"Enriching {company_id} ...")

        profile = load_company_profile(company_id)
        write_company_profile(company_id, profile)
        print(f"  profile: ticker={profile.get('ticker')} industry={profile.get('industry')}")

        executives = load_executives(company_id)
        write_executives(company_id, executives)
        print(f"  {len(executives)} executives")

        ticker = profile.get("ticker")
        if ticker:
            classification = load_sector_classification(ticker)
            write_sector_classification(company_id, classification)
            print(f"  sharadar classification: {classification}")

            periods = load_fundamentals(ticker)
            write_financials(company_id, ticker, periods)
            print(f"  {len(periods)} fiscal year(s) of fundamentals")

            actions = load_corporate_actions(ticker)
            write_events(company_id, ticker, actions)
            print(f"  {len(actions)} corporate action(s)")
        else:
            print("  no ticker from Wikidata profile — skipping Sharadar fundamentals/events")

        articles = load_news(company_id, start_date="2024-01-01", end_date="2025-12-31")
        write_news(company_id, articles)
        print(f"  {len(articles)} articles")


if __name__ == "__main__":
    main()
