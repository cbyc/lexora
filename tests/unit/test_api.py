"""Tests for the FastAPI endpoints."""

from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api import app
from src.app_state import AppState
from src.config import Settings
from src.feed.models import DuplicateFeedError, Feed, FeedError, Post
from src.feed.service import FeedResult
from src.knowledge.loaders.models import Document
from src.models import NOT_FOUND, AskResponse, Chunk
from src.routers.feed import get_app_state as feed_get_app_state
from src.routers.knowledge import get_app_state as knowledge_get_app_state
from src.routers.knowledge import get_settings


class FakePipeline:
    def __init__(
        self,
        search_result: list[Chunk] | None = None,
        ask_response: AskResponse | None = None,
    ):
        self._search_result = search_result or []
        self._ask_response = ask_response or AskResponse(
            text="An answer.", sources=["notes/a.txt"]
        )
        self.search_calls: list[str] = []
        self.add_docs_calls: list[list[Document]] = []
        self.ask_calls: list[str] = []

    async def search_document_store(self, query: str) -> list[Chunk]:
        self.search_calls.append(query)
        return self._search_result

    async def add_docs(self, docs: list[Document]) -> None:
        self.add_docs_calls.append(docs)

    async def ask(self, question: str) -> AskResponse:
        self.ask_calls.append(question)
        return self._ask_response


class FakeFeedService:
    def __init__(
        self,
        result: FeedResult | None = None,
        add_feed_raises: Exception | None = None,
    ):
        self._result = result or FeedResult(posts=[], errors=[])
        self._add_feed_raises = add_feed_raises

    async def get_posts(self, **kwargs) -> FeedResult:
        return self._result

    async def add_feed(self, name: str, url: str) -> Feed:
        if self._add_feed_raises is not None:
            raise self._add_feed_raises
        return Feed(name=name, url=url)


def make_app_state(pipeline=None, feed_service=None) -> AppState:
    return AppState(
        pipeline=pipeline or FakePipeline(),
        feed_service=feed_service or FakeFeedService(),
    )


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
        app.dependency_overrides[knowledge_get_app_state] = lambda: make_app_state()
        response = client.post("/api/v1/query", json={"question": "what is python?"})
        assert response.status_code == 200

    def test_returns_list_of_chunk_dicts(self, client):
        """Response body should be a list of chunk objects."""
        results = [Chunk(text="hello", source="a.txt", chunk_index=0)]
        state = make_app_state(pipeline=FakePipeline(search_result=results))
        app.dependency_overrides[knowledge_get_app_state] = lambda: state
        response = client.post("/api/v1/query", json={"question": "what is python?"})
        body = response.json()
        assert isinstance(body, list)
        assert body[0]["text"] == "hello"
        assert body[0]["source"] == "a.txt"
        assert body[0]["chunk_index"] == 0

    def test_returns_empty_list_when_no_results(self, client):
        """An empty result set should return an empty list, not null."""
        app.dependency_overrides[knowledge_get_app_state] = lambda: make_app_state()
        response = client.post("/api/v1/query", json={"question": "anything"})
        assert response.json() == []

    def test_passes_question_to_pipeline(self, client):
        """The exact question string should be forwarded to the pipeline."""
        fake_pipeline = FakePipeline()
        state = make_app_state(pipeline=fake_pipeline)
        app.dependency_overrides[knowledge_get_app_state] = lambda: state
        client.post("/api/v1/query", json={"question": "what is python?"})
        assert fake_pipeline.search_calls == ["what is python?"]

    def test_question_over_max_length_returns_422(self, client):
        """A question exceeding 1024 characters should return HTTP 422."""
        app.dependency_overrides[knowledge_get_app_state] = lambda: make_app_state()
        response = client.post("/api/v1/query", json={"question": "x" * 1025})
        assert response.status_code == 422

    def test_question_at_max_length_returns_200(self, client):
        """A question of exactly 1024 characters should be accepted."""
        app.dependency_overrides[knowledge_get_app_state] = lambda: make_app_state()
        response = client.post("/api/v1/query", json={"question": "x" * 1024})
        assert response.status_code == 200

    def test_empty_question_returns_422(self, client):
        """An empty question string should fail Pydantic validation."""
        app.dependency_overrides[knowledge_get_app_state] = lambda: make_app_state()
        response = client.post("/api/v1/query", json={"question": ""})
        assert response.status_code == 422

    def test_missing_body_returns_422(self, client):
        """A request with no body should fail Pydantic validation."""
        app.dependency_overrides[knowledge_get_app_state] = lambda: make_app_state()
        response = client.post("/api/v1/query")
        assert response.status_code == 422


class TestReindexEndpoint:
    @pytest.fixture(autouse=True)
    def override_settings(self):
        app.dependency_overrides[get_settings] = lambda: Settings()
        yield

    def test_returns_200(self, client):
        """A reindex call should return HTTP 200."""
        app.dependency_overrides[knowledge_get_app_state] = lambda: make_app_state()
        with (
            patch("src.routers.knowledge.load_notes", return_value=[]),
            patch("src.routers.knowledge.load_bookmarks", return_value=[]),
        ):
            response = client.post("/api/v1/reindex")
        assert response.status_code == 200

    def test_calls_add_docs_on_pipeline(self, client):
        """Reindex should call add_docs on the pipeline exactly once."""
        fake_pipeline = FakePipeline()
        state = make_app_state(pipeline=fake_pipeline)
        app.dependency_overrides[knowledge_get_app_state] = lambda: state
        with (
            patch("src.routers.knowledge.load_notes", return_value=[]),
            patch("src.routers.knowledge.load_bookmarks", return_value=[]),
        ):
            client.post("/api/v1/reindex")
        assert len(fake_pipeline.add_docs_calls) == 1

    def test_combines_notes_and_bookmarks_into_one_call(self, client):
        """Notes and bookmarks should be merged before being passed to add_docs."""
        fake_pipeline = FakePipeline()
        state = make_app_state(pipeline=fake_pipeline)
        app.dependency_overrides[knowledge_get_app_state] = lambda: state
        note = Document(content="note content", source="note.txt")
        bookmark = Document(content="page content", source="https://example.com")
        with (
            patch("src.routers.knowledge.load_notes", return_value=[note]),
            patch("src.routers.knowledge.load_bookmarks", return_value=[bookmark]),
        ):
            client.post("/api/v1/reindex")
        docs_passed = fake_pipeline.add_docs_calls[0]
        assert len(docs_passed) == 2

    def test_response_body_has_expected_fields(self, client):
        """Response body should contain notes_indexed and bookmarks_indexed fields."""
        app.dependency_overrides[knowledge_get_app_state] = lambda: make_app_state()
        with (
            patch("src.routers.knowledge.load_notes", return_value=[]),
            patch("src.routers.knowledge.load_bookmarks", return_value=[]),
        ):
            response = client.post("/api/v1/reindex")
        body = response.json()
        assert "notes_indexed" in body
        assert "bookmarks_indexed" in body

    def test_response_counts_reflect_loaded_documents(self, client):
        """notes_indexed and bookmarks_indexed should match the number of docs loaded."""
        app.dependency_overrides[knowledge_get_app_state] = lambda: make_app_state()
        notes = [
            Document(content="n", source="a.txt"),
            Document(content="n2", source="b.txt"),
        ]
        bookmarks = [Document(content="b", source="https://example.com")]
        with (
            patch("src.routers.knowledge.load_notes", return_value=notes),
            patch("src.routers.knowledge.load_bookmarks", return_value=bookmarks),
        ):
            response = client.post("/api/v1/reindex")
        body = response.json()
        assert body["notes_indexed"] == 2
        assert body["bookmarks_indexed"] == 1


class TestAskEndpoint:
    def test_returns_200(self, client):
        """A well-formed question should return HTTP 200."""
        app.dependency_overrides[knowledge_get_app_state] = lambda: make_app_state()
        response = client.post("/api/v1/ask", json={"question": "What is Python?"})
        assert response.status_code == 200

    def test_response_has_text_and_sources(self, client):
        """Response body must contain text and sources fields."""
        response_val = AskResponse(
            text="Python is a language.", sources=["notes/py.txt"]
        )
        state = make_app_state(pipeline=FakePipeline(ask_response=response_val))
        app.dependency_overrides[knowledge_get_app_state] = lambda: state
        response = client.post("/api/v1/ask", json={"question": "What is Python?"})
        body = response.json()
        assert body["text"] == "Python is a language."
        assert body["sources"] == ["notes/py.txt"]

    def test_not_found_response_is_returned(self, client):
        """NOT_FOUND response from pipeline is forwarded as-is."""
        not_found = AskResponse(text=NOT_FOUND, sources=[])
        state = make_app_state(pipeline=FakePipeline(ask_response=not_found))
        app.dependency_overrides[knowledge_get_app_state] = lambda: state
        response = client.post("/api/v1/ask", json={"question": "capital of France?"})
        body = response.json()
        assert body["text"] == NOT_FOUND
        assert body["sources"] == []

    def test_passes_question_to_pipeline(self, client):
        """The exact question string should be forwarded to pipeline.ask."""
        fake_pipeline = FakePipeline()
        state = make_app_state(pipeline=fake_pipeline)
        app.dependency_overrides[knowledge_get_app_state] = lambda: state
        client.post("/api/v1/ask", json={"question": "What is the GIL?"})
        assert fake_pipeline.ask_calls == ["What is the GIL?"]

    def test_empty_question_returns_422(self, client):
        """An empty question string should fail Pydantic validation."""
        app.dependency_overrides[knowledge_get_app_state] = lambda: make_app_state()
        response = client.post("/api/v1/ask", json={"question": ""})
        assert response.status_code == 422

    def test_missing_body_returns_422(self, client):
        """A request with no body should fail Pydantic validation."""
        app.dependency_overrides[knowledge_get_app_state] = lambda: make_app_state()
        response = client.post("/api/v1/ask")
        assert response.status_code == 422


class TestGetRSSEndpoint:
    def test_returns_200_with_posts_and_errors_in_body(self, client):
        """GET /api/v1/rss should return 200 with posts and errors in the body."""
        post = Post(
            feed_name="Feed A",
            title="Article",
            url="https://example.com/1",
            published_at=datetime(2026, 2, 20, tzinfo=timezone.utc),
        )
        result = FeedResult(posts=[post], errors=[])
        state = make_app_state(feed_service=FakeFeedService(result=result))
        app.dependency_overrides[feed_get_app_state] = lambda: state
        response = client.get("/api/v1/rss")
        assert response.status_code == 200
        body = response.json()
        assert "posts" in body
        assert "errors" in body
        assert len(body["posts"]) == 1
        assert body["posts"][0]["title"] == "Article"

    def test_no_feeds_returns_empty_lists(self, client):
        """GET /api/v1/rss with no feeds returns empty posts and errors."""
        state = make_app_state(feed_service=FakeFeedService())
        app.dependency_overrides[feed_get_app_state] = lambda: state
        response = client.get("/api/v1/rss")
        assert response.status_code == 200
        body = response.json()
        assert body["posts"] == []
        assert body["errors"] == []

    def test_invalid_range_returns_400(self, client):
        """GET /api/v1/rss with invalid range returns 400."""

        class BadFeedService:
            async def get_posts(self, **kwargs):
                raise ValueError("invalid range: 'bad_range'")

            async def add_feed(self, name: str, url: str):
                pass

        state = make_app_state(feed_service=BadFeedService())
        app.dependency_overrides[feed_get_app_state] = lambda: state
        response = client.get("/api/v1/rss?range=bad_range")
        assert response.status_code == 400

    def test_errors_returned_in_body(self, client):
        """GET /api/v1/rss should include feed errors in the response body."""
        error = FeedError("Bad Feed", "https://bad.com/rss", "timeout")
        result = FeedResult(posts=[], errors=[error])
        state = make_app_state(feed_service=FakeFeedService(result=result))
        app.dependency_overrides[feed_get_app_state] = lambda: state
        response = client.get("/api/v1/rss")
        body = response.json()
        assert len(body["errors"]) == 1
        assert body["errors"][0]["feed_name"] == "Bad Feed"


class TestStaticFiles:
    def test_index_html_served(self, client):
        """GET / should return 200 with HTML content."""
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_static_css_served(self, client):
        """GET /styles/app.css should return 200."""
        response = client.get("/styles/app.css")
        assert response.status_code == 200

    def test_static_js_served(self, client):
        """GET /modules/feed.js should return 200."""
        response = client.get("/modules/feed.js")
        assert response.status_code == 200


class TestPutRSSEndpoint:
    def test_success_returns_201(self, client):
        """PUT /api/v1/rss with valid body returns 201."""
        state = make_app_state(feed_service=FakeFeedService())
        app.dependency_overrides[feed_get_app_state] = lambda: state
        response = client.put(
            "/api/v1/rss",
            json={"name": "New Feed", "url": "https://new.example.com/rss"},
        )
        assert response.status_code == 201

    def test_missing_fields_returns_422(self, client):
        """PUT /api/v1/rss with missing name returns 422."""
        state = make_app_state(feed_service=FakeFeedService())
        app.dependency_overrides[feed_get_app_state] = lambda: state
        response = client.put("/api/v1/rss", json={"url": "https://example.com/rss"})
        assert response.status_code == 422

    def test_duplicate_url_returns_409(self, client):
        """PUT /api/v1/rss with duplicate URL returns 409."""
        state = make_app_state(
            feed_service=FakeFeedService(
                add_feed_raises=DuplicateFeedError("Feed already exists")
            )
        )
        app.dependency_overrides[feed_get_app_state] = lambda: state
        response = client.put(
            "/api/v1/rss",
            json={"name": "Dup", "url": "https://existing.com/rss"},
        )
        assert response.status_code == 409

    def test_invalid_feed_url_returns_400(self, client):
        """PUT /api/v1/rss with invalid feed URL returns 400."""
        state = make_app_state(
            feed_service=FakeFeedService(add_feed_raises=ValueError("not a valid feed"))
        )
        app.dependency_overrides[feed_get_app_state] = lambda: state
        response = client.put(
            "/api/v1/rss",
            json={"name": "Bad", "url": "https://bad.example.com/rss"},
        )
        assert response.status_code == 400
