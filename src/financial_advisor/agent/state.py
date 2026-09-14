from typing import Literal, TypedDict

from pydantic import BaseModel, Field


class ToolCall(TypedDict):
    name: str
    args: dict


class RetrievalGrade(BaseModel):
    """Evaluation of whether the growing knowledge is enough to answer the question."""

    sufficient: bool = Field(
        description="True if the growing knowledge is enough to fully and precisely answer the question"
    )
    growing_knowledge: str = Field(
        description=(
            "The complete, self-contained knowledge base needed to answer the question: specific "
            "facts, figures, and quotes, each citing its source doc_id. Carry forward everything "
            "still relevant from previous rounds and add what's new — this replaces what the answer "
            "generator sees, the raw chunks are not passed forward."
        )
    )
    feedback: str = Field(
        default="",
        description=(
            "If not sufficient: exactly what's missing and which tool/query/document to try next "
            "— only from the tools actually available to this agent (see system prompt), never a "
            "source it has no way to call. Empty when sufficient."
        ),
    )


class AnswerGrade(BaseModel):
    """Evaluation of a generated answer against the growing knowledge it was allowed to use."""

    accepted: bool = Field(
        description="True if the answer is correct, complete, and well-grounded in the growing knowledge"
    )
    next_action: Literal["retry_answer", "retry_retrieval", "end"] = Field(
        description=(
            "'end' if accepted. If not accepted: 'retry_answer' when the growing knowledge already "
            "has what's needed but the answer failed to use it correctly; 'retry_retrieval' when "
            "information the question requires is genuinely missing from the growing knowledge."
        )
    )
    feedback: str = Field(default="", description="Specific guidance for the retry. Empty when accepted.")


class AgentState(TypedDict):
    question: str

    # retriever_strategy_agent -> call_tools
    tool_calls: list[ToolCall]
    tool_call_log: list[dict]
    retrieved_chunks: list[dict]
    retrieval_iterations: int

    # evaluate_retrieval
    growing_knowledge: str
    retrieval_feedback: str
    retrieval_sufficient: bool

    # generate_answer / evaluate_answer
    answer: str
    answer_attempts: int
    answer_feedback: str
    answer_next_action: str


def initial_state(question: str) -> AgentState:
    """Build a fresh AgentState for a new question."""
    return AgentState(
        question=question,
        tool_calls=[],
        tool_call_log=[],
        retrieved_chunks=[],
        retrieval_iterations=0,
        growing_knowledge="",
        retrieval_feedback="",
        retrieval_sufficient=False,
        answer="",
        answer_attempts=0,
        answer_feedback="",
        answer_next_action="",
    )
