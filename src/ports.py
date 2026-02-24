from typing import Protocol
from src.models import Chunk


class Chunker(Protocol):
    def chunk(self, text: str) -> list[str]: ...


class EmbeddingModel(Protocol):
    def encode(self, texts: str) -> list[float]: ...


class DocumentStore(Protocol):
    def ensure_collection(self) -> None: ...

    def add_chunks(
        self, chunks: list[Chunk], embeddings: list[list[float]]
    ) -> None: ...

    def search(
        self, query_embedding: list[float], top_k: int = 5, score_threshold: float = 0.0
    ) -> list[Chunk]: ...
