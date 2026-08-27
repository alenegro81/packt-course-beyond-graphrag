from financial_advisor.extraction.validators import EntityType
from financial_advisor.similarity.candidates import find_fuzzy_candidates, node_match_clause
from financial_advisor.similarity.rerank import _drop_near_duplicates
from financial_advisor.similarity.resolver import pick_canonical_name
from financial_advisor.similarity.validators import CandidateNode, ResolutionResult


def _node(label: str, name: str, **key) -> CandidateNode:
    return CandidateNode(label=label, key=key, name=name, entity_type=EntityType.COMPANY)


def test_node_match_clause_for_recognised_entity():
    node = _node("RecognisedEntity", "3M Company", string="3M Company", doc_id="3M/3M_2025_10K.pdf")
    clause, params = node_match_clause(node)
    assert "RecognisedEntity" in clause
    assert params == {"string": "3M Company", "doc_id": "3M/3M_2025_10K.pdf"}


def test_node_match_clause_for_curated_node():
    node = _node("Company", "3M", id="3M")
    clause, params = node_match_clause(node)
    assert "MATCH (n:Company {id: $id})" == clause
    assert params == {"id": "3M"}


def test_find_fuzzy_candidates_matches_name_variants():
    target = _node("Company", "3M Company", id="3M")
    pool = [
        _node("RecognisedEntity", "3M", string="3M", doc_id="doc1"),
        _node("RecognisedEntity", "Apple Inc.", string="Apple Inc.", doc_id="doc2"),
    ]
    matches = find_fuzzy_candidates(target, pool, threshold=60)
    assert [m.name for m in matches] == ["3M"]


def test_find_fuzzy_candidates_returns_empty_for_empty_pool():
    target = _node("Company", "3M Company", id="3M")
    assert find_fuzzy_candidates(target, []) == []


def test_find_fuzzy_candidates_respects_threshold():
    target = _node("Company", "3M Company", id="3M")
    pool = [_node("RecognisedEntity", "Totally Unrelated Corp", string="Totally Unrelated Corp", doc_id="doc1")]
    assert find_fuzzy_candidates(target, pool, threshold=90) == []


def test_pick_canonical_name_prefers_curated_node():
    members = [
        _node("RecognisedEntity", "3M", string="3M", doc_id="doc1"),
        _node("Company", "3M Company", id="3M"),
    ]
    assert pick_canonical_name(members) == "3M Company"


def test_pick_canonical_name_falls_back_to_longest_when_no_curated_node():
    members = [
        _node("RecognisedEntity", "3M", string="3M", doc_id="doc1"),
        _node("RecognisedEntity", "3M Company", string="3M Company", doc_id="doc2"),
    ]
    assert pick_canonical_name(members) == "3M Company"


def test_resolution_result_parses_from_dict():
    raw = {"judgments": [{"index": 0, "same_entity": True, "reason": "Same ticker and name"}]}
    result = ResolutionResult(**raw)
    assert len(result.judgments) == 1
    assert result.judgments[0].same_entity is True


def test_drop_near_duplicates_keeps_first_seen_of_a_pair():
    chunks = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
    deduped = _drop_near_duplicates(chunks, [("a", "b")])
    assert [c["id"] for c in deduped] == ["a", "c"]


def test_drop_near_duplicates_no_pairs_keeps_everything():
    chunks = [{"id": "a"}, {"id": "b"}]
    assert _drop_near_duplicates(chunks, []) == chunks


def test_drop_near_duplicates_is_not_transitive():
    # a~b and b~c, but a and c are not paired directly: b is dropped (paired with kept a), but
    # c survives — it's only ever compared against KEPT chunks, not dropped ones.
    chunks = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
    deduped = _drop_near_duplicates(chunks, [("a", "b"), ("b", "c")])
    assert [c["id"] for c in deduped] == ["a", "c"]


def test_drop_near_duplicates_pair_order_is_symmetric():
    chunks = [{"id": "a"}, {"id": "b"}]
    assert _drop_near_duplicates(chunks, [("b", "a")]) == [{"id": "a"}]
