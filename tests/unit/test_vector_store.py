"""Tests for ChromaDB vector store operations."""

from models import Chunk
from knowledge.vector_store import VectorStore


class TestVectorStore:
    """Tests for the VectorStore class."""

    def test_init_creates_client(self):
        """VectorStore should initialize with in-memory client."""
        store = VectorStore.in_memory()
        assert store is not None

    def test_ensure_collection(self):
        """ensure_collection should create a collection without error."""
        store = VectorStore.in_memory()
        store.ensure_collection()

    def test_add_and_search(
        self, sample_chunks: list[Chunk], sample_embeddings: list[list[float]]
    ):
        """add_chunks should store data retrievable by search."""
        store = VectorStore.in_memory()
        store.ensure_collection()
        store.add_chunks(sample_chunks, sample_embeddings)
        results = store.search(sample_embeddings[0], top_k=3)
        assert len(results) > 0

    def test_search_returns_search_results(
        self, sample_chunks: list[Chunk], sample_embeddings: list[list[float]]
    ):
        """search should return a list of Chunk objects."""
        store = VectorStore.in_memory()
        store.ensure_collection()
        store.add_chunks(sample_chunks, sample_embeddings)
        results = store.search(sample_embeddings[0], top_k=2)
        assert isinstance(results, list)
        assert all(isinstance(r, Chunk) for r in results)

    def test_search_respects_top_k(
        self, sample_chunks: list[Chunk], sample_embeddings: list[list[float]]
    ):
        """search should return at most top_k results."""
        store = VectorStore.in_memory()
        store.ensure_collection()
        store.add_chunks(sample_chunks, sample_embeddings)
        results = store.search(sample_embeddings[0], top_k=1)
        assert len(results) <= 1

    def test_search_empty_collection(self):
        """Searching an empty collection should return empty list."""
        store = VectorStore.in_memory()
        store.ensure_collection()
        results = store.search([0.0] * 768, top_k=5)
        assert results == []

    def test_delete_collection(
        self, sample_chunks: list[Chunk], sample_embeddings: list[list[float]]
    ):
        """delete_collection should remove all data."""
        store = VectorStore.in_memory()
        store.ensure_collection()
        store.add_chunks(sample_chunks, sample_embeddings)
        store.delete_collection()
        store.ensure_collection()
        results = store.search(sample_embeddings[0], top_k=3)
        assert results == []
