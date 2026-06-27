def aggregate_scores(results: list[dict]) -> dict:
    """Compute mean scores across a set of judge_answer results."""
    keys = ["correctness", "completeness", "grounding"]
    return {k: sum(r[k] for r in results) / len(results) for k in keys}
