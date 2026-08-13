"""Module 1 — one-shot RAG baseline: embed → retrieve → generate, no tool use, no loop.

Deliberately naive: a single vector search feeds a single LLM call. It works well on
questions a single chunk can answer, and struggles on anything requiring multiple
hops or cross-document reasoning — motivating the agentic loop built in Module 2.
"""

from dataclasses import dataclass

from financial_advisor.clients import get_llm
from financial_advisor.services.embedding_service import embedding_service
from financial_advisor.services.neo4j_service import neo4j_service

ANSWER_PROMPT = """\
Answer the question using only the context below. If the context does not contain \
the answer, say you don't know — do not guess.

Context:
{context}

Question: {question}
"""


@dataclass
class RetrievedChunk:
    id: str
    text: str
    doc_id: str
    company_id: str
    score: float


def embed_question(question: str) -> list[float]:
    """Embed a question with the same model used for Chunk.embedding."""
    return embedding_service.embed_text(question)


def retrieve_chunks(query_vector: list[float], k: int = 5) -> list[RetrievedChunk]:
    """Top-k chunks by cosine similarity against the chunk_embedding vector index."""
    rows = neo4j_service.run_query(
        """
        CALL db.index.vector.queryNodes('chunk_embedding', $k, $vector)
        YIELD node, score
        RETURN node.id AS id, node.text AS text, node.doc_id AS doc_id,
               node.company_id AS company_id, score
        ORDER BY score DESC
        """,
        {"k": k, "vector": query_vector},
    )
    return [RetrievedChunk(**row) for row in rows]


def build_context(chunks: list[RetrievedChunk]) -> str:
    """Concatenate retrieved chunks into a single context block, most relevant first."""
    return "\n\n".join(f"[{c.doc_id} | score={c.score:.3f}]\n{c.text}" for c in chunks)


def generate_answer(question: str, chunks: list[RetrievedChunk]) -> str:
    """Single LLM call over the retrieved context — the "one shot" in one-shot RAG."""
    prompt = ANSWER_PROMPT.format(context=build_context(chunks), question=question)
    response = get_llm().invoke(prompt)
    return response.content


def ask(question: str, k: int = 5) -> str:
    """Convenience wrapper chaining embed → retrieve → generate for non-notebook use."""
    chunks = retrieve_chunks(embed_question(question), k=k)
    return generate_answer(question, chunks)
