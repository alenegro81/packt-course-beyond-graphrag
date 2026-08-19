"""Loaders for structured data sources: Wikidata (executives) and the NYT Article Search API (news)."""

from __future__ import annotations

import time

import httpx

from financial_advisor.config import settings

WIKIDATA_SPARQL_URL = "https://query.wikidata.org/sparql"
WIKIDATA_API_URL = "https://www.wikidata.org/w/api.php"
WIKIPEDIA_SUMMARY_URL = "https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
NYT_SEARCH_URL = "https://api.nytimes.com/svc/search/v2/articlesearch.json"

USER_AGENT = "BeyondGraphRAGCourse/0.1 (Packt course notebook; contact: alenegro81@gmail.com)"

# company_id -> Wikidata QID / display name used to query external sources.
COMPANY_WIKIDATA_QID = {"3M": "Q159433", "APPLE": "Q312"}
COMPANY_DISPLAY_NAME = {"3M": "3M", "APPLE": "Apple Inc."}
_QID_TO_COMPANY_ID = {qid: company_id for company_id, qid in COMPANY_WIKIDATA_QID.items()}

# The fiscal year of the 10-Ks ingested in Module 1 — scopes the board roster to the people
# actually relevant to those filings, instead of pulling decades of historical turnover.
FILING_YEAR = 2018


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
        if resp.status_code == 429 and attempt < 3:
            time.sleep(int(resp.headers.get("Retry-After", 5)))
            continue
        if resp.status_code in (502, 503, 504) and attempt < 3:
            time.sleep(3 * (attempt + 1))
            continue
        resp.raise_for_status()
        return resp.json()["results"]["bindings"]
    raise RuntimeError("Wikidata SPARQL endpoint unavailable after retries")


def _officers_query(qid: str) -> str:
    return f"""
    SELECT ?person ?personLabel ?positionLabel ?start ?end WHERE {{
      VALUES ?company {{ wd:{qid} }}
      {{ ?company wdt:P169 ?person . BIND("Chief Executive Officer" AS ?positionLabel) }}
      UNION
      {{ ?company wdt:P488 ?person . BIND("Chairperson" AS ?positionLabel) }}
      UNION
      {{ ?company p:P3320 ?stmt . ?stmt ps:P3320 ?person .
         OPTIONAL {{ ?stmt pq:P580 ?start }} OPTIONAL {{ ?stmt pq:P582 ?end }}
         BIND("Board Member" AS ?positionLabel) }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
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
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }}
    """


def _tenure_query(person_qid: str) -> str:
    return f"""
    SELECT ?positionLabel ?start ?end WHERE {{
      wd:{person_qid} p:P39 ?stmt .
      ?stmt ps:P39 ?position .
      OPTIONAL {{ ?stmt pq:P580 ?start }}
      OPTIONAL {{ ?stmt pq:P582 ?end }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
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


# Wikidata's org-level P169/P488 (CEO/chairperson) only reflect the *current* holder, with no
# tenure dates — so for these two titles we cross-check against the person's own P39 (position
# held) history, which does carry start/end qualifiers, to see if they actually held the title
# during FILING_YEAR (see _matches_filing_year).
_TITLE_KEYWORDS = {"Chief Executive Officer": "chief executive", "Chairperson": "chair"}


def _matches_filing_year(tenure_rows: list[dict], keyword: str) -> bool:
    """True if a P39 tenure row matching `keyword` overlaps FILING_YEAR.

    No P39 data at all (common for a company's *current* officer, who Wikidata often records
    only via the org-level P169/P488 claim) can't be confirmed relevant, so it's excluded. But
    if the person has *some* P39 history just not a dated record of this exact title, or a
    matching record with no dates, we keep them (better recall than precision from there on).
    """
    if not tenure_rows:
        return False
    matching = [
        r for r in tenure_rows if keyword in (r.get("positionLabel", {}).get("value") or "").lower()
    ]
    if not matching:
        return True
    dated = [r for r in matching if r.get("start") or r.get("end")]
    if not dated:
        return True
    return any(
        _overlaps_filing_year(r.get("start", {}).get("value"), r.get("end", {}).get("value"))
        for r in dated
    )


def _parse_officer_rows(rows: list[dict]) -> list[dict]:
    """Group raw SPARQL officer/board-member bindings into one record per person.

    A person can hold more than one title at the same company (e.g. CEO and board member),
    so each record's `titles` is a list rather than a single flat title.
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
        if title == "Board Member" and not _overlaps_filing_year(start, end):
            continue
        person = people.setdefault(person_qid, {"id": person_qid, "name": name, "titles": []})
        person["titles"].append({"title": title, "start": start, "end": end})
    return list(people.values())


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


def load_executives(company_id: str) -> list[dict]:
    """Return executive/board records for a company from Wikidata.

    Each record includes `career_history` — prior employers with title and start/end dates,
    pulled from the person's own Wikidata entity (P108 employer claims). This is the data that
    fills the gap Module 2 hit: a 10-K names its officers but defers their career history to a
    proxy statement that was never ingested.
    """
    qid = COMPANY_WIKIDATA_QID[company_id]
    people = _parse_officer_rows(_sparql(_officers_query(qid)))

    executives = []
    for i, person in enumerate(people):
        if i > 0:
            time.sleep(1)  # stay well under Wikidata's SPARQL rate limit

        titles = person["titles"]
        undated_titles = [t for t in titles if t["title"] in _TITLE_KEYWORDS]
        if undated_titles:
            tenure_rows = _sparql(_tenure_query(person["id"]))
            titles = [
                t
                for t in titles
                if t["title"] not in _TITLE_KEYWORDS
                or _matches_filing_year(tenure_rows, _TITLE_KEYWORDS[t["title"]])
            ]
        if not titles:
            continue  # e.g. the current CEO/chairperson, but not as of FILING_YEAR

        executives.append(
            {
                "id": person["id"],
                "name": person["name"],
                "titles": titles,
                "bio": _wikipedia_bio(person["id"]),
                "career_history": _parse_career_rows(_sparql(_career_history_query(person["id"]))),
            }
        )
    return executives


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


def load_news(company_id: str, start_date: str, end_date: str) -> list[dict]:
    """Return news articles mentioning the company from the NYT Article Search API.

    start_date/end_date are "YYYY-MM-DD" strings. Paginates a handful of pages, sleeping
    between requests to stay well under NYT's free-tier rate limit (5 req/sec, 500 req/day).
    """
    if not settings.nyt_api_key:
        raise RuntimeError(
            "NYT_API_KEY is not set — get a free key at https://developer.nytimes.com/get-started "
            "and add it to .env before calling load_news."
        )

    query_name = COMPANY_DISPLAY_NAME.get(company_id, company_id)
    articles: list[dict] = []
    for page in range(3):
        resp = httpx.get(
            NYT_SEARCH_URL,
            params={
                "q": query_name,
                "begin_date": start_date.replace("-", ""),
                "end_date": end_date.replace("-", ""),
                "api-key": settings.nyt_api_key,
                "page": page,
            },
            timeout=20,
        )
        resp.raise_for_status()
        docs = resp.json()["response"]["docs"]
        if not docs:
            break
        articles.extend(_parse_nyt_docs(docs))
        if page < 2:
            time.sleep(6)
    return articles
