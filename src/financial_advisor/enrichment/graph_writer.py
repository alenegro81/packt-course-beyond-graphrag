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
