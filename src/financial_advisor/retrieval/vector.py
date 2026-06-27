from langchain_core.documents import Document
from langchain_neo4j import Neo4jVector

from financial_advisor.clients import get_embeddings, get_graph
from financial_advisor.config import settings


def get_vector_store() -> Neo4jVector:
    """Return a Neo4jVector store backed by Chunk.embedding."""
    return Neo4jVector.from_existing_index(
        embedding=get_embeddings(),
        url=settings.neo4j_uri,
        username=settings.neo4j_username,
        password=settings.neo4j_password,
        index_name="chunk_embedding",
        node_label="Chunk",
        text_node_property="text",
        embedding_node_property="embedding",
    )


def vector_search(query: str, k: int = 5) -> list[Document]:
    """Retrieve top-k chunks by semantic similarity."""
    store = get_vector_store()
    return store.similarity_search(query, k=k)
