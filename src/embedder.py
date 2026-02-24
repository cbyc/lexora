from sentence_transformers import SentenceTransformer


class SentenceTransformerEmbeddingModel:
    def __init__(self):
        self._embedding_model = SentenceTransformer(
            "sentence-transformers/all-MiniLM-L6-v2"
        )

    def encode(self, text: str) -> list[float]:
        return self._embedding_model.encode(text).tolist()
