from financial_advisor.clients import get_llm
from financial_advisor.evaluation.metrics import score_decomposed
from financial_advisor.evaluation.prompts import (
    DECOMPOSITION_SYSTEM_PROMPT,
    JUDGE_SYSTEM_PROMPT,
    build_decomposition_prompt,
    build_judge_prompt,
)
from financial_advisor.evaluation.validators import DecomposedJudgment, JudgeScore


def judge_answer(question: str, answer: str, ground_truth: str, context: str | None = None) -> dict:
    """Score a candidate answer against a gold answer on correctness, completeness, grounding.

    Always reference-based for correctness/completeness — scored relative to `ground_truth`,
    never in a vacuum. `context` (the retrieved chunks/growing_knowledge the system actually
    generated the answer from — e.g. `qa.baseline.build_context(chunks)` or an agent's
    `result["growing_knowledge"]`) drives `grounding` separately: with it, grounding checks
    faithfulness to what the system actually saw (catches hallucination independent of whether
    the answer happens to be correct); without it, grounding falls back to the gold answer as a
    weaker proxy reference.

    Temperature is left at the client default (1); this Azure deployment rejects temperature=0
    (see `text2cypher/chain.py`'s equivalent note), so determinism isn't a lever available here —
    the rationale-first schema and anchored rubric in `evaluation.prompts` substitute for it. See
    docs/adr/0011-llm-judge-bias-mitigation.md for the full design rationale.

    Returns a dict with keys: correctness, completeness, grounding (each 1-5), rationale.
    """
    model = get_llm()
    result: JudgeScore = model.with_structured_output(JudgeScore).invoke(
        [
            {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
            {"role": "user", "content": build_judge_prompt(question, answer, ground_truth, context=context)},
        ]
    )
    return {
        "correctness": result.correctness,
        "completeness": result.completeness,
        "grounding": result.grounding,
        "rationale": (
            f"Correctness: {result.correctness_rationale}\n"
            f"Completeness: {result.completeness_rationale}\n"
            f"Grounding: {result.grounding_rationale}"
        ),
    }


def judge_answer_decomposed(question: str, answer: str, ground_truth: str) -> dict:
    """Break a multi-part question into sub-claims and judge the candidate sub-claim by
    sub-claim, instead of with one holistic score.

    Recovers partial credit `judge_answer` rounds away on multi-part questions — see the Module 7
    notebook's worked example, where a single holistic call scores a mostly-right answer as
    outright wrong while this recovers the 2-of-3-correct signal. The `correctness` score
    returned here is computed from the sub-claim verdicts in code
    (`metrics.score_decomposed`), not requested from the model, so it can never silently
    disagree with the model's own itemized judgments.

    Returns a dict with keys: correctness (1-5, derived), sub_claims (list of dicts with claim/
    gold/rationale/verdict), rationale (one line per sub-claim).
    """
    model = get_llm()
    result: DecomposedJudgment = model.with_structured_output(DecomposedJudgment).invoke(
        [
            {"role": "system", "content": DECOMPOSITION_SYSTEM_PROMPT},
            {"role": "user", "content": build_decomposition_prompt(question, answer, ground_truth)},
        ]
    )
    sub_claims = [c.model_dump() for c in result.sub_claims]
    return {
        "correctness": score_decomposed(sub_claims),
        "sub_claims": sub_claims,
        "rationale": "\n".join(f"[{c['verdict']}] {c['claim']}: {c['rationale']}" for c in sub_claims),
    }
