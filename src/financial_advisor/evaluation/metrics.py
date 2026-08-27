_VERDICT_CREDIT = {"correct": 1.0, "partially_correct": 0.5, "incorrect": 0.0, "not_addressed": 0.0}


def aggregate_scores(results: list[dict]) -> dict:
    """Compute mean scores across a set of judge_answer results."""
    keys = ["correctness", "completeness", "grounding"]
    return {k: sum(r[k] for r in results) / len(results) for k in keys}


def aggregate_by_system(results: list[dict]) -> dict[str, dict]:
    """Group judge_answer results by their 'system' label and average each group separately.

    Expects each result dict to carry a 'system' key (e.g. "baseline", "agentic") alongside the
    usual correctness/completeness/grounding keys — set by the caller when the same question set
    is run through more than one retrieval system, so scores stay comparable system by system
    instead of blurring into one overall mean.
    """
    systems: dict[str, list[dict]] = {}
    for r in results:
        systems.setdefault(r["system"], []).append(r)
    return {system: aggregate_scores(rs) for system, rs in systems.items()}


def score_decomposed(sub_claims: list[dict]) -> float:
    """Turn per-sub-claim verdicts into one 1-5 correctness score, computed here rather than
    asked of the LLM — see evaluation.judge.judge_answer_decomposed for why."""
    if not sub_claims:
        return 1.0
    fraction = sum(_VERDICT_CREDIT[c["verdict"]] for c in sub_claims) / len(sub_claims)
    return round(1 + 4 * fraction, 2)
