from langchain_core.documents import Document

from financial_advisor.clients import get_llm
from financial_advisor.extraction.validators import ExtractionResult


def extract_relationships(chunk: Document, known_entities: list[str]) -> ExtractionResult:
    """Extract relationships between known entities found in a chunk."""
    raise NotImplementedError


def write_extraction_to_graph(graph, result: ExtractionResult, chunk_id: str) -> None:
    """Merge extracted entities and relationships into Neo4j, linked to their source chunk."""
    raise NotImplementedError
