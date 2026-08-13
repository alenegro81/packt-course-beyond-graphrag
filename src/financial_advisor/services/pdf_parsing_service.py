from dataclasses import dataclass, field
from pathlib import Path

from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
from docling.datamodel.base_models import ConversionStatus, InputFormat
from docling.datamodel.pipeline_options import (
    EasyOcrOptions,
    TableFormerMode,
    ThreadedPdfPipelineOptions,
)
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.pipeline.threaded_standard_pdf_pipeline import ThreadedStandardPdfPipeline
from docling_core.transforms.chunker.hybrid_chunker import HybridChunker
from docling_core.transforms.chunker.tokenizer.huggingface import HuggingFaceTokenizer
from transformers import AutoTokenizer


@dataclass
class ChunkResult:
    text: str
    pages: list[int] = field(default_factory=list)


class PdfParsingService:
    def __init__(self, chunk_max_tokens: int = 4096, num_threads: int = 4) -> None:
        pipeline_options = ThreadedPdfPipelineOptions(
            do_table_structure=True,
            do_ocr=True,
            generate_page_images=False,
            images_scale=3.0,
            accelerator_options=AcceleratorOptions(
                device=AcceleratorDevice.AUTO,
                num_threads=num_threads,
            ),
            ocr_batch_size=128,
            layout_batch_size=128,
            table_batch_size=128,
        )
        pipeline_options.table_structure_options.do_cell_matching = True
        pipeline_options.table_structure_options.mode = TableFormerMode.ACCURATE
        pipeline_options.ocr_options = EasyOcrOptions(force_full_page_ocr=False, lang=["en"])

        self.doc_converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_cls=ThreadedStandardPdfPipeline,
                    pipeline_options=pipeline_options,
                )
            }
        )
        # Pre-initialize the pipeline once for performance (avoids cold-start per document)
        self.doc_converter.initialize_pipeline(InputFormat.PDF)

        tokenizer = HuggingFaceTokenizer(
            tokenizer=AutoTokenizer.from_pretrained("jinaai/jina-embeddings-v2-base-en"),
            max_tokens=chunk_max_tokens,
        )
        self.chunker = HybridChunker(tokenizer=tokenizer, merge_peers=True)

    def convert_pdf(self, path: Path):
        """Return a Docling ConversionResult, or None if the conversion fails."""
        try:
            result = self.doc_converter.convert(str(path))
        except Exception as exc:
            print(f"  [docling] conversion error for {path.name}: {exc}")
            return None

        status = getattr(result, "status", None)
        if status is not None and status != ConversionStatus.SUCCESS:
            print(f"  [docling] conversion did not succeed for {path.name} (status={status})")
            return None
        return result

    def chunk_document(self, conv_result) -> list[ChunkResult]:
        """Chunk a converted Docling document into text segments with page provenance."""
        doc = conv_result.document
        results: list[ChunkResult] = []
        try:
            for chunk in self.chunker.chunk(doc):
                text = self.chunker.contextualize(chunk=chunk)
                if not text:
                    continue
                meta = chunk.meta.export_json_dict()
                pages = sorted(
                    {
                        prov["page_no"]
                        for item in meta.get("doc_items", [])
                        for prov in item.get("prov", [])
                        if "page_no" in prov
                    }
                )
                results.append(ChunkResult(text=text, pages=pages))
        except Exception as exc:
            print(f"  [docling] chunking error: {exc}")
        return results

    def extract_metadata(self, conv_result, path: Path) -> dict:
        """Extract document-level metadata from a Docling ConversionResult."""
        doc = getattr(conv_result, "document", None)
        props = getattr(doc, "properties", None)

        title = getattr(doc, "name", None)
        author = None
        subject = None
        creation_date = None
        keywords = None

        if props is not None:
            title = getattr(props, "title", title) or title
            author = getattr(props, "authors", None)
            subject = getattr(props, "subject", None)
            creation_date = getattr(props, "creation_date", None)
            keywords = getattr(props, "keywords", None)

        if creation_date is not None:
            creation_date = str(creation_date)

        total_pages = None
        try:
            pages_attr = getattr(conv_result, "pages", None)
            if pages_attr is not None:
                total_pages = len(pages_attr)
        except Exception:
            pass

        return {
            "doc_name": path.name,
            "title": title,
            "source": str(path.resolve()),
            "format": "pdf",
            "total_pages": total_pages,
            "author": author,
            "subject": subject,
            "creation_date": creation_date,
            "keywords": keywords,
        }


pdf_parsing_service = PdfParsingService()
