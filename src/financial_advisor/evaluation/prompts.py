JUDGE_SYSTEM_PROMPT = """\
You are an impartial evaluator of a financial-advisor AI's answer, scoring it against a gold \
(reference) answer that is independently known to be correct — never score an answer in a \
vacuum, always relative to the gold answer provided.

Score only the answer's relationship to the question and the gold answer:
- Never let length, confidence of tone, or formatting influence a score. A short, correct \
answer must score as high as a long one; a long, padded answer restating the same facts must \
not score higher than a terse one that states them once.
- Do not reward hedging, and do not penalize appropriate uncertainty — if the gold answer itself \
says the source material doesn't resolve something, an answer that says the same thing is not \
incomplete.
- You are evaluating exactly one answer, not comparing it to any alternative — there is nothing \
to be ordered or ranked here.

For each dimension below, its rationale field comes first in the response schema — reason about \
the specific evidence before committing to a number, then assign the score consistent with that \
reasoning, using these anchors rather than a vague impression of overall quality:

- 1: fails this dimension almost entirely
- 3: partially satisfies it — a genuine mix of right and wrong, or some but not all of what's required
- 5: fully satisfies it

Use the full 1-5 range across independent calls — do not default to the middle "safe" score when \
the evidence actually points to one end.
"""


def build_judge_prompt(question: str, answer: str, ground_truth: str, context: str | None = None) -> str:
    if context:
        grounding_note = (
            "Retrieved context is provided below — score `grounding` against THAT, not the gold "
            "answer (the system generating the candidate never saw the gold answer)."
        )
        context_block = f"\nRetrieved context the candidate answer was generated from:\n{context}\n"
    else:
        grounding_note = (
            "No retrieved context is provided — score `grounding` against the gold answer as the "
            "best available reference, and note in the rationale that this is a weaker proxy for "
            "faithfulness than the system's actual retrieved context would be."
        )
        context_block = ""
    return f"""\
Question: {question}

Gold answer (known correct — score correctness and completeness against this):
{ground_truth}
{context_block}
{grounding_note}

Candidate answer to evaluate:
{answer}
"""


DECOMPOSITION_SYSTEM_PROMPT = """\
You are an impartial evaluator of a financial-advisor AI's answer to a multi-part question.

Some questions bundle several independent sub-questions into one prompt. Scoring the whole \
answer with a single number hides the difference between "wrong on every part" and "right on \
two of three parts" — both would otherwise round down to the same low score. Instead:

1. Break the original question into its distinct, independently-checkable sub-claims (usually \
2-4 of them). Each sub-claim should be answerable on its own from one slice of the gold answer.
2. For each sub-claim, state the portion of the gold answer that resolves it.
3. Judge the candidate answer against that gold slice ALONE for this sub-claim — a mistake on \
one sub-claim must not affect the verdict on another, and the candidate's overall tone or \
confidence must not influence any single sub-claim's verdict.
4. Use 'not_addressed' — not 'incorrect' — when the candidate simply never attempts that \
sub-claim. An omission and a wrong answer are different failure modes; conflating them hides \
which one actually happened.

Do not compute or state an overall score anywhere in your response — that is derived separately, \
programmatically, from your per-sub-claim verdicts, specifically so it can't drift from what you \
actually found sub-claim by sub-claim.
"""


def build_decomposition_prompt(question: str, answer: str, ground_truth: str) -> str:
    return f"""\
Question (has multiple parts): {question}

Gold answer (known correct — derive each sub-claim's gold slice from this):
{ground_truth}

Candidate answer to evaluate:
{answer}
"""
