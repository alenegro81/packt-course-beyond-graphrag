from langchain_core.documents import Document

from financial_advisor.clients import get_llm
from financial_advisor.extraction.validators import ExtractionResult


def extract_entities(chunk: Document) -> ExtractionResult:
    """Extract entities from a single chunk using structured LLM output."""
    raise NotImplementedError
