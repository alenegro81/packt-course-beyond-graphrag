import pytest

from financial_advisor.enrichment.loaders import (
    _matches_filing_year,
    _overlaps_filing_year,
    _parse_actions_rows,
    _parse_career_rows,
    _parse_nyt_docs,
    _parse_officer_rows,
    _parse_profile_rows,
    _parse_sf1_rows,
    _parse_structure_rows,
    _parse_tickers_row,
    load_corporate_actions,
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


def test_overlaps_filing_year():
    assert _overlaps_filing_year(None, None) is True
    assert _overlaps_filing_year("2015-01-01T00:00:00Z", None) is True
    assert _overlaps_filing_year("2019-01-01T00:00:00Z", None) is False
    assert _overlaps_filing_year(None, "2017-01-01T00:00:00Z") is False
    assert _overlaps_filing_year("2010-01-01T00:00:00Z", "2020-01-01T00:00:00Z") is True


def test_matches_filing_year_false_when_no_tenure_data_at_all():
    assert _matches_filing_year([], "chief executive") is False


def test_matches_filing_year_true_when_no_matching_title():
    assert _matches_filing_year([{"positionLabel": {"value": "senator"}}], "chief executive") is True


def test_matches_filing_year_true_when_matching_title_has_no_dates():
    rows = [{"positionLabel": {"value": "chief executive officer"}}]
    assert _matches_filing_year(rows, "chief executive") is True


def test_matches_filing_year_false_when_dated_tenure_excludes_filing_year():
    rows = [
        {
            "positionLabel": {"value": "chief executive officer"},
            "start": {"value": "2024-05-01T00:00:00Z"},
        }
    ]
    assert _matches_filing_year(rows, "chief executive") is False


def test_matches_filing_year_true_when_dated_tenure_covers_filing_year():
    rows = [
        {
            "positionLabel": {"value": "chief executive officer"},
            "start": {"value": "2018-07-01T00:00:00Z"},
            "end": {"value": "2024-05-01T00:00:00Z"},
        }
    ]
    assert _matches_filing_year(rows, "chief executive") is True


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
