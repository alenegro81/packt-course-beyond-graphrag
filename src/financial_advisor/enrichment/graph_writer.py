from financial_advisor.services.neo4j_service import neo4j_service


def write_executives(company_id: str, executives: list[dict]) -> None:
    """Upsert Person nodes and (Person)-[:ROLE_AT {title, start, end}]->(Company) relationships.

    Each executive's career_history also lands as ROLE_AT edges to their prior employers —
    lightweight Company stub nodes (`stub: true`) distinct from the fully-ingested companies
    from Module 1, since we only know their name here, not their filings.
    """
    for executive in executives:
        neo4j_service.run_query(
            """
            MERGE (p:Person {id: $id})
            SET p.name = $name, p.bio = $bio
            """,
            {"id": executive["id"], "name": executive["name"], "bio": executive.get("bio")},
        )

        neo4j_service.run_query(
            """
            MATCH (p:Person {id: $person_id})
            MERGE (c:Company {id: $company_id})
            WITH p, c
            UNWIND $titles AS role
            MERGE (p)-[r:ROLE_AT {title: role.title}]->(c)
            SET r.start = role.start, r.end = role.end
            """,
            {
                "person_id": executive["id"],
                "company_id": company_id,
                "titles": executive["titles"],
            },
        )

        career_history = executive.get("career_history") or []
        if career_history:
            neo4j_service.run_query(
                """
                MATCH (p:Person {id: $person_id})
                UNWIND $history AS role
                MERGE (other:Company {id: role.employer})
                ON CREATE SET other.name = role.employer, other.stub = true
                MERGE (p)-[r:ROLE_AT {title: coalesce(role.title, "Employee")}]->(other)
                SET r.start = role.start, r.end = role.end
                """,
                {"person_id": executive["id"], "history": career_history},
            )


def write_company_profile(company_id: str, profile: dict) -> None:
    """Set Wikidata profile properties on the Company node and link parent/subsidiary structure.

    Parent/subsidiaries land as lightweight stub `Company` nodes (`stub: true`) when they aren't
    one of the fully-ingested companies from Module 1 — same convention `write_executives` uses
    for career_history employers.
    """
    neo4j_service.run_query(
        """
        MERGE (c:Company {id: $company_id})
        SET c.industry = $industry, c.founded = $founded, c.hq = $hq,
            c.exchange = $exchange, c.ticker = $ticker
        """,
        {
            "company_id": company_id,
            "industry": profile.get("industry"),
            "founded": profile.get("founded"),
            "hq": profile.get("hq"),
            "exchange": profile.get("exchange"),
            "ticker": profile.get("ticker"),
        },
    )

    parent = profile.get("parent")
    if parent:
        neo4j_service.run_query(
            """
            MATCH (c:Company {id: $company_id})
            MERGE (p:Company {id: $parent_id})
            ON CREATE SET p.name = $parent_name, p.stub = true
            MERGE (c)-[:SUBSIDIARY_OF]->(p)
            """,
            {"company_id": company_id, "parent_id": parent["id"], "parent_name": parent["name"]},
        )

    subsidiaries = profile.get("subsidiaries") or []
    if subsidiaries:
        neo4j_service.run_query(
            """
            MATCH (c:Company {id: $company_id})
            UNWIND $subsidiaries AS sub
            MERGE (s:Company {id: sub.id})
            ON CREATE SET s.name = sub.name, s.stub = true
            MERGE (s)-[:SUBSIDIARY_OF]->(c)
            """,
            {"company_id": company_id, "subsidiaries": subsidiaries},
        )


def write_sector_classification(company_id: str, classification: dict) -> None:
    """Set Sharadar's sector/industry on the Company node as `sharadar_sector`/`sharadar_industry`
    — kept separate from the Wikidata-sourced `industry` property (see adr/0005)."""
    neo4j_service.run_query(
        """
        MERGE (c:Company {id: $company_id})
        SET c.sharadar_sector = $sector, c.sharadar_industry = $industry
        """,
        {
            "company_id": company_id,
            "sector": classification.get("sector"),
            "industry": classification.get("industry"),
        },
    )


def write_financials(company_id: str, ticker: str, periods: list[dict]) -> None:
    """Upsert FinancialPeriod nodes (Sharadar SF1 fundamentals) linked via HAS_FINANCIALS."""
    if not periods:
        return
    neo4j_service.run_query(
        """
        MERGE (c:Company {id: $company_id})
        WITH c
        UNWIND $periods AS period
        MERGE (fp:FinancialPeriod {id: $ticker + ":" + period.calendardate})
        SET fp.calendardate = period.calendardate, fp.revenue = period.revenue,
            fp.netinc = period.netinc, fp.assets = period.assets,
            fp.liabilities = period.liabilities, fp.equity = period.equity, fp.eps = period.eps
        MERGE (c)-[:HAS_FINANCIALS]->(fp)
        """,
        {"company_id": company_id, "ticker": ticker, "periods": periods},
    )


def write_events(company_id: str, ticker: str, events: list[dict]) -> None:
    """Upsert Event nodes (Sharadar corporate actions) linked via HAD_EVENT."""
    if not events:
        return
    neo4j_service.run_query(
        """
        MERGE (c:Company {id: $company_id})
        WITH c
        UNWIND $events AS event
        MERGE (e:Event {id: $ticker + ":" + event.date + ":" + event.action})
        SET e.type = event.action, e.date = event.date,
            e.description = CASE
                WHEN event.contraname IS NULL OR event.contraname = "N/A" THEN event.name
                ELSE event.contraname
            END
        MERGE (c)-[:HAD_EVENT]->(e)
        """,
        {"company_id": company_id, "ticker": ticker, "events": events},
    )


def write_news(company_id: str, articles: list[dict]) -> None:
    """Upsert Article nodes and (Company)-[:MENTIONED_IN]->(Article) relationships."""
    if not articles:
        return
    neo4j_service.run_query(
        """
        MERGE (c:Company {id: $company_id})
        WITH c
        UNWIND $articles AS article
        MERGE (a:Article {id: article.id})
        SET a.title = article.title,
            a.text = article.text,
            a.url = article.url,
            a.published_at = article.published_at
        MERGE (c)-[:MENTIONED_IN]->(a)
        """,
        {"company_id": company_id, "articles": articles},
    )
