"""Qdrant vector store operations."""

import uuid
import structlog

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from src.models import Chunk

logger = structlog.get_logger(__name__)


class VectorStore:
    """Manages Qdrant vector store operations."""

    def __init__(
        self,
        client: QdrantClient,
        collection_name: str = "lexora",
        embedding_dimension: int = 384,
    ):
        """Initialise the vector store with a pre-built Qdrant client.

        Prefer the factory classmethods `in_memory()` and `from_url()`
        over calling this constructor directly.

        Args:
            client: A fully configured QdrantClient instance.
            collection_name: Name of the Qdrant collection to use.
            embedding_dimension: Dimension of the embedding vectors.
        """
        self._client = client
        self._collection_name = collection_name
        self._embedding_dimension = embedding_dimension

    @classmethod
    def in_memory(
        cls, collection_name: str = "lexora", embedding_dimension: int = 384
    ) -> "VectorStore":
        """Create a VectorStore backed by an ephemeral in-memory Qdrant instance.

        Intended for development and testing — data is lost when the process exits.

        Args:
            collection_name: Name of the Qdrant collection to use.
            embedding_dimension: Dimension of the embedding vectors.
        """
        client = QdrantClient(location=":memory:")
        return cls(client, collection_name, embedding_dimension)

    @classmethod
    def from_url(
        cls, url: str, collection_name: str = "lexora", embedding_dimension: int = 384
    ) -> "VectorStore":
        """Create a VectorStore connected to a remote Qdrant server.

        Args:
            url: URL of the Qdrant server (e.g. 'http://localhost:6333').
            collection_name: Name of the Qdrant collection to use.
            embedding_dimension: Dimension of the embedding vectors.
        """
        client = QdrantClient(url=url)
        return cls(client, collection_name, embedding_dimension)

    def ensure_collection(self) -> None:
        """Create collection if it doesn't exist."""
        collections = self._client.get_collections().collections
        if not any(c.name == self._collection_name for c in collections):
            self._client.create_collection(
                collection_name=self._collection_name,
                vectors_config=VectorParams(
                    size=self._embedding_dimension,
                    distance=Distance.COSINE,
                ),
            )

    def add_chunks(self, chunks: list[Chunk], embeddings: list[list[float]]) -> None:
        """Add chunks with their embeddings to the vector store.

        Args:
            chunks: List of text chunks to store.
            embeddings: Corresponding embedding vectors.
        """
        points = []
        for chunk, embedding in zip(chunks, embeddings):
            point_id = str(
                uuid.uuid5(
                    uuid.NAMESPACE_DNS,
                    f"{chunk.source}:{chunk.chunk_index}:{chunk.text}",
                )
            )
            points.append(
                PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload={
                        "text": chunk.text,
                        "source": chunk.source,
                        "chunk_index": chunk.chunk_index,
                    },
                )
            )
        self._client.upsert(collection_name=self._collection_name, points=points)

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        score_threshold: float = 0.0,
    ) -> list[Chunk]:
        """Search for similar chunks by embedding.

        Args:
            query_embedding: The query embedding vector.
            top_k: Number of results to return.
            score_threshold: Minimum relevance score. Results below this are filtered out.

        Returns:
            List of Chunk objects.
        """
        results = self._client.query_points(
            collection_name=self._collection_name,
            query=query_embedding,
            limit=top_k,
        ).points

        search_results = []
        for point in results:
            if point.score < score_threshold:
                continue
            payload = point.payload
            chunk = Chunk(
                text=payload["text"],
                source=payload["source"],
                chunk_index=payload["chunk_index"],
            )
            search_results.append(chunk)

        return search_results

    def delete_collection(self) -> None:
        """Delete the collection (for cleanup in tests)."""
        self._client.delete_collection(collection_name=self._collection_name)
