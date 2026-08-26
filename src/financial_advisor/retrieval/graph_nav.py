from financial_advisor.services.neo4j_service import neo4j_service


def get_document_pages(doc_id: str, pages: list[int], limit: int = 20) -> list[dict]:
    """Return chunks from specific pages of a document, ordered by position.

    Use once doc_id has already been identified from a semantic_search or fulltext_search
    hit — every chunk carries its source doc_id.
    """
    rows = neo4j_service.run_query(
        """
        MATCH (ch:Chunk {doc_id: $doc_id})
        WHERE any(p IN $pages WHERE p IN ch.pages)
        RETURN ch.id AS id, ch.text AS text, ch.doc_id AS doc_id,
               ch.company_id AS company_id, ch.idx AS idx, ch.pages AS pages, 1.0 AS score
        ORDER BY ch.idx
        LIMIT $limit
        """,
        {"doc_id": doc_id, "pages": pages, "limit": limit},
    )
    return rows


def get_executives(company_id: str) -> list[dict]:
    """Return people with a ROLE_AT the given company, with bio and career history elsewhere.

    career_history covers roles the same person held at *other* companies (board seats, prior
    employers) — this is what fills the gap where a 10-K names its officers but defers their
    biographical/career detail to a proxy statement that was never ingested.
    """
    rows = neo4j_service.run_query(
        """
        MATCH (p:Person)-[r:ROLE_AT]->(c:Company {id: $company_id})
        ORDER BY r.start desc
        WITH p, collect({title: r.title, start: r.start, end: r.end}) AS roles
        OPTIONAL MATCH (p)-[r2:ROLE_AT]->(other:Company)
        WHERE other.id <> $company_id
        WITH p, roles, other, r2
        ORDER BY r2.start DESC
        WITH p, roles, collect(
            CASE WHEN other IS NULL THEN null
                 ELSE {company: other.name, title: r2.title, start: r2.start, end: r2.end} END
        ) AS raw_history
        RETURN p.id AS id, p.name AS name, p.bio AS bio, roles,
               [x IN raw_history WHERE x IS NOT NULL] AS career_history
        """,
        {"company_id": company_id},
    )
    return rows


def get_company_profile(company_id: str) -> dict:
    """Return a company's profile (Wikidata), corporate structure (Wikidata), Sharadar's own
    sector classification, and events (Sharadar).

    industry/founded/hq/exchange/ticker and parent/subsidiaries come from Wikidata.
    sharadar_sector/sharadar_industry are Sharadar's own classification — kept separate from
    `industry` since the two sources can disagree. events are dated corporate actions (splits,
    spinoffs, mergers, name changes) from Sharadar ACTIONS, via HAD_EVENT. parent/subsidiaries
    may point to stub Company nodes we only know the name of.
    """
    rows = neo4j_service.run_query(
        """
        MATCH (c:Company {id: $company_id})
        OPTIONAL MATCH (c)-[:SUBSIDIARY_OF]->(parent:Company)
        OPTIONAL MATCH (sub:Company)-[:SUBSIDIARY_OF]->(c)
        OPTIONAL MATCH (c)-[:HAD_EVENT]->(e:Event)
        RETURN c.id AS id, c.name AS name, c.industry AS industry, c.founded AS founded,
               c.hq AS hq, c.exchange AS exchange, c.ticker AS ticker,
               c.sharadar_sector AS sharadar_sector, c.sharadar_industry AS sharadar_industry,
               parent.name AS parent,
               collect(DISTINCT sub.name) AS subsidiaries,
               collect(DISTINCT CASE WHEN e IS NULL THEN null
                       ELSE {type: e.type, date: e.date, description: e.description} END) AS events
        """,
        {"company_id": company_id},
    )
    if not rows:
        return {}
    row = rows[0]
    row["events"] = [e for e in row["events"] if e is not None]
    return row


def get_financials(company_id: str) -> list[dict]:
    """Return a company's annual fundamentals (Sharadar SF1), oldest fiscal year first."""
    return neo4j_service.run_query(
        """
        MATCH (c:Company {id: $company_id})-[:HAS_FINANCIALS]->(fp:FinancialPeriod)
        RETURN fp.id AS id, fp.calendardate AS calendardate, fp.revenue AS revenue,
               fp.netinc AS netinc, fp.assets AS assets, fp.liabilities AS liabilities,
               fp.equity AS equity, fp.eps AS eps
        ORDER BY fp.calendardate
        """,
        {"company_id": company_id},
    )


def get_recognised_entities(doc_id: str, entity_type: str | None = None) -> list[dict]:
    """Return LLM-extracted entities (Module 4) mentioned in a single document, optionally
    filtered by type (Company, Person, Product, Location, Regulation, Risk, FinancialMetric).

    Source: RecognisedEntity nodes, keyed (string, doc_id) — see adr/0007. Not merged across
    documents or reconciled against curated Company/Person nodes yet (Module 5's job), so the
    same real-world entity can appear under slightly different strings. Only covers chunks that
    have already been through extraction (c.extracted = true) — returns nothing otherwise.
    """
    rows = neo4j_service.run_query(
        """
        MATCH (e:RecognisedEntity {doc_id: $doc_id})
        WHERE $entity_type IS NULL OR e.type = $entity_type
        RETURN e.string AS string, e.type AS type, e.description AS description,
               e.doc_id AS doc_id
        ORDER BY e.type, e.string
        """,
        {"doc_id": doc_id, "entity_type": entity_type},
    )
    for row in rows:
        row["id"] = f"{row['doc_id']}::{row['string']}"
    return rows


def get_entity_relationships(doc_id: str, relationship_type: str | None = None) -> list[dict]:
    """Return relationships between LLM-extracted entities (Module 4) within a single document,
    optionally filtered by type (COMPETES_WITH, SUBSIDIARY_OF, SUPPLIES, CUSTOMER_OF, PRODUCES,
    OPERATES_IN, EXPOSED_TO, REGULATED_BY, EMPLOYED_BY).

    Source: generic RELATED_TO edges between RecognisedEntity nodes — see adr/0007 for why the
    edge type is generic with a `type` property rather than a real Neo4j relationship type. Use
    get_recognised_entities first if you don't already know which entity types exist in the
    document. Only covers chunks that have already been through extraction.
    """
    rows = neo4j_service.run_query(
        """
        MATCH (a:RecognisedEntity {doc_id: $doc_id})-[r:RELATED_TO]->(b:RecognisedEntity)
        WHERE $relationship_type IS NULL OR r.type = $relationship_type
        RETURN a.string AS source, a.type AS source_type, r.type AS relationship,
               b.string AS target, b.type AS target_type, r.evidence AS evidence
        ORDER BY r.type, a.string
        """,
        {"doc_id": doc_id, "relationship_type": relationship_type},
    )
    for row in rows:
        row["id"] = f"{doc_id}::{row['source']}::{row['relationship']}::{row['target']}"
    return rows
