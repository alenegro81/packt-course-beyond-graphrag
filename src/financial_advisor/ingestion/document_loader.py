from pathlib import Path

from langchain_core.documents import Document

from financial_advisor.services.embedding_service import embedding_service
from financial_advisor.services.pdf_parsing_service import pdf_parsing_service


def load_from_path(path: Path, company_id: str, year: int) -> list[Document]:
    """Convert a PDF filing to chunked LangChain Documents using Docling.

    Each Document carries metadata: company_id, year, source, pages, chunk_index
    plus document-level fields extracted by Docling (title, author, total_pages, …).
    Returns an empty list if the PDF cannot be converted.
    """
    conv_result = pdf_parsing_service.convert_pdf(path)
    if conv_result is None:
        return []

    meta_base = pdf_parsing_service.extract_metadata(conv_result, path)
    chunks = pdf_parsing_service.chunk_document(conv_result)

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


def add_embeddings(documents: list[Document]) -> list[Document]:
    """Embed each Document's text and store the vector as metadata["embedding"].

    Batches all texts into a single embedding_service call. Mutates and returns
    the same list of Documents.
    """
    vectors = embedding_service.embed_texts([doc.page_content for doc in documents])
    for doc, vector in zip(documents, vectors):
        doc.metadata["embedding"] = vector
    return documents
