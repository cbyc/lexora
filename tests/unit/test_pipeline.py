"""Tests for the Pipeline orchestration class."""

import asyncio

from knowledge.loaders.models import Document
from models import NOT_FOUND, AskResponse, Chunk
from knowledge.pipeline import Pipeline

DIM = 768


class FakeAskAgent:
    def __init__(self, response: AskResponse | None = None):
        self.calls: list[tuple[str, list[Chunk]]] = []
        self._response = response or AskResponse(
            text="An answer.", sources=["notes/a.txt"]
        )

    async def answer(self, question: str, chunks: list[Chunk]) -> AskResponse:
        self.calls.append((question, chunks))
        return self._response


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

    async def encode(self, text: str) -> list[float]:
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
    def test_chunker_called_once_per_doc(self):
        """The chunker should be called exactly once for each document's content."""
        chunker = FakeChunker()
        pipeline = Pipeline(
            chunker, FakeEmbeddingModel(), FakeDocumentStore(), FakeAskAgent()
        )
        asyncio.run(
            pipeline.add_docs(
                [
                    Document(content="first", source="a.txt"),
                    Document(content="second", source="b.txt"),
                ]
            )
        )
        assert chunker.calls == ["first", "second"]

    def test_embedding_model_called_once_per_chunk(self):
        """The embedding model should be called once for every chunk produced."""
        embedder = FakeEmbeddingModel()
        pipeline = Pipeline(
            FakeChunker(returns=["c1", "c2", "c3"]),
            embedder,
            FakeDocumentStore(),
            FakeAskAgent(),
        )
        asyncio.run(pipeline.add_docs([Document(content="text", source="a.txt")]))
        assert embedder.calls == ["c1", "c2", "c3"]

    def test_add_chunks_called_once_per_doc(self):
        """add_chunks on the store should be called once per document."""
        store = FakeDocumentStore()
        pipeline = Pipeline(
            FakeChunker(returns=["c1"]), FakeEmbeddingModel(), store, FakeAskAgent()
        )
        asyncio.run(
            pipeline.add_docs(
                [
                    Document(content="first", source="a.txt"),
                    Document(content="second", source="b.txt"),
                ]
            )
        )
        assert len(store.added_batches) == 2

    def test_chunk_objects_carry_correct_source(self):
        """Each Chunk passed to the store should have the source of its Document."""
        store = FakeDocumentStore()
        pipeline = Pipeline(
            FakeChunker(returns=["c1", "c2"]),
            FakeEmbeddingModel(),
            store,
            FakeAskAgent(),
        )
        asyncio.run(pipeline.add_docs([Document(content="text", source="notes/a.txt")]))
        chunks, _ = store.added_batches[0]
        assert all(c.source == "notes/a.txt" for c in chunks)

    def test_chunk_objects_carry_sequential_index(self):
        """Chunks for a document should be indexed 0, 1, 2, … in order."""
        store = FakeDocumentStore()
        pipeline = Pipeline(
            FakeChunker(returns=["c1", "c2", "c3"]),
            FakeEmbeddingModel(),
            store,
            FakeAskAgent(),
        )
        asyncio.run(pipeline.add_docs([Document(content="text", source="a.txt")]))
        chunks, _ = store.added_batches[0]
        assert [c.chunk_index for c in chunks] == [0, 1, 2]

    def test_chunks_and_embeddings_are_aligned(self):
        """The number of chunks and embeddings passed to add_chunks must match."""
        store = FakeDocumentStore()
        pipeline = Pipeline(
            FakeChunker(returns=["c1", "c2"]),
            FakeEmbeddingModel(),
            store,
            FakeAskAgent(),
        )
        asyncio.run(pipeline.add_docs([Document(content="text", source="a.txt")]))
        chunks, embeddings = store.added_batches[0]
        assert len(chunks) == len(embeddings)

    def test_empty_docs_does_not_call_add_chunks(self):
        """With an empty document list, add_chunks should never be called."""
        store = FakeDocumentStore()
        pipeline = Pipeline(FakeChunker(), FakeEmbeddingModel(), store, FakeAskAgent())
        asyncio.run(pipeline.add_docs([]))
        assert store.added_batches == []


class TestPipelineAsk:
    def test_delegates_question_and_chunks_to_ask_agent(self):
        """ask() should pass the question and retrieved chunks to the agent."""
        chunks = [Chunk(text="hello", source="a.txt", chunk_index=0)]
        store = FakeDocumentStore(search_result=chunks)
        fake_agent = FakeAskAgent()
        pipeline = Pipeline(FakeChunker(), FakeEmbeddingModel(), store, fake_agent)
        asyncio.run(pipeline.ask("What is python?"))
        assert len(fake_agent.calls) == 1
        question, passed_chunks = fake_agent.calls[0]
        assert question == "What is python?"
        assert passed_chunks == chunks

    def test_returns_ask_agent_response(self):
        """ask() should return whatever AskAgent.answer returns."""
        expected = AskResponse(text="Python is great.", sources=["notes/python.txt"])
        fake_agent = FakeAskAgent(response=expected)
        pipeline = Pipeline(
            FakeChunker(), FakeEmbeddingModel(), FakeDocumentStore(), fake_agent
        )
        result = asyncio.run(pipeline.ask("What is python?"))
        assert result == expected

    def test_not_found_response_is_returned(self):
        """ask() should return NOT_FOUND response when the agent cannot answer."""
        not_found = AskResponse(text=NOT_FOUND, sources=[])
        fake_agent = FakeAskAgent(response=not_found)
        pipeline = Pipeline(
            FakeChunker(), FakeEmbeddingModel(), FakeDocumentStore(), fake_agent
        )
        result = asyncio.run(pipeline.ask("capital of France?"))
        assert result.text == NOT_FOUND
        assert result.sources == []


class TestPipelineSearch:
    def test_encodes_query_string(self):
        """search_document_store should encode the query string."""
        embedder = FakeEmbeddingModel()
        pipeline = Pipeline(
            FakeChunker(), embedder, FakeDocumentStore(), FakeAskAgent()
        )
        asyncio.run(pipeline.search_document_store("what is python?"))
        assert embedder.calls == ["what is python?"]

    def test_passes_embedding_to_store(self):
        """The embedding returned by the model should be forwarded to the store."""
        store = FakeDocumentStore()
        pipeline = Pipeline(FakeChunker(), FakeEmbeddingModel(), store, FakeAskAgent())
        asyncio.run(pipeline.search_document_store("query"))
        assert len(store.search_calls) == 1
        assert store.search_calls[0] == [0.0] * DIM

    def test_returns_results_from_store(self):
        """search_document_store should return exactly what the store returns."""
        expected = [Chunk(text="hello", source="a.txt", chunk_index=0)]
        store = FakeDocumentStore(search_result=expected)
        pipeline = Pipeline(FakeChunker(), FakeEmbeddingModel(), store, FakeAskAgent())
        result = asyncio.run(pipeline.search_document_store("query"))
        assert result == expected

    def test_returns_empty_list_when_no_results(self):
        """search_document_store should return an empty list when the store finds nothing."""
        pipeline = Pipeline(
            FakeChunker(), FakeEmbeddingModel(), FakeDocumentStore(), FakeAskAgent()
        )
        result = asyncio.run(pipeline.search_document_store("query"))
        assert result == []

    def test_search_does_not_call_ensure_collection(self):
        """Querying should have no write side-effects on the store."""
        store = FakeDocumentStore()
        pipeline = Pipeline(FakeChunker(), FakeEmbeddingModel(), store, FakeAskAgent())
        asyncio.run(pipeline.search_document_store("query"))
        assert not store.ensured
