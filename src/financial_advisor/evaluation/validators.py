from typing import Literal

from pydantic import BaseModel, Field


class JudgeScore(BaseModel):
    """Reference-based judgment of one answer against a gold answer, one dimension at a time.

    Each score field is preceded by its own rationale field so the model has to state its
    reasoning before committing to a number, rather than the reverse — a structured-output
    analogue of "think before you answer" that measurably reduces snap, unjustified scores. See
    docs/adr/0011-llm-judge-bias-mitigation.md for why this field order is deliberate.
    """

    correctness_rationale: str = Field(
        description=(
            "Compare the answer's factual content to the gold answer. Note any figures, dates, "
            "or claims that are right, wrong, or missing. Judge factual accuracy only — not "
            "style, tone, or length."
        )
    )
    correctness: int = Field(
        ge=1,
        le=5,
        description=(
            "1=contradicts the gold answer on its central claim; 3=partially correct, a mix of "
            "right and wrong or missing facts; 5=fully matches the gold answer's facts"
        ),
    )
    completeness_rationale: str = Field(
        description=(
            "Check the answer against every part of what the question asked, using the gold "
            "answer as the checklist. List anything the gold answer addresses that this answer "
            "omits."
        )
    )
    completeness: int = Field(
        ge=1,
        le=5,
        description=(
            "1=addresses none of what was asked; 3=addresses some but not all parts of a "
            "multi-part question; 5=addresses everything the question asked for"
        ),
    )
    grounding_rationale: str = Field(
        description=(
            "Check whether every claim in the answer is traceable to the retrieved context it "
            "was generated from (if provided) — or to the gold answer, when no retrieved context "
            "is given. Ignore whether an invented fact happens to be true — judge only whether "
            "the answer is supported by what it was given, a different failure mode from "
            "correctness: a system can be faithfully grounded in context that was itself "
            "incomplete or wrong, and it can also be correct by chance while inventing an "
            "unsupported justification."
        )
    )
    grounding: int = Field(
        ge=1,
        le=5,
        description=(
            "1=largely fabricated, unsupported by what was given; 3=mixes grounded and "
            "unsupported claims; 5=every claim traceable to what was given"
        ),
    )


class SubClaimJudgment(BaseModel):
    """One independently-checkable piece of a multi-part question, judged in isolation."""

    claim: str = Field(
        description="One discrete, independently-checkable sub-question implied by the original question"
    )
    gold: str = Field(description="The portion of the gold answer that resolves this specific sub-claim")
    rationale: str = Field(
        description="Compare the candidate answer against `gold` for this sub-claim only, not the answer as a whole"
    )
    verdict: Literal["correct", "partially_correct", "incorrect", "not_addressed"] = Field(
        description="This sub-claim's verdict on its own, independent of how the other sub-claims scored"
    )


class DecomposedJudgment(BaseModel):
    """A multi-part question broken into independently-scored sub-claims.

    Decomposing guards against two failure modes a single holistic score is prone to: the halo
    effect (one wrong figure drags an otherwise-mostly-right answer down to "incorrect") and
    self-inconsistency (an LLM asked for both an itemized breakdown and one overall number in the
    same response can produce a number that doesn't match its own breakdown). The overall score
    is deliberately not requested here — `evaluation.metrics.score_decomposed` computes it from
    `sub_claims` in code instead, so it can never disagree with the model's own itemized
    judgments.
    """

    sub_claims: list[SubClaimJudgment]
