"""Tests for the Pipeline orchestration class."""

from src.loaders.models import Document
from src.models import Chunk
from src.pipeline import Pipeline

DIM = 384


class FakeChunker:
    def __init__(self, returns: list[str] | None = None):
        self.calls: list[str] = []
        self._returns = returns if returns is not None else ["chunk_a", "chunk_b"]

    def chunk(self, text: str) -> list[str]:
        self.calls.append(text)
        return self._returns


class FakeEmbeddingModel:
    def __init__(self):
        self.calls: list[str] = []

    def encode(self, text: str) -> list[float]:
        self.calls.append(text)
        return [0.0] * DIM


class FakeDocumentStore:
    def __init__(self, search_result: list[Chunk] | None = None):
        self.ensured = False
        self.added_batches: list[tuple[list[Chunk], list[list[float]]]] = []
        self.search_calls: list[list[float]] = []
        self._search_result = search_result or []

    def ensure_collection(self) -> None:
        self.ensured = True

    def add_chunks(self, chunks: list[Chunk], embeddings: list[list[float]]) -> None:
        self.added_batches.append((chunks, embeddings))

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        score_threshold: float = 0.0,
    ) -> list[Chunk]:
        self.search_calls.append(query_embedding)
        return self._search_result


class TestPipelineAddDocs:
    def test_ensure_collection_called(self):
        """add_docs should call ensure_collection on the store."""
        store = FakeDocumentStore()
        pipeline = Pipeline(FakeChunker(), FakeEmbeddingModel(), store)
        pipeline.add_docs([Document(content="text", source="a.txt")])
        assert store.ensured

    def test_ensure_collection_called_even_with_empty_docs(self):
        """ensure_collection should be called even when the doc list is empty."""
        store = FakeDocumentStore()
        pipeline = Pipeline(FakeChunker(), FakeEmbeddingModel(), store)
        pipeline.add_docs([])
        assert store.ensured

    def test_chunker_called_once_per_doc(self):
        """The chunker should be called exactly once for each document's content."""
        chunker = FakeChunker()
        pipeline = Pipeline(chunker, FakeEmbeddingModel(), FakeDocumentStore())
        pipeline.add_docs(
            [
                Document(content="first", source="a.txt"),
                Document(content="second", source="b.txt"),
            ]
        )
        assert chunker.calls == ["first", "second"]

    def test_embedding_model_called_once_per_chunk(self):
        """The embedding model should be called once for every chunk produced."""
        embedder = FakeEmbeddingModel()
        pipeline = Pipeline(
            FakeChunker(returns=["c1", "c2", "c3"]), embedder, FakeDocumentStore()
        )
        pipeline.add_docs([Document(content="text", source="a.txt")])
        assert embedder.calls == ["c1", "c2", "c3"]

    def test_add_chunks_called_once_per_doc(self):
        """add_chunks on the store should be called once per document."""
        store = FakeDocumentStore()
        pipeline = Pipeline(FakeChunker(returns=["c1"]), FakeEmbeddingModel(), store)
        pipeline.add_docs(
            [
                Document(content="first", source="a.txt"),
                Document(content="second", source="b.txt"),
            ]
        )
        assert len(store.added_batches) == 2

    def test_chunk_objects_carry_correct_source(self):
        """Each Chunk passed to the store should have the source of its Document."""
        store = FakeDocumentStore()
        pipeline = Pipeline(
            FakeChunker(returns=["c1", "c2"]), FakeEmbeddingModel(), store
        )
        pipeline.add_docs([Document(content="text", source="notes/a.txt")])
        chunks, _ = store.added_batches[0]
        assert all(c.source == "notes/a.txt" for c in chunks)

    def test_chunk_objects_carry_sequential_index(self):
        """Chunks for a document should be indexed 0, 1, 2, … in order."""
        store = FakeDocumentStore()
        pipeline = Pipeline(
            FakeChunker(returns=["c1", "c2", "c3"]), FakeEmbeddingModel(), store
        )
        pipeline.add_docs([Document(content="text", source="a.txt")])
        chunks, _ = store.added_batches[0]
        assert [c.chunk_index for c in chunks] == [0, 1, 2]

    def test_chunks_and_embeddings_are_aligned(self):
        """The number of chunks and embeddings passed to add_chunks must match."""
        store = FakeDocumentStore()
        pipeline = Pipeline(
            FakeChunker(returns=["c1", "c2"]), FakeEmbeddingModel(), store
        )
        pipeline.add_docs([Document(content="text", source="a.txt")])
        chunks, embeddings = store.added_batches[0]
        assert len(chunks) == len(embeddings)

    def test_empty_docs_does_not_call_add_chunks(self):
        """With an empty document list, add_chunks should never be called."""
        store = FakeDocumentStore()
        pipeline = Pipeline(FakeChunker(), FakeEmbeddingModel(), store)
        pipeline.add_docs([])
        assert store.added_batches == []


class TestPipelineSearch:
    def test_encodes_query_string(self):
        """search_document_store should encode the query string."""
        embedder = FakeEmbeddingModel()
        pipeline = Pipeline(FakeChunker(), embedder, FakeDocumentStore())
        pipeline.search_document_store("what is python?")
        assert embedder.calls == ["what is python?"]

    def test_passes_embedding_to_store(self):
        """The embedding returned by the model should be forwarded to the store."""
        store = FakeDocumentStore()
        pipeline = Pipeline(FakeChunker(), FakeEmbeddingModel(), store)
        pipeline.search_document_store("query")
        assert len(store.search_calls) == 1
        assert store.search_calls[0] == [0.0] * DIM

    def test_returns_results_from_store(self):
        """search_document_store should return exactly what the store returns."""
        expected = [Chunk(text="hello", source="a.txt", chunk_index=0)]
        store = FakeDocumentStore(search_result=expected)
        pipeline = Pipeline(FakeChunker(), FakeEmbeddingModel(), store)
        result = pipeline.search_document_store("query")
        assert result == expected

    def test_returns_empty_list_when_no_results(self):
        """search_document_store should return an empty list when the store finds nothing."""
        pipeline = Pipeline(FakeChunker(), FakeEmbeddingModel(), FakeDocumentStore())
        result = pipeline.search_document_store("query")
        assert result == []

    def test_search_does_not_call_ensure_collection(self):
        """Querying should have no write side-effects on the store."""
        store = FakeDocumentStore()
        pipeline = Pipeline(FakeChunker(), FakeEmbeddingModel(), store)
        pipeline.search_document_store("query")
        assert not store.ensured
