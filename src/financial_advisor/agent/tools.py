from langchain_core.tools import tool
from neo4j.exceptions import CypherSyntaxError

from financial_advisor.retrieval import graph_nav, keyword, vector
from financial_advisor.text2cypher.chain import run_text_to_cypher


@tool
def semantic_search(
    query: str, k: int = 5, company_id: str | None = None, year: int | None = None
) -> list[dict]:
    """Search 10-K filing text by semantic similarity (embeddings).

    Source: this project's own Neo4j vector index over `Chunk` embeddings — unstructured filing
    text, not a structured/reference source. Best for broad, conceptual, or comparative
    questions, or when you're unsure of the exact wording used in the filing. Set company_id
    (e.g. "3M", "APPLE") to restrict the search to one company's filings once you know which one
    you need. Set year (e.g. 2024, 2025) to restrict to one filing year — combine both when a
    company has more than one year in the corpus and you need to pinpoint a single filing. Do
    NOT use this for people/leadership, company profile, or financial-figure questions — those
    have dedicated structured tools below that are more reliable.
    """
    return vector.semantic_search(query, k=k, company_id=company_id, year=year)


@tool
def fulltext_search(
    query: str, k: int = 5, company_id: str | None = None, year: int | None = None
) -> list[dict]:
    """Search 10-K filing text with Neo4j's Lucene full-text index.

    Source: this project's own Neo4j fulltext index over `Chunk` text — unstructured filing
    text, not a structured/reference source. Best once you know the exact terminology (line
    items, section titles). Lucene syntax: combine terms with AND/OR, use ~ for single-word
    fuzzy matching (e.g. "research~ AND development~"). Phrase fuzzy matching ("some phrase"~)
    is not supported. Set company_id to restrict the search to one company's filings, and/or
    year (e.g. 2024, 2025) to restrict to one filing year — combine both to pinpoint a single
    filing. Do NOT use this for people/leadership, company profile, or financial-figure
    questions — those have dedicated structured tools below that are more reliable.
    """
    return keyword.fulltext_search(query, k=k, company_id=company_id, year=year)


@tool
def get_document_pages(doc_id: str, pages: list[int], limit: int = 20) -> list[dict]:
    """Retrieve chunks from specific pages of a 10-K, given its doc_id.

    Source: this project's own Neo4j `Chunk` nodes from the ingested filings — unstructured
    filing text. Use only after doc_id has already been identified from a previous
    semantic_search or fulltext_search result — every returned chunk carries its source doc_id.
    Useful for pulling the full surrounding context around a promising hit.
    """
    return graph_nav.get_document_pages(doc_id, pages, limit=limit)


@tool
def get_executives(company_id: str) -> list[dict]:
    """Look up a company's executives and board members, with bio and career history elsewhere.

    Source: Wikidata — a crowdsourced structured knowledge base, queried via SPARQL — not the
    filing text. Coverage can be incomplete: smaller/less-notable roles or people may be
    missing, and dates aren't always recorded. Use for questions about a company's leadership,
    officers, board composition, or an executive's background/prior employers — the 10-K
    filings name officers but don't carry biographical detail (that's deferred to the proxy
    statement, which isn't in this corpus). Set company_id (e.g. "3M", "APPLE"). Prefer this
    over semantic_search/fulltext_search for any people question.
    """
    return graph_nav.get_executives(company_id)


@tool
def get_company_profile(company_id: str) -> dict:
    """Look up a company's profile (industry, founding year, HQ, exchange, ticker), corporate
    structure (parent/subsidiaries), Sharadar's own sector/industry classification, and dated
    corporate events (splits, spinoffs, mergers, name changes).

    Source: profile facts and corporate structure come from Wikidata (crowdsourced structured
    KB, via SPARQL) — coverage can be incomplete. `sharadar_sector`/`sharadar_industry` and
    events come from Sharadar (a paid financial-data vendor feed) — deliberately kept as
    separate fields from Wikidata's `industry` rather than merged, since the two sources can
    legitimately classify the same company differently. Use for "what kind of company is
    this", "who owns/is owned by whom", or "what corporate events has this company had"
    questions. Set company_id (e.g. "3M", "APPLE"). Do NOT use this for revenue/profit/
    balance-sheet figures — use get_financials.
    """
    return graph_nav.get_company_profile(company_id)


@tool
def get_financials(company_id: str) -> list[dict]:
    """Look up a company's annual fundamentals: revenue, net income, assets, liabilities,
    equity, and EPS, one entry per fiscal year, oldest first.

    Source: Sharadar (via Nasdaq Data Link) — a paid financial-data vendor feed of as-reported
    figures, not an LLM extraction from filing text. Treat these numbers as ground truth, more
    reliable than anything semantic_search/fulltext_search would surface from a 10-K's own
    financial statement tables. Use for any question asking for specific financial figures or
    year-over-year/company-to-company financial comparisons. Set company_id (e.g. "3M",
    "APPLE").
    """
    return graph_nav.get_financials(company_id)


@tool
def get_recognised_entities(doc_id: str, entity_type: str | None = None) -> list[dict]:
    """List entities an LLM extracted from one document's text, optionally filtered by type.

    Source: this project's own Neo4j `RecognisedEntity` nodes (Module 4) — an LLM's structured
    read of the filing text, not the raw text itself and not a vetted external source like
    Wikidata/Sharadar. entity_type is one of Company, Person, Product, Location, Regulation,
    Risk, FinancialMetric (omit to get all). Use for "what does this filing mention" questions
    about a specific doc_id — e.g. subsidiaries, named regulations, products, risk topics — where
    you want a complete, deduplicated list rather than whatever a text search happens to surface.
    Only covers chunks that have already been through extraction; if it returns nothing, fall
    back to semantic_search/fulltext_search. Get doc_id from a prior search hit.
    """
    return graph_nav.get_recognised_entities(doc_id, entity_type=entity_type)


@tool
def get_entity_relationships(doc_id: str, relationship_type: str | None = None) -> list[dict]:
    """List relationships between LLM-extracted entities within one document, optionally
    filtered by type.

    Source: this project's own Neo4j generic RELATED_TO edges between RecognisedEntity nodes
    (Module 4) — an LLM's structured read of the filing text. relationship_type is one of
    COMPETES_WITH, SUBSIDIARY_OF, SUPPLIES, CUSTOMER_OF, PRODUCES, OPERATES_IN, EXPOSED_TO,
    REGULATED_BY, EMPLOYED_BY (omit to get all). Use once you need to know how entities in a
    document connect — e.g. "which subsidiaries and what jurisdictions" needs SUBSIDIARY_OF and
    OPERATES_IN together. Call get_recognised_entities first if you're not sure what's in the
    document. Only covers chunks that have already been through extraction.
    """
    return graph_nav.get_entity_relationships(doc_id, relationship_type=relationship_type)


@tool
def query_graph(question: str) -> list[dict]:
    """Answer a question by generating and running a read-only Cypher query against the whole
    graph, schema-aware but with no built-in retry or self-correction.

    Source: an LLM-generated Cypher query over this project's live Neo4j schema (all labels/
    relationships from every module) — not a curated source, and not guaranteed correct. Use
    this ONLY as a last resort, for questions none of the other tools cover — typically
    cross-cutting aggregates, counts, or multi-hop patterns spanning several node types (e.g.
    "how many companies has each executive worked at", "which entities are RELATED_TO both a
    Risk and a Regulation"). Prefer the structured tools above whenever the question fits one of
    them — they're more reliable. If this returns an error, don't retry the exact same question;
    rephrase it or fall back to another tool.
    """
    try:
        cypher, rows = run_text_to_cypher(question)
    except (ValueError, CypherSyntaxError) as exc:
        return [{"id": "query_graph_error", "error": str(exc)}]
    if not rows:
        return [{"id": "query_graph_empty", "cypher": cypher, "message": "Query returned no results."}]
    return [{"id": row.get("id", f"row_{i}"), **row} for i, row in enumerate(rows)]


MODULE_2_TOOLS = [semantic_search, fulltext_search, get_document_pages]
MODULE_3_TOOLS = [
    semantic_search,
    fulltext_search,
    get_document_pages,
    get_executives,
    get_company_profile,
    get_financials,
]
MODULE_4_TOOLS = MODULE_3_TOOLS + [get_recognised_entities, get_entity_relationships]
MODULE_6_TOOLS = MODULE_4_TOOLS + [query_graph]
TOOLS_BY_NAME = {t.name: t for t in MODULE_6_TOOLS}
