from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from typing_extensions import TypedDict

from financial_advisor.agent.prompts import SYSTEM_PROMPT
from financial_advisor.agent.tools import (
    fulltext_search,
    get_company_documents,
    get_context_around_chunk,
    semantic_search,
)
from financial_advisor.clients import get_llm

TOOLS = [semantic_search, fulltext_search, get_company_documents, get_context_around_chunk]


class AgentState(TypedDict):
    messages: list


def build_agent() -> StateGraph:
    """Construct the LangGraph ReAct agent for the financial advisor."""
    llm = get_llm().bind_tools(TOOLS)

    def call_model(state: AgentState) -> AgentState:
        from langchain_core.messages import SystemMessage
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
        return {"messages": [llm.invoke(messages)]}

    graph = StateGraph(AgentState)
    graph.add_node("agent", call_model)
    graph.add_node("tools", ToolNode(TOOLS))
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", tools_condition)
    graph.add_edge("tools", "agent")
    graph.add_edge("agent", END)

    return graph.compile()
