"""Module 2 — agentic RAG nodes.

Each node is a plain function of (state, ...) -> partial state update, kept independent of
LangGraph so they can be called directly in a notebook to inspect one step at a time. Wiring
(binding the model, connecting edges) happens in agent.graph.
"""

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from financial_advisor.agent.prompts import (
    build_answer_grading_prompt,
    build_answer_prompt,
    build_retrieval_grading_prompt,
    build_strategy_prompt,
)
from financial_advisor.agent.state import AgentState, AnswerGrade, RetrievalGrade
from financial_advisor.agent.tools import TOOLS_BY_NAME
from financial_advisor.similarity.rerank import deduplicate_by_similarity

MAX_RETRIEVAL_ITERATIONS = 4
MAX_ANSWER_ATTEMPTS = 3


def retriever_strategy_node(state: AgentState, model_with_tools: Any, strategy_prompt: str) -> dict:
    """Decide which tool(s) to call next, given the question, growing knowledge, and history."""
    prompt = build_strategy_prompt(state)
    response = model_with_tools.invoke(
        [SystemMessage(content=strategy_prompt), HumanMessage(content=prompt)]
    )
    tool_calls = [{"name": tc["name"], "args": tc["args"]} for tc in (response.tool_calls or [])]

    if not tool_calls:
        print("[strategy] model returned no tool calls — falling back to semantic_search(question)")
        tool_calls = [{"name": "semantic_search", "args": {"query": state["question"], "k": 5}}]

    iteration = state.get("retrieval_iterations", 0) + 1
    print(f"[strategy] iteration {iteration}: {len(tool_calls)} tool call(s) planned")
    for call in tool_calls:
        print(f"    - {call['name']}({call['args']})")

    return {"tool_calls": tool_calls, "retrieval_iterations": iteration}


def call_tools_node(state: AgentState) -> dict:
    """Execute the tool calls chosen by the strategy node and accumulate unique chunks."""
    tool_calls = state.get("tool_calls", [])
    if not tool_calls:
        print("[tools] no tool calls to execute")
        return {}

    chunks_by_id = {chunk["id"]: chunk for chunk in state.get("retrieved_chunks", [])}
    log_entries = list(state.get("tool_call_log", []))

    for call in tool_calls:
        tool = TOOLS_BY_NAME.get(call["name"])
        if tool is None:
            print(f"[tools] unknown tool: {call['name']}")
            continue
        try:
            results = tool.invoke(call["args"])
            if isinstance(results, dict):
                # A handful of tools (get_company_profile) return one dict, not a list — every
                # other tool returns list[dict]; normalize so the loop below always sees rows.
                results = [results] if results else []
        except Exception as exc:
            print(f"[tools] {call['name']} failed: {exc}")
            results = []

        print(f"[tools] {call['name']}({call['args']}) -> {len(results)} chunk(s)")
        for chunk in results:
            chunks_by_id[chunk["id"]] = chunk
        log_entries.append({"tool": call["name"], "args": call["args"], "n_results": len(results)})

    return {
        "retrieved_chunks": list(chunks_by_id.values()),
        "tool_call_log": log_entries,
        "tool_calls": [],
    }


def deduplicate_chunks_node(state: AgentState, threshold: float = 0.92) -> dict:
    """Drop near-duplicate chunks (precomputed SIMILAR_TO score >= threshold, see
    similarity/linker.py + similarity/rerank.py) before retrieval grading sees them — keeps
    whichever copy was retrieved first. Optional: only wired in when build_agent(dedup=True)."""
    chunks = state.get("retrieved_chunks", [])
    deduped = deduplicate_by_similarity(chunks, threshold=threshold)
    dropped = len(chunks) - len(deduped)
    if dropped:
        print(f"[dedup] {dropped} near-duplicate chunk(s) dropped ({len(chunks)} -> {len(deduped)})")
    return {"retrieved_chunks": deduped}


def evaluate_retrieval_node(state: AgentState, model: Any) -> dict:
    """Grow the knowledge base from retrieved chunks; decide if it's enough to answer."""
    prompt = build_retrieval_grading_prompt(state)
    grade: RetrievalGrade = model.with_structured_output(RetrievalGrade).invoke(prompt)

    print(f"[grade-retrieval] sufficient={grade.sufficient}")
    if not grade.sufficient:
        print(f"    feedback: {grade.feedback}")

    return {
        "growing_knowledge": grade.growing_knowledge or state.get("growing_knowledge", ""),
        "retrieval_feedback": grade.feedback,
        "retrieval_sufficient": grade.sufficient,
    }


def evaluate_retrieval_edge(state: AgentState) -> str:
    """Route to another retrieval round, or on to answer generation."""
    if state["retrieval_iterations"] >= MAX_RETRIEVAL_ITERATIONS:
        print("[grade-retrieval] max retrieval iterations reached — continuing with what we have")
        return "continue"
    return "continue" if state.get("retrieval_sufficient") else "retry"


def generate_answer_node(state: AgentState, model: Any) -> dict:
    """Generate an answer from the growing knowledge only — retrieved chunks are not visible here."""
    prompt = build_answer_prompt(state)
    response = model.invoke(prompt)
    attempts = state.get("answer_attempts", 0) + 1
    print(f"[answer] attempt #{attempts}")
    return {"answer": response.content, "answer_attempts": attempts}


def evaluate_answer_node(state: AgentState, model: Any) -> dict:
    """Grade the generated answer for correctness and completeness against the growing knowledge."""
    prompt = build_answer_grading_prompt(state)
    grade: AnswerGrade = model.with_structured_output(AnswerGrade).invoke(prompt)

    print(f"[grade-answer] accepted={grade.accepted} next_action={grade.next_action}")
    if grade.feedback:
        print(f"    feedback: {grade.feedback}")

    return {"answer_feedback": grade.feedback, "answer_next_action": grade.next_action}


def evaluate_answer_edge(state: AgentState) -> str:
    """Route to end, retry the answer, or go back to retrieval for more information."""
    if state.get("answer_attempts", 0) >= MAX_ANSWER_ATTEMPTS:
        print("[grade-answer] max answer attempts reached — ending")
        return "end"
    action = state.get("answer_next_action", "end")
    return action if action in {"retry_answer", "retry_retrieval", "end"} else "end"
