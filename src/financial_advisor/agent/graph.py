from functools import partial

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from financial_advisor.agent.nodes import (
    call_tools_node,
    deduplicate_chunks_node,
    evaluate_answer_edge,
    evaluate_answer_node,
    evaluate_retrieval_edge,
    evaluate_retrieval_node,
    generate_answer_node,
    retriever_strategy_node,
)
from financial_advisor.agent.prompts import MODULE_3_STRATEGY_PROMPT
from financial_advisor.agent.state import AgentState
from financial_advisor.agent.tools import MODULE_3_TOOLS
from financial_advisor.clients import get_llm


def build_agent(
    tools: list = MODULE_3_TOOLS,
    strategy_prompt: str = MODULE_3_STRATEGY_PROMPT,
    dedup: bool = False,
) -> CompiledStateGraph:
    """Construct the agentic RAG workflow.

    retriever_strategy -> call_tools -> [deduplicate_chunks] -> evaluate_retrieval
                                                            --retry--> retriever_strategy
                                                            --continue--> generate_answer
    generate_answer -> evaluate_answer --retry_answer--> generate_answer
                                        --retry_retrieval--> retriever_strategy
                                        --end--> END

    tools and strategy_prompt are paired — pass a matching set (e.g. agent.tools.MODULE_2_TOOLS
    with agent.prompts.MODULE_2_STRATEGY_PROMPT) so the strategy LLM is never told about a tool
    it doesn't actually have bound.

    dedup=True (Module 5) inserts deduplicate_chunks_node between call_tools and
    evaluate_retrieval, dropping near-duplicate chunks via precomputed SIMILAR_TO edges before
    grading ever sees them. Defaults to False so every earlier module's graph shape is unchanged.
    """
    model = get_llm()
    model_with_tools = model.bind_tools(tools)

    graph = StateGraph(AgentState)
    graph.add_node(
        "retriever_strategy",
        partial(retriever_strategy_node, model_with_tools=model_with_tools, strategy_prompt=strategy_prompt),
    )
    graph.add_node("call_tools", call_tools_node)
    graph.add_node("evaluate_retrieval", partial(evaluate_retrieval_node, model=model))
    graph.add_node("generate_answer", partial(generate_answer_node, model=model))
    graph.add_node("evaluate_answer", partial(evaluate_answer_node, model=model))

    graph.add_edge(START, "retriever_strategy")
    graph.add_edge("retriever_strategy", "call_tools")
    if dedup:
        graph.add_node("deduplicate_chunks", deduplicate_chunks_node)
        graph.add_edge("call_tools", "deduplicate_chunks")
        graph.add_edge("deduplicate_chunks", "evaluate_retrieval")
    else:
        graph.add_edge("call_tools", "evaluate_retrieval")
    graph.add_conditional_edges(
        "evaluate_retrieval",
        evaluate_retrieval_edge,
        {"retry": "retriever_strategy", "continue": "generate_answer"},
    )
    graph.add_edge("generate_answer", "evaluate_answer")
    graph.add_conditional_edges(
        "evaluate_answer",
        evaluate_answer_edge,
        {"retry_answer": "generate_answer", "retry_retrieval": "retriever_strategy", "end": END},
    )

    return graph.compile()
