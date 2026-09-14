from financial_advisor.agent.state import AgentState

# Tool behavior (what each tool does, its source, when to use it) lives entirely in each tool's
# own docstring in agent.tools — the LLM already receives those via bind_tools, so repeating
# them here would be a second copy that can silently drift out of sync with whichever tools a
# given agent build actually has bound (this happened: the old single STRATEGY_SYSTEM_PROMPT
# always described get_executives even when Module 2's agent didn't have it bound). This
# preamble only carries strategy that isn't a property of any one tool.
STRATEGY_PREAMBLE = """\
You are a financial research analyst. Use the tools available to you to answer the question — \
their docstrings tell you what each one does, its data source, and when to prefer it. Call one \
or more tools per turn. Don't repeat an identical (tool, arguments) call you've already tried — \
vary the query, tool, or target document instead.
"""

MODULE_2_STRATEGY_HINT = """\
Prefer semantic_search early or for broad/comparative questions; switch to fulltext_search \
once you know specific terminology; use get_document_pages once you've identified a promising \
doc_id and page range.
"""

MODULE_3_STRATEGY_HINT = (
    MODULE_2_STRATEGY_HINT
    + """\
Use get_executives, get_company_profile, or get_financials directly whenever the question is \
about people, company profile/structure/events, or financial figures — don't reach for \
semantic_search/fulltext_search for those, the structured tools are more reliable.
"""
)

MODULE_4_STRATEGY_HINT = (
    MODULE_3_STRATEGY_HINT
    + """\
Use get_recognised_entities/get_entity_relationships when the question asks what a specific \
document mentions (e.g. subsidiaries, regulations, products, risk topics) or how those things \
connect — they give a complete, deduplicated structured view of one doc_id instead of whatever \
a text search happens to surface, and are far more reliable for counting/enumerating than \
reading raw chunk text. Get the doc_id from a prior search hit first if you don't already have \
one. They only cover chunks already run through extraction; if they return nothing, fall back \
to semantic_search/fulltext_search.
"""
)

MODULE_6_STRATEGY_HINT = (
    MODULE_4_STRATEGY_HINT
    + """\
Use query_graph only as a last resort, when the question needs a cross-cutting aggregate, \
count, or multi-hop pattern that none of the structured tools above can answer directly. It \
generates its own Cypher with no guarantee of correctness — prefer any other tool that fits.
"""
)

MODULE_2_STRATEGY_PROMPT = STRATEGY_PREAMBLE + "\n" + MODULE_2_STRATEGY_HINT
MODULE_3_STRATEGY_PROMPT = STRATEGY_PREAMBLE + "\n" + MODULE_3_STRATEGY_HINT
MODULE_4_STRATEGY_PROMPT = STRATEGY_PREAMBLE + "\n" + MODULE_4_STRATEGY_HINT
MODULE_6_STRATEGY_PROMPT = STRATEGY_PREAMBLE + "\n" + MODULE_6_STRATEGY_HINT

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


def _render_retrieved_item(item: dict) -> str:
    """Render one retrieved_chunks entry — a document chunk, or a structured record from a
    non-chunk tool like get_executives (no doc_id/text, so it's rendered as labeled facts)."""
    if "doc_id" in item and "text" in item:
        return (
            f"[doc_id={item['doc_id']} | chunk_id={item['id']} | pages={item.get('pages')} | "
            f"score={item.get('score', 0):.3f}]\n{item['text']}"
        )
    fields = "\n".join(f"  {k}: {v}" for k, v in item.items() if k != "id")
    return f"[record id={item['id']}]\n{fields}"


# Retrieval grading has no bind_tools call (it's with_structured_output, not tool-calling), so
# unlike the strategy LLM it never sees each tool's docstring automatically — without this, the
# grader judges sufficiency against an unbounded ideal answer and, having no idea what sources
# actually exist, invents "next steps" the agent has no way to execute: e.g. asking for a
# question about 3M's corporate-action history to be filled out via "SEC EDGAR", "3M's Wikipedia
# page", or "Bloomberg/CRSP" when the agent's only source for that (Sharadar's ACTIONS feed) has
# already been queried and simply doesn't carry that data — burning every retry on a suggestion
# that was never reachable, rather than recognizing the source's real coverage ends there. Built
# from the same tool list the strategy prompt is paired with, so it can't drift the way a second
# hardcoded copy would (see the top-of-file note on STRATEGY_PREAMBLE).
RETRIEVAL_GRADING_PREAMBLE_TEMPLATE = """\
You are grading retrieval for a financial research agent whose ONLY sources of information are \
the tools below — it cannot browse the web, Wikipedia, SEC EDGAR, or any financial database not \
listed here. Judge sufficiency against what these specific tools can plausibly return, not an \
idealized complete answer. If the question asks for something none of these sources would ever \
contain (e.g. a fact outside a data provider's own tracked coverage, or a document never \
ingested — read each tool's docstring below for what it does and doesn't cover), that is a \
real, permanent gap — mark it sufficient once every tool that COULD help has actually been \
tried, note the gap plainly in `growing_knowledge`, and let the final answer state the \
limitation honestly. Only suggest retrying when there's a tool below, not yet tried with a \
reasonable variation, that could plausibly close the specific gap. Two ways retrieval wastes \
rounds without gaining anything — avoid steering it into either:
- A tool called again with the same (or equivalent) arguments returns the same result. Once a \
structured tool (one with no free-text query, e.g. a profile/executives/financials lookup) has \
been called for a given target, calling it again cannot surface anything new — don't suggest \
re-running it "to double check."
- A text-search tool (semantic_search/fulltext_search) already tried with several genuinely \
different phrasings of the same concept, turning up nothing on the topic (or the same handful \
of facts each time), is evidence that concept isn't in the corpus — not a reason to keep \
suggesting yet another rephrasing. One more differently-worded query is worth trying only if \
the prior attempts hinted at something (a partial mention, a promising but unexplored doc_id) \
worth chasing specifically — not as a general "try again" reflex.

`sufficient` must agree with your own `feedback`: if what you write concludes (however \
worded — "no further queries would help", "this is a permanent gap", "not available from the \
tools in this environment") that nothing left to try could close the remaining gap, that \
conclusion means `sufficient=True` — writing that conclusion while still setting \
`sufficient=False` sends the agent through another retrieval round with nothing new to \
attempt. Reaching that conclusion is a legitimate, complete answer to this grading task, not a \
failure to find enough — it's what should happen once the available sources are exhausted.

Tools available to this agent:
{tool_descriptions}
"""


def build_retrieval_grading_system_prompt(tools: list) -> str:
    """System prompt for the retrieval grader — see RETRIEVAL_GRADING_PREAMBLE_TEMPLATE."""
    tool_descriptions = "\n\n".join(f"- {t.name}: {t.description}" for t in tools)
    return RETRIEVAL_GRADING_PREAMBLE_TEMPLATE.format(tool_descriptions=tool_descriptions)


def build_retrieval_grading_prompt(state: AgentState) -> str:
    """User prompt for grading retrieved chunks and growing the knowledge base."""
    chunks = state.get("retrieved_chunks", [])
    chunks_block = (
        "\n\n".join(_render_retrieved_item(c) for c in chunks) or "(no chunks retrieved)"
    )

    return f"""\
Question: {state["question"]}

Knowledge carried over from previous rounds:
{state.get("growing_knowledge") or "(none yet)"}

All chunks retrieved so far (cumulative across rounds):
{chunks_block}

Task:
1. Decide whether the cumulative knowledge — previous rounds plus these chunks — is enough to \
fully and precisely answer the question, given only the tools actually available to this agent \
(see system prompt).
2. Rewrite `growing_knowledge` as the complete, self-contained set of facts needed to answer, \
citing doc_id for each fact. This replaces what the answer generator sees — the raw chunks are \
NOT passed forward, so do not omit anything still needed. If part of the question is out of \
reach of every available tool, say so explicitly here too.
3. If not sufficient, explain in `feedback` exactly what's missing and which available tool — \
by name — and what different query/arguments might close the gap. Never suggest a source that \
isn't one of the tools listed in the system prompt.
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
