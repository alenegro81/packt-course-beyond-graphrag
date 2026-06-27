from financial_advisor.clients import get_llm


def judge_answer(question: str, answer: str, ground_truth: str) -> dict:
    """Use an LLM to score an answer against a ground truth on correctness, completeness, and grounding.

    Returns a dict with keys: correctness, completeness, grounding (each 1-5), rationale.
    """
    raise NotImplementedError
