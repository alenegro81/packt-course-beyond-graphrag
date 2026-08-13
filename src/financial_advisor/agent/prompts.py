from financial_advisor.agent.state import AgentState

STRATEGY_SYSTEM_PROMPT = """\
You are a financial research analyst. You have access to three tools that search a Neo4j \
knowledge graph of 10-K filings:

- semantic_search: meaning-based search over chunk embeddings. Good for concepts, themes, \
comparisons, or when you're unsure of the exact wording used in the filing.
- fulltext_search: Lucene-syntax keyword search. Good for exact terms, line items, or section \
titles. Combine terms with AND/OR; use ~ for single-word fuzzy matching (e.g. "research~ AND \
development~"). Always include the company name in the query text, or use the company_id \
argument instead.
- get_document_pages: once you know a doc_id (returned by the other two tools, e.g. \
"3M/3M_2018_10K.pdf"), pull specific pages directly for fuller context around a promising hit.

Call one or more tools per turn. Prefer semantic_search early or for broad/comparative \
questions; switch to fulltext_search once you know specific terminology; use get_document_pages \
once you've identified a promising doc_id and page range. Don't repeat an identical (tool, \
arguments) call you've already tried — vary the query, tool, or target document instead.
"""

ANSWER_SYSTEM_PROMPT = """\
You are an expert financial analyst. Answer the question using ONLY the knowledge elements \
below — you do not have access to the original documents, so treat this as your complete and \
only source of truth. Cite the source doc_id for each figure or claim. If the knowledge is \
insufficient to fully answer, say so explicitly rather than guessing.
"""


def build_strategy_prompt(state: AgentState) -> str:
    """User prompt for the retriever strategy agent: question, knowledge so far, and history."""
    tool_log = state.get("tool_call_log", [])
    if tool_log:
        log_lines = "\n".join(
            f"  {i}. {entry['tool']}({entry['args']}) -> {entry['n_results']} chunk(s)"
            for i, entry in enumerate(tool_log, start=1)
        )
    else:
        log_lines = "  (none yet)"

    feedback = state.get("retrieval_feedback") or ""
    feedback_block = f"\nFeedback from the last evaluation round:\n{feedback}\n" if feedback else ""
    growing_knowledge = state.get("growing_knowledge") or "(nothing extracted yet)"

    return f"""\
Question: {state["question"]}

Knowledge gathered so far:
{growing_knowledge}

Tool calls tried so far:
{log_lines}
{feedback_block}
Decide which tool(s) to call next to make progress on answering the question.
"""


def build_retrieval_grading_prompt(state: AgentState) -> str:
    """User prompt for grading retrieved chunks and growing the knowledge base."""
    chunks = state.get("retrieved_chunks", [])
    chunks_block = (
        "\n\n".join(
            f"[doc_id={c['doc_id']} | chunk_id={c['id']} | pages={c.get('pages')} | "
            f"score={c.get('score', 0):.3f}]\n{c['text']}"
            for c in chunks
        )
        or "(no chunks retrieved)"
    )

    return f"""\
Question: {state["question"]}

Knowledge carried over from previous rounds:
{state.get("growing_knowledge") or "(none yet)"}

All chunks retrieved so far (cumulative across rounds):
{chunks_block}

Task:
1. Decide whether the cumulative knowledge — previous rounds plus these chunks — is enough to \
fully and precisely answer the question.
2. Rewrite `growing_knowledge` as the complete, self-contained set of facts needed to answer, \
citing doc_id for each fact. This replaces what the answer generator sees — the raw chunks are \
NOT passed forward, so do not omit anything still needed.
3. If not sufficient, explain in `feedback` exactly what's missing and suggest the next tool, \
query, or document to try.
"""


def build_answer_prompt(state: AgentState) -> str:
    """User prompt for the answer generator: growing knowledge only, no raw chunks."""
    feedback = state.get("answer_feedback") or ""
    feedback_block = (
        f"\n\nFeedback on your previous attempt — address this directly:\n{feedback}" if feedback else ""
    )
    return f"""{ANSWER_SYSTEM_PROMPT}
Knowledge elements:
{state.get("growing_knowledge") or "(none extracted)"}

Question: {state["question"]}{feedback_block}
"""


def build_answer_grading_prompt(state: AgentState) -> str:
    """User prompt for grading the generated answer against the growing knowledge."""
    return f"""\
You are verifying a financial analyst's answer for correctness and completeness against the \
knowledge elements it was allowed to use.

Question: {state["question"]}

Knowledge elements available to the answer generator:
{state.get("growing_knowledge") or "(none)"}

Generated answer (attempt #{state.get("answer_attempts", 0)}):
{state.get("answer")}

Task:
- accepted=true only if the answer directly and fully addresses the question, is grounded in \
the knowledge elements, and free of calculation errors.
- If not accepted, decide next_action:
  - 'retry_answer' if the knowledge elements already contain what's needed but the answer \
misused, misread, or ignored them.
  - 'retry_retrieval' if the knowledge elements are missing something the question requires.
- In feedback, be specific about what's wrong or missing.
"""
