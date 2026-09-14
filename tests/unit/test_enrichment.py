import pytest

from financial_advisor.enrichment.loaders import (
    _nyt_get,
    _overlaps_filing_year,
    _parse_actions_rows,
    _parse_career_rows,
    _parse_nyt_docs,
    _parse_officer_rows,
    _parse_profile_rows,
    _parse_sf1_rows,
    _parse_structure_rows,
    _parse_tickers_row,
    _reconcile_self_references,
    load_corporate_actions,
    load_executives,
    load_fundamentals,
    load_news,
    load_sector_classification,
)


def _binding(**kwargs) -> dict:
    return {k: {"value": v} for k, v in kwargs.items() if v is not None}


def test_parse_officer_rows_groups_multiple_titles_per_person():
    rows = [
        {
            "person": {"value": "http://www.wikidata.org/entity/Q123"},
            **_binding(personLabel="Mike Roman", positionLabel="Chief Executive Officer"),
        },
        {
            "person": {"value": "http://www.wikidata.org/entity/Q123"},
            **_binding(
                personLabel="Mike Roman",
                positionLabel="Board Member",
                start="2018-05-08T00:00:00Z",
            ),
        },
    ]
    people = _parse_officer_rows(rows)
    assert len(people) == 1
    assert people[0]["id"] == "Q123"
    assert [t["title"] for t in people[0]["titles"]] == [
        "Chief Executive Officer",
        "Board Member",
    ]


def test_parse_officer_rows_skips_unresolved_labels():
    rows = [
        {
            "person": {"value": "http://www.wikidata.org/entity/Q999"},
            "positionLabel": {"value": "Board Member"},
            # personLabel missing -> SPARQL label service failed to resolve, falls back to QID
        },
    ]
    assert _parse_officer_rows(rows) == []


def test_parse_officer_rows_filters_board_member_outside_filing_year():
    rows = [
        {
            "person": {"value": "http://www.wikidata.org/entity/Q1"},
            **_binding(
                personLabel="Past Member",
                positionLabel="Board Member",
                start="2000-01-01T00:00:00Z",
                end="2010-01-01T00:00:00Z",
            ),
        },
        {
            "person": {"value": "http://www.wikidata.org/entity/Q2"},
            **_binding(
                personLabel="Current Member",
                positionLabel="Board Member",
                start="2015-01-01T00:00:00Z",
            ),
        },
    ]
    people = _parse_officer_rows(rows)
    assert [p["name"] for p in people] == ["Current Member"]


def test_parse_officer_rows_filters_dated_ceo_outside_filing_year():
    # Regression: P169/P488 statements now carry their own start/end qualifiers (queried via
    # p:/ps:/pq: rather than the truthy wdt: shortcut, which only surfaces the best-ranked
    # statement and can drop the officer actually in office during FILING_YEAR), so CEO/
    # chairperson rows are scoped by date exactly like board members.
    rows = [
        {
            "person": {"value": "http://www.wikidata.org/entity/Q1"},
            **_binding(
                personLabel="Former CEO",
                positionLabel="Chief Executive Officer",
                start="2000-01-01T00:00:00Z",
                end="2010-01-01T00:00:00Z",
            ),
        },
        {
            "person": {"value": "http://www.wikidata.org/entity/Q2"},
            **_binding(
                personLabel="Current CEO",
                positionLabel="Chief Executive Officer",
                start="2015-01-01T00:00:00Z",
            ),
        },
    ]
    people = _parse_officer_rows(rows)
    assert [p["name"] for p in people] == ["Current CEO"]


def test_parse_officer_rows_keeps_founders_regardless_of_filing_year():
    rows = [
        {
            "person": {"value": "http://www.wikidata.org/entity/Q1"},
            **_binding(personLabel="Company Founder", positionLabel="Founder"),
        },
    ]
    people = _parse_officer_rows(rows)
    assert [p["name"] for p in people] == ["Company Founder"]


def test_parse_officer_rows_keeps_full_history_once_person_qualifies():
    # Regression: Steve Jobs qualifies for Apple's roster via "Founder" (exempt from
    # FILING_YEAR), and Wikidata's raw P169 rows do carry his real 1997-2011 "Chief Executive
    # Officer" stint (see _officers_query) — that title must survive too, not get silently
    # stripped just because it individually predates FILING_YEAR while Founder is what let him
    # in. Filtering was previously done per-title-row instead of per-person.
    rows = [
        {
            "person": {"value": "http://www.wikidata.org/entity/Q19837"},
            **_binding(personLabel="Steve Jobs", positionLabel="Founder"),
        },
        {
            "person": {"value": "http://www.wikidata.org/entity/Q19837"},
            **_binding(
                personLabel="Steve Jobs",
                positionLabel="Chief Executive Officer",
                start="1997-09-01T00:00:00Z",
                end="2011-08-23T00:00:00Z",
            ),
        },
    ]
    people = _parse_officer_rows(rows)
    assert len(people) == 1
    assert [t["title"] for t in people[0]["titles"]] == ["Founder", "Chief Executive Officer"]


def test_load_executives_excludes_self_referential_career_history(monkeypatch):
    # Regression: a person's own P108 "employer" claims include the very company we're loading
    # executives for, almost always with no P39 title qualifier — left in, that landed as a
    # spurious ROLE_AT{title:"Employee"} edge duplicating the real title already in `titles`.
    officer_rows = [
        {
            "person": {"value": "http://www.wikidata.org/entity/Q1"},
            **_binding(
                personLabel="Jane CEO",
                positionLabel="Chief Executive Officer",
                start="2015-01-01T00:00:00Z",
            ),
        },
    ]
    career_rows = [
        {
            "employer": {"value": "http://www.wikidata.org/entity/Q312"},
            **_binding(employerLabel="Apple Inc."),  # self-reference: no title, no dates
        },
        {
            "employer": {"value": "http://www.wikidata.org/entity/Q37156"},
            **_binding(
                employerLabel="IBM", start="2000-01-01T00:00:00Z", end="2014-01-01T00:00:00Z"
            ),
        },
    ]

    def fake_sparql(query):
        return career_rows if "P108" in query else officer_rows

    monkeypatch.setattr("financial_advisor.enrichment.loaders._sparql", fake_sparql)
    monkeypatch.setattr("financial_advisor.enrichment.loaders._wikipedia_bio", lambda qid: None)
    monkeypatch.setattr("financial_advisor.enrichment.loaders.COMPANY_WIKIDATA_QID", {"APPLE": "Q312"})

    executives = load_executives("APPLE")
    assert len(executives) == 1
    assert [h["employer"] for h in executives[0]["career_history"]] == ["IBM"]


def test_reconcile_self_references_drops_untitled_self_reference():
    # The common case (Tim Cook, Mike Roman, ...): a self-reference with a start date (their
    # actual hire date) but no P39 title — not a role, so it's dropped rather than surfacing as
    # a bogus generic "Employee" title or as fake career_history at the company we're loading for.
    titles = [{"title": "Chief Executive Officer", "start": "2011-01-01T00:00:00Z", "end": None}]
    raw_history = [
        {"employer": "APPLE", "employer_qid": "Q312", "title": None, "start": "1998-01-01T00:00:00Z", "end": None},
        {"employer": "IBM", "employer_qid": "Q37156", "title": None, "start": "1982-01-01T00:00:00Z", "end": None},
    ]
    new_titles, career_history = _reconcile_self_references(titles, raw_history, "APPLE")
    assert new_titles == titles
    assert [h["employer"] for h in career_history] == ["IBM"]


def test_reconcile_self_references_folds_in_a_genuinely_new_title():
    # A self-reference can carry a P39 title that isn't on any of the org-level P169/P488/
    # P3320/P112 claims (e.g. a President or COO Wikidata only recorded on the person's own
    # item) — that's real information the org-level query missed, so it's added to titles.
    titles = [{"title": "Board Member", "start": "2015-01-01T00:00:00Z", "end": None}]
    raw_history = [
        {
            "employer": "APPLE",
            "employer_qid": "Q312",
            "title": "chief operating officer",
            "start": "2007-01-01T00:00:00Z",
            "end": "2011-08-24T00:00:00Z",
        },
    ]
    new_titles, career_history = _reconcile_self_references(titles, raw_history, "APPLE")
    assert new_titles == [
        titles[0],
        {"title": "Chief Operating Officer", "start": "2007-01-01T00:00:00Z", "end": "2011-08-24T00:00:00Z"},
    ]
    assert career_history == []


def test_reconcile_self_references_skips_case_different_duplicate_title():
    # Regression, observed live on 3M: William Brown's self-reference is titled "chief
    # executive officer" — a case-different restatement of the "Chief Executive Officer" title
    # already captured from P169. Folding it in blindly would create a near-duplicate ROLE_AT
    # edge differing only by title casing.
    titles = [{"title": "Chief Executive Officer", "start": "2024-05-01T00:00:00Z", "end": None}]
    raw_history = [
        {
            "employer": "3M",
            "employer_qid": "Q159433",
            "title": "chief executive officer",
            "start": "2024-05-01T00:00:00Z",
            "end": None,
        },
    ]
    new_titles, career_history = _reconcile_self_references(titles, raw_history, "3M")
    assert new_titles == titles
    assert career_history == []


def test_overlaps_filing_year():
    assert _overlaps_filing_year(None, None) is True
    assert _overlaps_filing_year("2015-01-01T00:00:00Z", None) is True
    assert _overlaps_filing_year("2030-01-01T00:00:00Z", None) is False
    assert _overlaps_filing_year(None, "2017-01-01T00:00:00Z") is False
    assert _overlaps_filing_year("2010-01-01T00:00:00Z", "2030-01-01T00:00:00Z") is True


def test_parse_career_rows_skips_unresolved_employer_labels():
    rows = [
        {
            "employer": {"value": "http://www.wikidata.org/entity/Q37156"},
            **_binding(employerLabel="IBM", start="1982-01-01T00:00:00Z", end="1994-01-01T00:00:00Z"),
        },
        {
            "employer": {"value": "http://www.wikidata.org/entity/Q42"},
            # employerLabel missing -> falls back to QID, should be skipped
        },
    ]
    history = _parse_career_rows(rows)
    assert len(history) == 1
    assert history[0]["employer"] == "IBM"
    assert history[0]["employer_qid"] == "Q37156"


def test_parse_nyt_docs_maps_fields():
    docs = [
        {
            "_id": "nyt://article/1",
            "headline": {"main": "3M announces restructuring"},
            "abstract": "3M said today...",
            "web_url": "https://nytimes.com/1",
            "pub_date": "2018-06-01T10:00:00+0000",
        }
    ]
    articles = _parse_nyt_docs(docs)
    assert articles == [
        {
            "id": "nyt://article/1",
            "title": "3M announces restructuring",
            "text": "3M said today...",
            "url": "https://nytimes.com/1",
            "published_at": "2018-06-01",
        }
    ]


def test_load_news_raises_without_api_key(monkeypatch):
    monkeypatch.setattr("financial_advisor.enrichment.loaders.settings.nyt_api_key", "")
    with pytest.raises(RuntimeError, match="NYT_API_KEY"):
        load_news("3M", "2018-01-01", "2018-12-31")


class _FakeNYTResponse:
    def __init__(self, status_code, headers=None, payload=None):
        self.status_code = status_code
        self.headers = headers or {}
        self._payload = payload

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx

            raise httpx.HTTPStatusError(
                "error", request=httpx.Request("GET", "https://api.nytimes.com"), response=self
            )

    def json(self):
        return self._payload


def test_nyt_get_retries_on_429_honoring_retry_after(monkeypatch):
    # Regression: NYT's free-tier limit is 5 requests/MINUTE, not /second (a stale comment had
    # this off by 60x, which is why load_news used to hit 429s so fast). A 429 shouldn't crash
    # the whole load — retry with backoff, honoring Retry-After when NYT sends one, same as
    # _sparql already does for Wikidata's endpoint.
    sleeps = []
    monkeypatch.setattr("financial_advisor.enrichment.loaders.time.sleep", sleeps.append)

    responses = [
        _FakeNYTResponse(429, headers={"Retry-After": "2"}),
        _FakeNYTResponse(200, payload={"response": {"docs": []}}),
    ]
    calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append(params)
        return responses.pop(0)

    monkeypatch.setattr("financial_advisor.enrichment.loaders.httpx.get", fake_get)

    result = _nyt_get({"q": "3M"})
    assert result == {"response": {"docs": []}}
    assert sleeps == [2]
    assert len(calls) == 2


def test_nyt_get_gives_up_after_exhausting_retries(monkeypatch):
    monkeypatch.setattr("financial_advisor.enrichment.loaders.time.sleep", lambda *_: None)
    monkeypatch.setattr(
        "financial_advisor.enrichment.loaders.httpx.get",
        lambda *a, **k: _FakeNYTResponse(429, headers={"Retry-After": "1"}),
    )
    with pytest.raises(RuntimeError, match="rate-limited"):
        _nyt_get({"q": "3M"})


def test_parse_profile_rows_takes_first_non_null_per_field():
    rows = [
        _binding(industryLabel="Conglomerate", exchangeLabel="NYSE", ticker="MMM"),
        _binding(inception="2000-01-01T00:00:00Z", hqLabel="St. Paul, Minnesota"),
    ]
    profile = _parse_profile_rows(rows)
    assert profile == {
        "industry": "Conglomerate",
        "founded": 2000,
        "hq": "St. Paul, Minnesota",
        "exchange": "NYSE",
        "ticker": "MMM",
    }


def test_parse_profile_rows_prefers_us_exchange_over_first_row():
    # Regression: Apple's Wikidata P414 statements include Tokyo Stock Exchange (6689) ahead of
    # Nasdaq (AAPL) in SPARQL row order; Sharadar only covers US-listed securities, so the
    # secondary foreign listing must not win just because it happened to come first.
    rows = [
        _binding(exchangeLabel="Tokyo Stock Exchange", ticker="6689"),
        _binding(exchangeLabel="Nasdaq", ticker="AAPL"),
        _binding(exchangeLabel="Tokyo Stock Exchange", ticker="6689"),
    ]
    profile = _parse_profile_rows(rows)
    assert profile["exchange"] == "Nasdaq"
    assert profile["ticker"] == "AAPL"


def test_parse_profile_rows_all_null_when_no_data():
    assert _parse_profile_rows([]) == {
        "industry": None,
        "founded": None,
        "hq": None,
        "exchange": None,
        "ticker": None,
    }


def test_parse_structure_rows_splits_parent_and_subsidiaries():
    rows = [
        {
            "company": {"value": "http://www.wikidata.org/entity/Q1"},
            **_binding(companyLabel="Parent Co", relation="parent"),
        },
        {
            "company": {"value": "http://www.wikidata.org/entity/Q2"},
            **_binding(companyLabel="Sub One", relation="subsidiary"),
        },
    ]
    structure = _parse_structure_rows(rows)
    assert structure["parent"] == {"id": "Q1", "name": "Parent Co"}
    assert structure["subsidiaries"] == [{"id": "Q2", "name": "Sub One"}]


def test_parse_structure_rows_skips_unresolved_labels():
    rows = [
        {
            "company": {"value": "http://www.wikidata.org/entity/Q3"},
            "relation": {"value": "subsidiary"},
            # companyLabel missing -> falls back to QID, should be skipped
        }
    ]
    assert _parse_structure_rows(rows) == {"parent": None, "subsidiaries": []}


def test_parse_sf1_rows_maps_and_sorts_by_calendardate():
    rows = [
        {"calendardate": "2025-12-31", "revenue": 24948, "netinc": 1000},
        {"calendardate": "2024-12-31", "revenue": 24575, "netinc": 900},
    ]
    periods = _parse_sf1_rows(rows)
    assert [p["calendardate"] for p in periods] == ["2024-12-31", "2025-12-31"]
    assert periods[1]["revenue"] == 24948


def test_parse_actions_rows_maps_and_sorts_by_date():
    rows = [
        {"date": "2024-04-01", "action": "spinoff", "name": "3M CO", "contraname": "SOLVENTUM CORP"},
        {"date": "2019-06-01", "action": "split"},
    ]
    actions = _parse_actions_rows(rows)
    assert [a["date"] for a in actions] == ["2019-06-01", "2024-04-01"]
    assert actions[1]["contraname"] == "SOLVENTUM CORP"


def test_parse_actions_rows_excludes_routine_dividends():
    rows = [
        {"date": "2024-04-01", "action": "spinoff", "name": "3M CO", "contraname": "SOLVENTUM CORP"},
        {"date": "2024-05-23", "action": "dividend", "name": "3M CO"},
    ]
    actions = _parse_actions_rows(rows)
    assert [a["action"] for a in actions] == ["spinoff"]


def test_load_fundamentals_raises_without_api_key(monkeypatch):
    monkeypatch.setattr("financial_advisor.enrichment.loaders.settings.nasdaq_data_link_api_key", "")
    with pytest.raises(RuntimeError, match="NASDAQ_DATA_LINK_API_KEY"):
        load_fundamentals("MMM")


def test_load_corporate_actions_raises_without_api_key(monkeypatch):
    monkeypatch.setattr("financial_advisor.enrichment.loaders.settings.nasdaq_data_link_api_key", "")
    with pytest.raises(RuntimeError, match="NASDAQ_DATA_LINK_API_KEY"):
        load_corporate_actions("MMM")


def test_parse_tickers_row_maps_sector_and_industry():
    assert _parse_tickers_row([{"sector": "Industrials", "industry": "Conglomerates"}]) == {
        "sector": "Industrials",
        "industry": "Conglomerates",
    }


def test_parse_tickers_row_empty_when_no_rows():
    assert _parse_tickers_row([]) == {"sector": None, "industry": None}


def test_load_sector_classification_raises_without_api_key(monkeypatch):
    monkeypatch.setattr("financial_advisor.enrichment.loaders.settings.nasdaq_data_link_api_key", "")
    with pytest.raises(RuntimeError, match="NASDAQ_DATA_LINK_API_KEY"):
        load_sector_classification("MMM")
