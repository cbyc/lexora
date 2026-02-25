from sentence_transformers import SentenceTransformer


class SentenceTransformerEmbeddingModel:
    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self._embedding_model = SentenceTransformer(model_name)

    def encode(self, text: str) -> list[float]:
        return self._embedding_model.encode(text).tolist()
