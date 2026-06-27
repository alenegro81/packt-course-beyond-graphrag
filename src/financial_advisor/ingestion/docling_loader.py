from pathlib import Path

from langchain_core.documents import Document


def load_filing(path: Path, company_id: str, year: int) -> list[Document]:
    """Convert a PDF filing to chunked LangChain Documents using Docling.

    Each Document carries metadata: company_id, year, source, page, chunk_index.
    """
    raise NotImplementedError
