import pytest

from financial_advisor.enrichment.loaders import (
    _matches_filing_year,
    _overlaps_filing_year,
    _parse_career_rows,
    _parse_nyt_docs,
    _parse_officer_rows,
    load_news,
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
