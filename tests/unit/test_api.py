"""Tests for the FastAPI endpoints."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api import app, get_pipeline, get_settings
from src.config import Settings
from src.loaders.models import Document
from src.models import Chunk


class FakePipeline:
    def __init__(self, search_result: list[Chunk] | None = None):
        self._search_result = search_result or []
        self.search_calls: list[str] = []
        self.add_docs_calls: list[list[Document]] = []

    def search_document_store(self, query: str) -> list[Chunk]:
        self.search_calls.append(query)
        return self._search_result

    def add_docs(self, docs: list[Document]) -> None:
        self.add_docs_calls.append(docs)


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=True)


@pytest.fixture(autouse=True)
def reset_overrides():
    yield
    app.dependency_overrides.clear()


class TestQueryEndpoint:
    def test_returns_200(self, client):
        """A well-formed question should return HTTP 200."""
        app.dependency_overrides[get_pipeline] = lambda: FakePipeline()
        response = client.post("/api/v1/query", json={"question": "what is python?"})
        assert response.status_code == 200

    def test_returns_list_of_chunk_dicts(self, client):
        """Response body should be a list of chunk objects."""
        results = [Chunk(text="hello", source="a.txt", chunk_index=0)]
        app.dependency_overrides[get_pipeline] = lambda: FakePipeline(
            search_result=results
        )
        response = client.post("/api/v1/query", json={"question": "what is python?"})
        body = response.json()
        assert isinstance(body, list)
        assert body[0]["text"] == "hello"
        assert body[0]["source"] == "a.txt"
        assert body[0]["chunk_index"] == 0

    def test_returns_empty_list_when_no_results(self, client):
        """An empty result set should return an empty list, not null."""
        app.dependency_overrides[get_pipeline] = lambda: FakePipeline()
        response = client.post("/api/v1/query", json={"question": "anything"})
        assert response.json() == []

    def test_passes_question_to_pipeline(self, client):
        """The exact question string should be forwarded to the pipeline."""
        fake = FakePipeline()
        app.dependency_overrides[get_pipeline] = lambda: fake
        client.post("/api/v1/query", json={"question": "what is python?"})
        assert fake.search_calls == ["what is python?"]

    def test_question_over_max_length_returns_422(self, client):
        """A question exceeding 1024 characters should return HTTP 422."""
        app.dependency_overrides[get_pipeline] = lambda: FakePipeline()
        response = client.post("/api/v1/query", json={"question": "x" * 1025})
        assert response.status_code == 422

    def test_question_at_max_length_returns_200(self, client):
        """A question of exactly 1024 characters should be accepted."""
        app.dependency_overrides[get_pipeline] = lambda: FakePipeline()
        response = client.post("/api/v1/query", json={"question": "x" * 1024})
        assert response.status_code == 200

    def test_empty_question_returns_422(self, client):
        """An empty question string should fail Pydantic validation."""
        app.dependency_overrides[get_pipeline] = lambda: FakePipeline()
        response = client.post("/api/v1/query", json={"question": ""})
        assert response.status_code == 422

    def test_missing_body_returns_422(self, client):
        """A request with no body should fail Pydantic validation."""
        app.dependency_overrides[get_pipeline] = lambda: FakePipeline()
        response = client.post("/api/v1/query")
        assert response.status_code == 422


class TestReindexEndpoint:
    @pytest.fixture(autouse=True)
    def override_settings(self):
        app.dependency_overrides[get_settings] = lambda: Settings()
        yield

    def test_returns_200(self, client):
        """A reindex call should return HTTP 200."""
        app.dependency_overrides[get_pipeline] = lambda: FakePipeline()
        with (
            patch("api.load_notes", return_value=[]),
            patch("api.load_bookmarks", return_value=[]),
        ):
            response = client.post("/api/v1/reindex")
        assert response.status_code == 200

    def test_calls_add_docs_on_pipeline(self, client):
        """Reindex should call add_docs on the pipeline exactly once."""
        fake = FakePipeline()
        app.dependency_overrides[get_pipeline] = lambda: fake
        with (
            patch("api.load_notes", return_value=[]),
            patch("api.load_bookmarks", return_value=[]),
        ):
            client.post("/api/v1/reindex")
        assert len(fake.add_docs_calls) == 1

    def test_combines_notes_and_bookmarks_into_one_call(self, client):
        """Notes and bookmarks should be merged before being passed to add_docs."""
        fake = FakePipeline()
        app.dependency_overrides[get_pipeline] = lambda: fake
        note = Document(content="note content", source="note.txt")
        bookmark = Document(content="page content", source="https://example.com")
        with (
            patch("api.load_notes", return_value=[note]),
            patch("api.load_bookmarks", return_value=[bookmark]),
        ):
            client.post("/api/v1/reindex")
        docs_passed = fake.add_docs_calls[0]
        assert len(docs_passed) == 2

    def test_response_body_has_expected_fields(self, client):
        """Response body should contain notes_indexed and bookmarks_indexed fields."""
        app.dependency_overrides[get_pipeline] = lambda: FakePipeline()
        with (
            patch("api.load_notes", return_value=[]),
            patch("api.load_bookmarks", return_value=[]),
        ):
            response = client.post("/api/v1/reindex")
        body = response.json()
        assert "notes_indexed" in body
        assert "bookmarks_indexed" in body

    def test_response_counts_reflect_loaded_documents(self, client):
        """notes_indexed and bookmarks_indexed should match the number of docs loaded."""
        app.dependency_overrides[get_pipeline] = lambda: FakePipeline()
        notes = [
            Document(content="n", source="a.txt"),
            Document(content="n2", source="b.txt"),
        ]
        bookmarks = [Document(content="b", source="https://example.com")]
        with (
            patch("api.load_notes", return_value=notes),
            patch("api.load_bookmarks", return_value=bookmarks),
        ):
            response = client.post("/api/v1/reindex")
        body = response.json()
        assert body["notes_indexed"] == 2
        assert body["bookmarks_indexed"] == 1
