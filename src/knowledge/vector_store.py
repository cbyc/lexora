"""ChromaDB vector store operations."""

import uuid

import chromadb
import structlog

from models import Chunk

logger = structlog.get_logger(__name__)


class VectorStore:
    """Manages ChromaDB vector store operations."""

    def __init__(
        self,
        client,
        collection_name: str = "lexora",
        embedding_dimension: int = 768,
    ):
        self._client = client
        self._collection_name = collection_name
        self._embedding_dimension = embedding_dimension
        self._collection = None

    @classmethod
    def in_memory(
        cls, collection_name: str = "lexora", embedding_dimension: int = 768
    ) -> "VectorStore":
        """Create a VectorStore backed by an ephemeral in-memory ChromaDB instance.

        Each call produces an isolated store: a UUID suffix is appended to the
        collection name to avoid state leakage across instances (EphemeralClient
        uses a process-level singleton under the hood).
        """
        unique_name = f"{collection_name}_{uuid.uuid4().hex[:8]}"
        return cls(chromadb.EphemeralClient(), unique_name, embedding_dimension)

    @classmethod
    def from_path(
        cls, path: str, collection_name: str = "lexora", embedding_dimension: int = 768
    ) -> "VectorStore":
        """Create a VectorStore persisted to a local directory."""
        return cls(
            chromadb.PersistentClient(path=path), collection_name, embedding_dimension
        )

    def ensure_collection(self) -> None:
        """Get or create the collection."""
        self._collection = self._client.get_or_create_collection(
            name=self._collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def add_chunks(self, chunks: list[Chunk], embeddings: list[list[float]]) -> None:
        """Add chunks with their embeddings to the vector store."""
        ids, vecs, docs, metas = [], [], [], []
        for chunk, emb in zip(chunks, embeddings):
            ids.append(
                str(
                    uuid.uuid5(
                        uuid.NAMESPACE_DNS,
                        f"{chunk.source}:{chunk.chunk_index}:{chunk.text}",
                    )
                )
            )
            vecs.append(emb)
            docs.append(chunk.text)
            metas.append({"source": chunk.source, "chunk_index": chunk.chunk_index})
        self._collection.upsert(
            ids=ids, embeddings=vecs, documents=docs, metadatas=metas
        )

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        score_threshold: float = 0.0,
    ) -> list[Chunk]:
        """Search for similar chunks by embedding."""
        count = self._collection.count()
        n = min(top_k, count)
        if n == 0:
            return []
        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=n,
            include=["documents", "metadatas", "distances"],
        )
        out = []
        for doc, meta, dist in zip(
            results["documents"][0], results["metadatas"][0], results["distances"][0]
        ):
            if (1.0 - dist) < score_threshold:
                continue
            out.append(
                Chunk(text=doc, source=meta["source"], chunk_index=meta["chunk_index"])
            )
        return out

    def delete_collection(self) -> None:
        """Delete the collection (for cleanup in tests)."""
        self._client.delete_collection(self._collection_name)
        self._collection = None
