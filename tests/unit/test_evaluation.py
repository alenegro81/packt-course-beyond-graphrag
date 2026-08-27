from financial_advisor.evaluation.metrics import aggregate_by_system, aggregate_scores, score_decomposed
from financial_advisor.evaluation.validators import DecomposedJudgment, JudgeScore, SubClaimJudgment


def test_judge_score_parses_from_dict():
    raw = {
        "correctness_rationale": "matches the gold figure",
        "correctness": 5,
        "completeness_rationale": "covers everything asked",
        "completeness": 5,
        "grounding_rationale": "every claim cites the context",
        "grounding": 5,
    }
    score = JudgeScore(**raw)
    assert score.correctness == 5


def test_sub_claim_judgment_parses_from_dict():
    raw = {"claim": "total net sales", "gold": "$391.035B", "rationale": "matches", "verdict": "correct"}
    claim = SubClaimJudgment(**raw)
    assert claim.verdict == "correct"


def test_decomposed_judgment_parses_list_of_sub_claims():
    raw = {
        "sub_claims": [
            {"claim": "a", "gold": "x", "rationale": "r", "verdict": "correct"},
            {"claim": "b", "gold": "y", "rationale": "r", "verdict": "incorrect"},
        ]
    }
    result = DecomposedJudgment(**raw)
    assert len(result.sub_claims) == 2


def test_score_decomposed_all_correct_is_five():
    sub_claims = [{"verdict": "correct"}, {"verdict": "correct"}]
    assert score_decomposed(sub_claims) == 5.0


def test_score_decomposed_all_incorrect_or_unaddressed_is_one():
    sub_claims = [{"verdict": "incorrect"}, {"verdict": "not_addressed"}]
    assert score_decomposed(sub_claims) == 1.0


def test_score_decomposed_mixed_gives_partial_credit_above_the_floor():
    # 2 of 3 correct should score well above the "wrong" floor a holistic judge might round down to.
    sub_claims = [{"verdict": "correct"}, {"verdict": "correct"}, {"verdict": "not_addressed"}]
    score = score_decomposed(sub_claims)
    assert 1.0 < score < 5.0
    assert score == round(1 + 4 * (2 / 3), 2)


def test_score_decomposed_partially_correct_counts_as_half_credit():
    assert score_decomposed([{"verdict": "partially_correct"}]) == 3.0


def test_score_decomposed_empty_defaults_to_floor():
    assert score_decomposed([]) == 1.0


def test_aggregate_scores_computes_mean_per_dimension():
    results = [
        {"correctness": 5, "completeness": 5, "grounding": 5},
        {"correctness": 1, "completeness": 3, "grounding": 3},
    ]
    assert aggregate_scores(results) == {"correctness": 3.0, "completeness": 4.0, "grounding": 4.0}


def test_aggregate_by_system_groups_and_averages_separately():
    results = [
        {"system": "baseline", "correctness": 1, "completeness": 1, "grounding": 1},
        {"system": "agentic", "correctness": 5, "completeness": 5, "grounding": 5},
        {"system": "agentic", "correctness": 3, "completeness": 3, "grounding": 3},
    ]
    agg = aggregate_by_system(results)
    assert agg["baseline"]["correctness"] == 1.0
    assert agg["agentic"]["correctness"] == 4.0
