from functools import partial

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from financial_advisor.agent.nodes import (
    call_tools_node,
    evaluate_answer_edge,
    evaluate_answer_node,
    evaluate_retrieval_edge,
    evaluate_retrieval_node,
    generate_answer_node,
    retriever_strategy_node,
)
from financial_advisor.agent.state import AgentState
from financial_advisor.agent.tools import TOOLS
from financial_advisor.clients import get_llm


def build_agent() -> CompiledStateGraph:
    """Construct the Module 2 agentic RAG workflow.

    retriever_strategy -> call_tools -> evaluate_retrieval --retry--> retriever_strategy
                                                            --continue--> generate_answer
    generate_answer -> evaluate_answer --retry_answer--> generate_answer
                                        --retry_retrieval--> retriever_strategy
                                        --end--> END
    """
    model = get_llm()
    model_with_tools = model.bind_tools(TOOLS)

    graph = StateGraph(AgentState)
    graph.add_node("retriever_strategy", partial(retriever_strategy_node, model_with_tools=model_with_tools))
    graph.add_node("call_tools", call_tools_node)
    graph.add_node("evaluate_retrieval", partial(evaluate_retrieval_node, model=model))
    graph.add_node("generate_answer", partial(generate_answer_node, model=model))
    graph.add_node("evaluate_answer", partial(evaluate_answer_node, model=model))

    graph.add_edge(START, "retriever_strategy")
    graph.add_edge("retriever_strategy", "call_tools")
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
