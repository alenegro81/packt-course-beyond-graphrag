from pathlib import Path

from langchain_core.documents import Document

from financial_advisor.services.docling_service import docling_service


def load_filing(path: Path, company_id: str, year: int) -> list[Document]:
    """Convert a PDF filing to chunked LangChain Documents using Docling.

    Each Document carries metadata: company_id, year, source, pages, chunk_index
    plus document-level fields extracted by Docling (title, author, total_pages, …).
    Returns an empty list if the PDF cannot be converted.
    """
    conv_result = docling_service.convert_pdf(path)
    if conv_result is None:
        return []

    meta_base = docling_service.extract_metadata(conv_result, path)
    chunks = docling_service.chunk_document(conv_result)

    return [
        Document(
            page_content=chunk.text,
            metadata={
                "company_id": company_id,
                "year": year,
                "chunk_index": i,
                "pages": chunk.pages,
                **meta_base,
            },
        )
        for i, chunk in enumerate(chunks)
    ]
