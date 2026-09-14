"""Loaders for structured data sources: Wikidata (executives) and the NYT Article Search API (news)."""

from __future__ import annotations

import time

import httpx

from financial_advisor.config import settings

WIKIDATA_SPARQL_URL = "https://query.wikidata.org/sparql"
WIKIDATA_API_URL = "https://www.wikidata.org/w/api.php"
WIKIPEDIA_SUMMARY_URL = "https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
NYT_SEARCH_URL = "https://api.nytimes.com/svc/search/v2/articlesearch.json"
# Sharadar's own API, NOT proxied through Nasdaq Data Link's "datatables" REST API — see
# adr/0005's amendment. https://sharadar.com/docs/getting-started for the endpoint reference.
SHARADAR_BASE_URL = "https://api.sharadar.com/v1.0/data"

USER_AGENT = "BeyondGraphRAGCourse/0.1 (Packt course notebook; contact: alenegro81@gmail.com)"

# company_id -> Wikidata QID / display name used to query external sources.
COMPANY_WIKIDATA_QID = {"3M": "Q159433", "APPLE": "Q312"}
COMPANY_DISPLAY_NAME = {"3M": "3M", "APPLE": "Apple Inc."}
_QID_TO_COMPANY_ID = {qid: company_id for company_id, qid in COMPANY_WIKIDATA_QID.items()}

# The most recent fiscal year among the 10-Ks ingested in Module 1 — scopes the officer/board
# roster to the people actually relevant to those filings (both 2024 and 2025 are in the corpus;
# 2025 is used as "current" since a person holding a role through 2025 also covers the 2024
# filing). Keep this in sync with whatever's actually ingested — nothing derives it automatically.
# Founders are exempt from this filter (see _parse_officer_rows) since they're relevant
# regardless of which fiscal year a filing covers.
#
# Caveat (found 2026-09-01, live on Apple/Q312): wdt:P169/wdt:P488 are "truthy" shortcuts — they
# return only the *best*-ranked statement(s), which is ALL normal-rank statements only until an
# editor sets one statement's rank to "preferred" (e.g. recording a new CEO), at which point every
# other officer — including the one actually in office during FILING_YEAR — silently disappears
# from the result. _officers_query below queries the full statement (p:/ps:/pq:) instead, getting
# every CEO/chairperson ever recorded with their own start/end dates, then applies the same
# FILING_YEAR overlap filter already used for board members.
FILING_YEAR = 2025


def _sparql(query: str) -> list[dict]:
    # query.wikidata.org rate-limits (429), occasionally 502s, and can be slow to respond —
    # all transient under normal public-endpoint load.
    for attempt in range(4):
        try:
            resp = httpx.get(
                WIKIDATA_SPARQL_URL,
                params={"query": query, "format": "json"},
                headers={"User-Agent": USER_AGENT},
                timeout=30,
            )
        except httpx.TransportError:
            if attempt < 3:
                time.sleep(3 * (attempt + 1))
                continue
            raise
        if resp.status_code == 429:
            if attempt < 3:
                time.sleep(int(resp.headers.get("Retry-After", 5)))
                continue
            break  # last attempt: fall through to the RuntimeError below, not raise_for_status
        if resp.status_code in (502, 503, 504):
            if attempt < 3:
                time.sleep(3 * (attempt + 1))
                continue
            break
        resp.raise_for_status()
        return resp.json()["results"]["bindings"]
    raise RuntimeError("Wikidata SPARQL endpoint unavailable after retries")


# "en,mul" (not just "en"): Wikidata has been migrating person-name labels that don't vary by
# language onto the language-neutral "mul" code instead of duplicating them per-language, and
# plenty of entities — Steve Jobs (Q19837) among them — now carry *only* a "mul" label, no "en"
# one. A label-service call scoped to "en" alone falls back to the raw QID for these, and every
# _parse_*_rows helper below treats an unresolved (QID-as-label) row as noise and drops it — so
# without "mul" in the language list, real people/companies silently vanish from every query here.
def _officers_query(qid: str) -> str:
    return f"""
    SELECT ?person ?personLabel ?positionLabel ?start ?end WHERE {{
      VALUES ?company {{ wd:{qid} }}
      {{ ?company p:P169 ?stmt . ?stmt ps:P169 ?person .
         OPTIONAL {{ ?stmt pq:P580 ?start }} OPTIONAL {{ ?stmt pq:P582 ?end }}
         BIND("Chief Executive Officer" AS ?positionLabel) }}
      UNION
      {{ ?company p:P488 ?stmt . ?stmt ps:P488 ?person .
         OPTIONAL {{ ?stmt pq:P580 ?start }} OPTIONAL {{ ?stmt pq:P582 ?end }}
         BIND("Chairperson" AS ?positionLabel) }}
      UNION
      {{ ?company p:P3320 ?stmt . ?stmt ps:P3320 ?person .
         OPTIONAL {{ ?stmt pq:P580 ?start }} OPTIONAL {{ ?stmt pq:P582 ?end }}
         BIND("Board Member" AS ?positionLabel) }}
      UNION
      {{ ?company wdt:P112 ?person . BIND("Founder" AS ?positionLabel) }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en,mul". }}
    }}
    """


def _career_history_query(person_qid: str) -> str:
    return f"""
    SELECT ?employer ?employerLabel ?positionLabel ?start ?end WHERE {{
      wd:{person_qid} p:P108 ?stmt .
      ?stmt ps:P108 ?employer .
      OPTIONAL {{ ?stmt pq:P39 ?position }}
      OPTIONAL {{ ?stmt pq:P580 ?start }}
      OPTIONAL {{ ?stmt pq:P582 ?end }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en,mul". }}
    }}
    """


def _qid_from_uri(uri: str) -> str:
    return uri.rsplit("/", 1)[-1]


def _year(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(value[:4])
    except ValueError:
        return None


def _overlaps_filing_year(start: str | None, end: str | None) -> bool:
    start_year, end_year = _year(start), _year(end)
    if start_year is not None and start_year > FILING_YEAR:
        return False
    if end_year is not None and end_year < FILING_YEAR:
        return False
    return True


def _parse_officer_rows(rows: list[dict]) -> list[dict]:
    """Group raw SPARQL officer/board-member/founder bindings into one record per person.

    A person can hold more than one title at the same company (e.g. CEO and board member),
    so each record's `titles` is a list rather than a single flat title.

    FILING_YEAR decides who's *included* in the roster, not which of their titles survive: a
    person qualifies if any one title is a Founder (always relevant) or overlaps FILING_YEAR;
    once they qualify, ALL of their titles are kept, including ones that don't themselves
    overlap FILING_YEAR. Filtering title-by-title instead of person-by-person was the bug found
    2026-09-01: it silently stripped Steve Jobs's real 1997-2011 "Chief Executive Officer" title
    (present in the raw SPARQL rows — see _officers_query) even though he'd already qualified via
    "Founder", because that CEO stint itself predates FILING_YEAR. Once someone is relevant
    enough to include, their full role history is real information, not noise to re-filter.
    """
    people: dict[str, dict] = {}
    for row in rows:
        person_qid = _qid_from_uri(row["person"]["value"])
        name = row.get("personLabel", {}).get("value")
        if not name or name == person_qid:
            continue  # unresolved label — data-quality noise, skip
        title = row["positionLabel"]["value"]
        start = row.get("start", {}).get("value")
        end = row.get("end", {}).get("value")
        person = people.setdefault(person_qid, {"id": person_qid, "name": name, "titles": []})
        person["titles"].append({"title": title, "start": start, "end": end})

    return [
        p
        for p in people.values()
        if any(
            t["title"] == "Founder" or _overlaps_filing_year(t["start"], t["end"])
            for t in p["titles"]
        )
    ]


def _parse_career_rows(rows: list[dict]) -> list[dict]:
    history = []
    for row in rows:
        employer = row.get("employerLabel", {}).get("value")
        employer_qid = _qid_from_uri(row.get("employer", {}).get("value", ""))
        if not employer or employer == employer_qid:
            continue  # unresolved label — data-quality noise, skip
        history.append(
            {
                # Normalize to our own company_id when the employer is 3M/Apple itself, so this
                # merges into the canonical Company node rather than a duplicate stub.
                "employer": _QID_TO_COMPANY_ID.get(employer_qid, employer),
                "employer_qid": employer_qid,
                "title": row.get("positionLabel", {}).get("value"),
                "start": row.get("start", {}).get("value"),
                "end": row.get("end", {}).get("value"),
            }
        )
    return history


def _wikipedia_bio(person_qid: str) -> str | None:
    resp = httpx.get(
        WIKIDATA_API_URL,
        params={
            "action": "wbgetentities",
            "ids": person_qid,
            "props": "sitelinks",
            "sitefilter": "enwiki",
            "format": "json",
        },
        headers={"User-Agent": USER_AGENT},
        timeout=15,
    )
    resp.raise_for_status()
    entity = resp.json().get("entities", {}).get(person_qid, {})
    sitelink = entity.get("sitelinks", {}).get("enwiki")
    if not sitelink:
        return None

    summary = httpx.get(
        WIKIPEDIA_SUMMARY_URL.format(title=sitelink["title"]),
        headers={"User-Agent": USER_AGENT},
        timeout=15,
    )
    if summary.status_code != 200:
        return None
    return summary.json().get("extract")


def _reconcile_self_references(titles: list[dict], raw_history: list[dict], company_id: str) -> tuple[list[dict], list[dict]]:
    """Split a person's P108 career history into (titles gained, career_history at other firms).

    Virtually every officer's P108 ("employer") claims include their own employer — this
    company — alongside their outside employers, almost always with no P39 title qualifier.
    That untitled self-reference isn't career history (which is about *other* companies) and
    would otherwise write a bogus `ROLE_AT {title: "Employee"}` edge duplicating a role already
    in `titles`. But occasionally the self-reference *does* carry a P39 title Wikidata didn't
    also record on the org's own P169/P488/P3320/P112 claims (a President, COO, etc. that only
    shows up on the person's own item) — that's real information, so it's folded into `titles`
    rather than dropped, as long as it isn't just a case-different restatement of one we already
    have (observed live: 3M's William Brown has a self-reference titled "chief executive
    officer" that's exactly his existing "Chief Executive Officer" title, re-arriving lowercase).
    """
    titles = list(titles)
    known = {t["title"].lower() for t in titles}
    career_history = []
    for role in raw_history:
        if role["employer"] != company_id:
            career_history.append(role)
            continue
        if role["title"] and role["title"].lower() not in known:
            titles.append({"title": role["title"].title(), "start": role["start"], "end": role["end"]})
            known.add(role["title"].lower())
    return titles, career_history


def load_executives(company_id: str) -> list[dict]:
    """Return executive/board records for a company from Wikidata.

    Each record includes `career_history` — prior employers with title and start/end dates,
    pulled from the person's own Wikidata entity (P108 employer claims). This is the data that
    fills the gap Module 2 hit: a 10-K names its officers but defers their career history to a
    proxy statement that was never ingested. See _reconcile_self_references for how a person's
    own P108 claim about *this* company (as distinct from their other employers) gets folded
    back into `titles` instead of duplicating it or leaking through as career_history.
    """
    qid = COMPANY_WIKIDATA_QID[company_id]
    people = _parse_officer_rows(_sparql(_officers_query(qid)))

    executives = []
    for i, person in enumerate(people):
        if i > 0:
            time.sleep(1)  # stay well under Wikidata's SPARQL rate limit

        raw_history = _parse_career_rows(_sparql(_career_history_query(person["id"])))
        titles, career_history = _reconcile_self_references(person["titles"], raw_history, company_id)
        executives.append(
            {
                "id": person["id"],
                "name": person["name"],
                "titles": titles,
                "bio": _wikipedia_bio(person["id"]),
                "career_history": career_history,
            }
        )
    return executives


def _profile_query(qid: str) -> str:
    return f"""
    SELECT ?industryLabel ?inception ?hqLabel ?exchangeLabel ?ticker WHERE {{
      VALUES ?company {{ wd:{qid} }}
      OPTIONAL {{ ?company wdt:P452 ?industry }}
      OPTIONAL {{ ?company wdt:P571 ?inception }}
      OPTIONAL {{ ?company wdt:P159 ?hq }}
      OPTIONAL {{
        ?company p:P414 ?exchangeStmt .
        ?exchangeStmt ps:P414 ?exchange .
        OPTIONAL {{ ?exchangeStmt pq:P249 ?ticker }}
      }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en,mul". }}
    }}
    """


def _structure_query(qid: str) -> str:
    return f"""
    SELECT ?company ?companyLabel ?relation WHERE {{
      {{ wd:{qid} wdt:P749 ?company . BIND("parent" AS ?relation) }}
      UNION
      {{ wd:{qid} wdt:P355 ?company . BIND("subsidiary" AS ?relation) }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en,mul". }}
    }}
    """


# A company can have several P414 (stock exchange) statements — e.g. Apple is Wikidata-listed
# on both Nasdaq (AAPL) and the Tokyo Stock Exchange (6689, a secondary/depositary listing).
# SPARQL row order across these is arbitrary, so picking "the first row" can silently grab a
# secondary listing instead of the primary one. Sharadar only covers US-listed securities, so
# prefer a US exchange when one is present; found live on 2026-08-26 (Apple resolving to Tokyo)
# while checking why Sharadar fundamentals came back empty for a ticker Sharadar's never heard of.
PREFERRED_EXCHANGES = ("nasdaq", "new york stock exchange", "nyse")


def _parse_profile_rows(rows: list[dict]) -> dict:
    """Collapse possibly-several profile rows (one exchange statement can multiply the join)
    into a single set of facts: first non-null value seen for industry/founded/hq, but the
    exchange/ticker pair prefers a major US exchange (see PREFERRED_EXCHANGES) over just
    whichever row SPARQL happened to return first.
    """
    profile: dict = {"industry": None, "founded": None, "hq": None, "exchange": None, "ticker": None}
    for row in rows:
        if profile["industry"] is None and row.get("industryLabel"):
            profile["industry"] = row["industryLabel"]["value"]
        if profile["founded"] is None and row.get("inception"):
            profile["founded"] = _year(row["inception"]["value"])
        if profile["hq"] is None and row.get("hqLabel"):
            profile["hq"] = row["hqLabel"]["value"]

        exchange_label = row.get("exchangeLabel", {}).get("value")
        if not exchange_label:
            continue
        is_preferred = exchange_label.lower() in PREFERRED_EXCHANGES
        already_preferred = (profile["exchange"] or "").lower() in PREFERRED_EXCHANGES
        if profile["exchange"] is None or (is_preferred and not already_preferred):
            profile["exchange"] = exchange_label
            profile["ticker"] = row["ticker"]["value"] if row.get("ticker") else None
    return profile


def _parse_structure_rows(rows: list[dict]) -> dict:
    parent = None
    subsidiaries = []
    for row in rows:
        company_qid = _qid_from_uri(row["company"]["value"])
        name = row.get("companyLabel", {}).get("value")
        if not name or name == company_qid:
            continue  # unresolved label — data-quality noise, skip
        entry = {"id": company_qid, "name": name}
        if row["relation"]["value"] == "parent":
            parent = entry
        else:
            subsidiaries.append(entry)
    return {"parent": parent, "subsidiaries": subsidiaries}


def load_company_profile(company_id: str) -> dict:
    """Return company profile facts and corporate structure from Wikidata.

    Profile facts: industry, founding year, HQ, stock exchange, ticker symbol. Structure:
    parent organization (if any) and subsidiaries. The `ticker` this returns is what
    `load_fundamentals`/`load_corporate_actions` use to look up the same company in Sharadar —
    the two sources connect through it rather than a second hardcoded ticker table.
    """
    qid = COMPANY_WIKIDATA_QID[company_id]
    profile = _parse_profile_rows(_sparql(_profile_query(qid)))
    structure = _parse_structure_rows(_sparql(_structure_query(qid)))
    return {**profile, **structure}


def _parse_nyt_docs(docs: list[dict]) -> list[dict]:
    return [
        {
            "id": doc["_id"],
            "title": doc.get("headline", {}).get("main", ""),
            "text": doc.get("abstract") or doc.get("snippet") or "",
            "url": doc.get("web_url"),
            "published_at": (doc.get("pub_date") or "")[:10],
        }
        for doc in docs
    ]


def _nyt_get(params: dict) -> dict:
    # NYT's free-tier limit is 5 requests PER MINUTE (not per second — a previous version of
    # this comment had that wrong by 60x, which is exactly why load_news used to hit 429s so
    # fast: a 6s inter-page sleep is a ~10 req/min pace, already double the real limit), plus
    # 500 requests/day. Retry with backoff (honoring Retry-After when NYT sends one) rather than
    # crashing on the first 429, matching the pattern _sparql already uses for Wikidata.
    for attempt in range(4):
        resp = httpx.get(NYT_SEARCH_URL, params=params, timeout=20)
        if resp.status_code == 429:
            if attempt < 3:
                time.sleep(int(resp.headers.get("Retry-After", 30)))
                continue
            break  # last attempt: fall through to the RuntimeError below, not raise_for_status
        resp.raise_for_status()
        return resp.json()
    raise RuntimeError("NYT Article Search API unavailable after retries (rate-limited)")


def load_news(company_id: str, start_date: str, end_date: str) -> list[dict]:
    """Return news articles mentioning the company from the NYT Article Search API.

    start_date/end_date are "YYYY-MM-DD" strings. Paginates a handful of pages, sleeping
    between requests to stay under NYT's actual free-tier rate limit — 5 requests/minute (see
    _nyt_get) — so calling this for multiple companies back-to-back (as the notebook does)
    doesn't burn through it either.
    """
    if not settings.nyt_api_key:
        raise RuntimeError(
            "NYT_API_KEY is not set — get a free key at https://developer.nytimes.com/get-started "
            "and add it to .env before calling load_news."
        )

    query_name = COMPANY_DISPLAY_NAME.get(company_id, company_id)
    articles: list[dict] = []
    for page in range(3):
        data = _nyt_get(
            {
                "q": query_name,
                "begin_date": start_date.replace("-", ""),
                "end_date": end_date.replace("-", ""),
                "api-key": settings.nyt_api_key,
                "page": page,
            }
        )
        docs = data["response"]["docs"]
        if not docs:
            break
        articles.extend(_parse_nyt_docs(docs))
        # 60s / 5 requests, plus margin. Sleep even after the last page of this call (not just
        # between pages) so a follow-up load_news call for another company — the notebook loops
        # over 3M/APPLE back-to-back — doesn't restart the pace from zero.
        time.sleep(13)
    return articles


# --- Sharadar — fundamentals + corporate actions ------------------------------------------------
#
# Unlike Wikidata/NYT, this is a paid vendor dataset. Requested via Sharadar's own REST API
# (api.sharadar.com — NOT Nasdaq Data Link's "datatables" API, despite the settings/env var name
# below being a holdover from when this was written against the wrong host; see adr/0005's
# amendment). No extra client library needed.

SF1_COLUMNS = ["calendardate", "revenue", "netinc", "assets", "liabilities", "equity", "eps"]
ACTIONS_COLUMNS = ["date", "action", "name", "contraname"]
TICKERS_COLUMNS = ["sector", "industry"]


def _sharadar_error_detail(resp: httpx.Response) -> str:
    """Best-effort dump of why a Sharadar request failed.

    Sharadar's documented error shape is `{"error": ..., "description": ...}`, but this doesn't
    assume that schema holds for every failure mode (a gateway/CDN in front of the API can return
    its own, often non-JSON, error page) — it surfaces whatever's actually there.
    """
    try:
        body = resp.json()
        message = body.get("description") or body.get("error") or body.get("message")
        body_detail = message or str(body)[:300]
    except ValueError:
        body_detail = resp.text.strip()[:300] or "(empty response body)"

    rate_limit_headers = {k: v for k, v in resp.headers.items() if "ratelimit" in k.lower() or k.lower() == "retry-after"}
    headers_detail = f", headers: {rate_limit_headers}" if rate_limit_headers else ""
    return f"body: {body_detail}{headers_detail}"


def _sharadar_get(table: str, columns: list[str], **filters: str) -> list[dict]:
    """GET one Sharadar endpoint (e.g. "fundamentals", "actions", "tickers"), scoped to
    `filters` (e.g. ticker=, dimension=) and `columns`.

    Sharadar's API returns `{"count": N, "data": [{...}, ...]}` — already one dict per row (no
    column/row zipping needed, unlike the old Nasdaq Data Link "datatables" shape this was
    originally written against). `format=json` must be requested explicitly; the API defaults to
    CSV otherwise.
    """
    if not settings.nasdaq_data_link_api_key:
        raise RuntimeError(
            "NASDAQ_DATA_LINK_API_KEY is not set — a Sharadar API key is required; add it to "
            ".env before calling this."
        )
    params = {
        "fields": ",".join(columns),
        "api_key": settings.nasdaq_data_link_api_key,
        "format": "json",
        **filters,
    }
    for attempt in range(4):
        resp = httpx.get(f"{SHARADAR_BASE_URL}/{table}", params=params, timeout=30)
        if resp.status_code == 429:
            raise RuntimeError(f"Sharadar {table} rate-limited — {_sharadar_error_detail(resp)}")
        if resp.status_code in (502, 503, 504) and attempt < 3:
            time.sleep(3 * (attempt + 1))
            continue
        if resp.status_code >= 400:
            raise RuntimeError(f"Sharadar {table} request failed ({resp.status_code}) — {_sharadar_error_detail(resp)}")
        return resp.json()["data"]
    raise RuntimeError(f"Sharadar {table} unavailable after retries (repeated 5xx)")


def _parse_sf1_rows(rows: list[dict]) -> list[dict]:
    return sorted(
        (
            {
                "calendardate": row["calendardate"],
                "revenue": row.get("revenue"),
                "netinc": row.get("netinc"),
                "assets": row.get("assets"),
                "liabilities": row.get("liabilities"),
                "equity": row.get("equity"),
                "eps": row.get("eps"),
            }
            for row in rows
        ),
        key=lambda r: r["calendardate"],
    )


def load_fundamentals(ticker: str, dimension: str = "ARY") -> list[dict]:
    """Return annual fundamentals (revenue, net income, assets, liabilities, equity, eps) for
    a ticker from Sharadar's fundamentals endpoint — one row per fiscal year.

    dimension="ARY" is Sharadar's "as-reported annual" cut — see
    https://sharadar.com/docs/fundamentals for the full dimension taxonomy (ARQ/ART/MRY/MRQ/MRT
    — quarterly cuts, restated vs. as-reported, trailing-twelve-month) if a different slice is
    needed.
    """
    rows = _sharadar_get("fundamentals", SF1_COLUMNS, ticker=ticker, dimension=dimension)
    return _parse_sf1_rows(rows)


# Verified against a live response for MMM (2026-08-26): the `action` taxonomy for a single
# ticker is small (dividend, spinoff, spinoffdividend) but "dividend" recurs quarterly forever —
# 39 of 42 rows for MMM alone — and drowns out the one-off events (e.g. the 2024-04-01 Solventum
# spinoff) that HAD_EVENT is meant to surface. adr/0005 originally hoped for mergers/name changes
# too, but neither has ever actually shown up for MMM or AAPL — so "dividend" is excluded because
# it's noise, not because the rest of the intended taxonomy is present and just needs filtering.
EXCLUDED_ACTIONS = {"dividend"}


def _parse_actions_rows(rows: list[dict]) -> list[dict]:
    return sorted(
        (
            {
                "date": row["date"],
                "action": row["action"],
                "name": row.get("name"),
                "contraname": row.get("contraname"),
            }
            for row in rows
            if row.get("action") not in EXCLUDED_ACTIONS
        ),
        key=lambda r: r["date"],
    )


def load_corporate_actions(ticker: str) -> list[dict]:
    """Return dated corporate actions for a ticker from Sharadar's actions endpoint — this is
    what backs the graph's `Event` nodes.

    ADR 0005 originally assumed this table would cover mergers and legal name changes alongside
    splits/spinoffs; checked live (2026-08-26, MMM and AAPL), the real `action` taxonomy this
    endpoint has ever returned for either ticker is just dividend/spinoff/spinoffdividend/split
    — no merger or name-change action type has been observed. Treat "mergers, name changes" as
    NOT covered by this source; a question asking for those needs a different one entirely (this
    endpoint has no such data to be fetched with different arguments). Excludes routine dividend
    entries (see EXCLUDED_ACTIONS) — everything else Sharadar returns is passed through as-is.
    """
    rows = _sharadar_get("actions", ACTIONS_COLUMNS, ticker=ticker)
    return _parse_actions_rows(rows)


def _parse_tickers_row(rows: list[dict]) -> dict:
    row = rows[0] if rows else {}
    return {"sector": row.get("sector"), "industry": row.get("industry")}


def load_sector_classification(ticker: str) -> dict:
    """Return Sharadar's own sector/industry classification for a ticker (Sharadar's tickers
    endpoint).

    Deliberately kept separate from Wikidata's `industry` (load_company_profile) rather than
    merged — a financial-data vendor's taxonomy and a crowdsourced one can legitimately classify
    the same company differently; see adr/0005 for why that's surfaced rather than papered over.
    """
    rows = _sharadar_get("tickers", TICKERS_COLUMNS, ticker=ticker)
    return _parse_tickers_row(rows)
