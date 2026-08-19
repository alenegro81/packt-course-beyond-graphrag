from sentence_transformers import SentenceTransformer


class EmbeddingService:
    def __init__(self, model_name: str = "BAAI/bge-m3", batch_size: int = 4) -> None:
        self.model_name = model_name
        self.batch_size = batch_size
        self.model = SentenceTransformer(model_name)
        # fp16 + a small batch size measured ~36% faster than fp32/batch_size=32 (the
        # sentence-transformers default) for 4096-token chunks on MPS, with no meaningful
        # loss of retrieval quality — embedding cosine similarity is robust to fp16 rounding.
        self.model = self.model.half()
        self.dimensions: int = self.model.get_embedding_dimension()

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts, returning one vector per input in the same order.

        Used both for bulk chunk embedding (ingestion) and single-question embedding
        (retrieval, via embed_text) — both paths share this model/precision/batch_size.
        """
        vectors = self.model.encode(texts, batch_size=self.batch_size, show_progress_bar=False)
        return vectors.tolist()

    def embed_text(self, text: str) -> list[float]:
        return self.embed_texts([text])[0]


embedding_service = EmbeddingService()
