"""Tests for the FastAPI endpoints."""

import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from lexora.main import app
from lexora.app_state import AppState
from lexora.config import Settings
from lexora.feed.models import DuplicateFeedError, Feed, FeedError, Post
from lexora.feed.service import FeedResult
from lexora.knowledge.loaders.models import Document
from lexora.models import NOT_FOUND, AskResponse, Chunk
from lexora.routers.knowledge import _run_reindex
from lexora.routers.capabilities import get_app_state as capabilities_get_app_state
from lexora.routers.feed import get_app_state as feed_get_app_state
from lexora.routers.knowledge import get_app_state as knowledge_get_app_state
from lexora.routers.knowledge import get_settings
from lexora.routers.settings import get_env_file
from lexora.routers.settings import get_settings as settings_get_settings


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


_UNSET = object()


def make_app_state(pipeline=_UNSET, feed_service=None) -> AppState:
    return AppState(
        pipeline=FakePipeline() if pipeline is _UNSET else pipeline,
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

    @pytest.fixture(autouse=True)
    def reset_reindex_task(self):
        import lexora.routers.knowledge as rk

        rk._reindex_task = None
        yield
        rk._reindex_task = None

    def test_returns_202_when_no_reindex_running(self, client):
        """POST /reindex returns 202 when no reindex is currently running."""
        app.dependency_overrides[knowledge_get_app_state] = lambda: make_app_state()
        with patch("asyncio.create_task", return_value=MagicMock()):
            response = client.post("/api/v1/reindex")
        assert response.status_code == 202

    def test_response_body_is_started(self, client):
        """Response body is {"status": "started"} on successful reindex launch."""
        app.dependency_overrides[knowledge_get_app_state] = lambda: make_app_state()
        with patch("asyncio.create_task", return_value=MagicMock()):
            response = client.post("/api/v1/reindex")
        assert response.json() == {"status": "started"}

    def test_returns_409_when_reindex_already_running(self, client):
        """POST /reindex returns 409 when a reindex task is already in progress."""
        import lexora.routers.knowledge as rk

        app.dependency_overrides[knowledge_get_app_state] = lambda: make_app_state()
        rk._reindex_task = MagicMock(done=lambda: False)
        response = client.post("/api/v1/reindex")
        assert response.status_code == 409

    def test_503_when_pipeline_disabled(self, client):
        """POST /reindex returns 503 when pipeline is disabled."""
        state = make_app_state(pipeline=None)
        app.dependency_overrides[knowledge_get_app_state] = lambda: state
        response = client.post("/api/v1/reindex")
        assert response.status_code == 503


class TestRunReindex:
    @pytest.mark.anyio
    async def test_calls_add_docs_with_combined_docs(self):
        """_run_reindex passes notes + bookmarks merged into a single add_docs call."""
        fake_pipeline = FakePipeline()
        state = make_app_state(pipeline=fake_pipeline)
        cfg = Settings()
        note = Document(content="note content", source="note.txt")
        bookmark = Document(content="page content", source="https://example.com")
        with (
            patch(
                "lexora.routers.knowledge.load_notes",
                new=AsyncMock(return_value=[note]),
            ),
            patch("lexora.routers.knowledge.load_bookmarks", return_value=[bookmark]),
        ):
            await _run_reindex(fake_pipeline, cfg, state)
        assert fake_pipeline.add_docs_calls[0] == [note, bookmark]

    @pytest.mark.anyio
    async def test_calls_add_docs_once(self):
        """_run_reindex calls add_docs exactly once."""
        fake_pipeline = FakePipeline()
        state = make_app_state(pipeline=fake_pipeline)
        cfg = Settings()
        with (
            patch(
                "lexora.routers.knowledge.load_notes", new=AsyncMock(return_value=[])
            ),
            patch("lexora.routers.knowledge.load_bookmarks", return_value=[]),
        ):
            await _run_reindex(fake_pipeline, cfg, state)
        assert len(fake_pipeline.add_docs_calls) == 1


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
    def test_returns_200_with_posts_as_array(self, client):
        """GET /api/v1/rss should return 200 with a plain array of posts."""
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
        assert isinstance(body, list)
        assert len(body) == 1
        assert body[0]["title"] == "Article"
        assert body[0]["feed_name"] == "Feed A"

    def test_no_feeds_returns_empty_array(self, client):
        """GET /api/v1/rss with no feeds returns an empty array."""
        state = make_app_state(feed_service=FakeFeedService())
        app.dependency_overrides[feed_get_app_state] = lambda: state
        response = client.get("/api/v1/rss")
        assert response.status_code == 200
        assert response.json() == []

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

    def test_all_feeds_failed_sets_header(self, client):
        """GET /api/v1/rss sets X-Feed-Errors header when all feeds fail."""
        error = FeedError("Bad Feed", "https://bad.com/rss", "timeout")
        result = FeedResult(posts=[], errors=[error])
        state = make_app_state(feed_service=FakeFeedService(result=result))
        app.dependency_overrides[feed_get_app_state] = lambda: state
        response = client.get("/api/v1/rss")
        assert response.status_code == 200
        assert response.json() == []
        assert response.headers.get("x-feed-errors") == "all-feeds-failed"

    def test_partial_failure_no_header(self, client):
        """GET /api/v1/rss does not set X-Feed-Errors when some posts are returned."""
        post = Post(
            feed_name="Good Feed",
            title="OK",
            url="https://example.com/ok",
            published_at=datetime(2026, 2, 20, tzinfo=timezone.utc),
        )
        error = FeedError("Bad Feed", "https://bad.com/rss", "timeout")
        result = FeedResult(posts=[post], errors=[error])
        state = make_app_state(feed_service=FakeFeedService(result=result))
        app.dependency_overrides[feed_get_app_state] = lambda: state
        response = client.get("/api/v1/rss")
        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.headers.get("x-feed-errors") is None


class TestLifespan:
    def test_startup_succeeds_when_google_api_key_missing(self):
        """Lifespan starts without GOOGLE_API_KEY; pipeline is set to None."""
        fake_settings = MagicMock()
        fake_settings.google_api_key = None
        with (
            patch("lexora.main.settings", fake_settings),
            patch("lexora.main.YamlFeedStore"),
            patch("lexora.main.HttpFeedFetcher"),
            patch("lexora.main.FeedService"),
        ):
            with TestClient(app):
                assert app.state.app_state.pipeline is None

    def test_startup_uses_in_memory_vector_store_when_chroma_path_not_set(self):
        """VectorStore.in_memory is called when settings.chroma_path is falsy."""
        fake_settings = MagicMock()
        fake_settings.google_api_key = "test-key"
        fake_settings.chroma_path = None
        with (
            patch("lexora.main.settings", fake_settings),
            patch("lexora.main.GeminiEmbeddingModel"),
            patch("lexora.main.VectorStore") as mock_vs,
            patch("lexora.main.PydanticAIAskAgent"),
            patch("lexora.main.Pipeline"),
            patch("lexora.main.YamlFeedStore"),
            patch("lexora.main.HttpFeedFetcher"),
            patch("lexora.main.FeedService"),
        ):
            with TestClient(app):
                pass
        mock_vs.in_memory.assert_called_once()
        mock_vs.from_path.assert_not_called()

    def test_startup_uses_persistent_vector_store_when_chroma_path_set(self):
        """VectorStore.from_path is called with the configured path, collection, and dimension."""
        fake_settings = MagicMock()
        fake_settings.google_api_key = "test-key"
        fake_settings.chroma_path = "/data/chroma"
        with (
            patch("lexora.main.settings", fake_settings),
            patch("lexora.main.GeminiEmbeddingModel"),
            patch("lexora.main.VectorStore") as mock_vs,
            patch("lexora.main.PydanticAIAskAgent"),
            patch("lexora.main.Pipeline"),
            patch("lexora.main.YamlFeedStore"),
            patch("lexora.main.HttpFeedFetcher"),
            patch("lexora.main.FeedService"),
        ):
            with TestClient(app):
                pass
        mock_vs.from_path.assert_called_once_with(
            "/data/chroma",
            fake_settings.chroma_collection,
            fake_settings.embedding_dimension,
        )
        mock_vs.in_memory.assert_not_called()

    def test_startup_wires_pipeline_and_feed_service_into_app_state(self):
        """Lifespan stores the constructed pipeline and feed_service on app.state."""
        fake_pipeline = MagicMock()
        fake_feed_service = MagicMock()
        fake_settings = MagicMock()
        fake_settings.google_api_key = "test-key"
        with (
            patch("lexora.main.settings", fake_settings),
            patch("lexora.main.GeminiEmbeddingModel"),
            patch("lexora.main.VectorStore"),
            patch("lexora.main.PydanticAIAskAgent"),
            patch("lexora.main.Pipeline", return_value=fake_pipeline),
            patch("lexora.main.YamlFeedStore"),
            patch("lexora.main.HttpFeedFetcher"),
            patch("lexora.main.FeedService", return_value=fake_feed_service),
        ):
            with TestClient(app):
                state = app.state.app_state
        assert state.pipeline is fake_pipeline
        assert state.feed_service is fake_feed_service

    def test_startup_propagates_api_key_from_settings_to_os_environ(self):
        """GOOGLE_API_KEY read from .env is exported to os.environ for pydantic-ai."""
        fake_settings = MagicMock()
        fake_settings.google_api_key = "key-from-dotenv"
        fake_settings.chroma_path = None
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("GOOGLE_API_KEY", None)
            with (
                patch("lexora.main.settings", fake_settings),
                patch("lexora.main.GeminiEmbeddingModel"),
                patch("lexora.main.VectorStore"),
                patch("lexora.main.PydanticAIAskAgent"),
                patch("lexora.main.Pipeline"),
                patch("lexora.main.YamlFeedStore"),
                patch("lexora.main.HttpFeedFetcher"),
                patch("lexora.main.FeedService"),
            ):
                with TestClient(app):
                    pass
            assert os.environ.get("GOOGLE_API_KEY") == "key-from-dotenv"


class TestKnowledgeEndpointsWhenPipelineDisabled:
    @pytest.fixture(autouse=True)
    def disabled_state(self):
        state = make_app_state(pipeline=None)
        app.dependency_overrides[knowledge_get_app_state] = lambda: state

    def test_query_returns_503(self, client):
        """POST /query returns 503 when pipeline is disabled."""
        response = client.post("/api/v1/query", json={"question": "test?"})
        assert response.status_code == 503

    def test_ask_returns_503(self, client):
        """POST /ask returns 503 when pipeline is disabled."""
        response = client.post("/api/v1/ask", json={"question": "test?"})
        assert response.status_code == 503

    def test_reindex_returns_503(self, client):
        """POST /reindex returns 503 when pipeline is disabled."""
        app.dependency_overrides[get_settings] = lambda: Settings()
        with (
            patch(
                "lexora.routers.knowledge.load_notes", new=AsyncMock(return_value=[])
            ),
            patch("lexora.routers.knowledge.load_bookmarks", return_value=[]),
        ):
            response = client.post("/api/v1/reindex")
        assert response.status_code == 503


class TestCapabilities:
    def test_mind_enabled_when_pipeline_present(self, client):
        """GET /capabilities returns mind_enabled=true when pipeline is wired."""
        state = make_app_state(pipeline=FakePipeline())
        app.dependency_overrides[capabilities_get_app_state] = lambda: state
        response = client.get("/api/v1/capabilities")
        assert response.status_code == 200
        assert response.json() == {"mind_enabled": True, "feed_enabled": True}

    def test_mind_disabled_when_pipeline_absent(self, client):
        """GET /capabilities returns mind_enabled=false when pipeline is None."""
        state = make_app_state(pipeline=None)
        app.dependency_overrides[capabilities_get_app_state] = lambda: state
        response = client.get("/api/v1/capabilities")
        assert response.status_code == 200
        assert response.json() == {"mind_enabled": False, "feed_enabled": True}


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


@pytest.fixture
def settings_env_file(tmp_path):
    env_path = tmp_path / ".env"
    app.dependency_overrides[get_env_file] = lambda: env_path
    yield env_path


class TestSettingsEndpoints:
    @pytest.fixture(autouse=True)
    def override_settings(self):
        fake = Settings(
            google_api_key="secret",
            notes_dir="./data/notes",
            bookmarks_profile_path="/ff/profile",
        )
        app.dependency_overrides[settings_get_settings] = lambda: fake
        yield

    # ── GET /api/v1/settings ─────────────────────────────────────────

    def test_get_returns_200(self, client):
        """GET /api/v1/settings returns HTTP 200."""
        response = client.get("/api/v1/settings")
        assert response.status_code == 200

    def test_get_returns_key_set_true_when_key_present(self, client):
        """google_api_key_set is true when an API key is configured."""
        body = client.get("/api/v1/settings").json()
        assert body["google_api_key_set"] is True

    def test_get_returns_key_set_false_when_key_absent(self, client):
        """google_api_key_set is false when no API key is configured."""
        app.dependency_overrides[settings_get_settings] = lambda: Settings(
            google_api_key=None, notes_dir="./data/notes"
        )
        body = client.get("/api/v1/settings").json()
        assert body["google_api_key_set"] is False

    def test_get_does_not_return_raw_api_key(self, client):
        """Response must never expose the raw API key value."""
        body = client.get("/api/v1/settings").json()
        assert "google_api_key" not in body
        assert "secret" not in str(body)

    def test_get_returns_notes_dir(self, client):
        """notes_dir is returned in the response."""
        body = client.get("/api/v1/settings").json()
        assert body["notes_dir"] == "./data/notes"

    def test_get_returns_bookmarks_profile_path(self, client):
        """bookmarks_profile_path is returned when configured."""
        body = client.get("/api/v1/settings").json()
        assert body["bookmarks_profile_path"] == "/ff/profile"

    def test_get_returns_null_bookmarks_when_not_configured(self, client):
        """bookmarks_profile_path is null when not configured."""
        app.dependency_overrides[settings_get_settings] = lambda: Settings(
            google_api_key=None, notes_dir="./data/notes", bookmarks_profile_path=None
        )
        body = client.get("/api/v1/settings").json()
        assert body["bookmarks_profile_path"] is None

    # ── PUT /api/v1/settings ─────────────────────────────────────────

    def test_put_returns_200(self, client, settings_env_file):
        """PUT /api/v1/settings returns HTTP 200."""
        response = client.put("/api/v1/settings", json={"google_api_key": "new-key"})
        assert response.status_code == 200

    def test_put_returns_saved_and_restart_required(self, client, settings_env_file):
        """Response body contains saved=true and restart_required=true."""
        body = client.put("/api/v1/settings", json={"google_api_key": "k"}).json()
        assert body["saved"] is True
        assert body["restart_required"] is True

    def test_put_writes_google_api_key_to_env_file(self, client, settings_env_file):
        """PUT writes GOOGLE_API_KEY to the .env file."""
        client.put("/api/v1/settings", json={"google_api_key": "my-key"})
        assert 'GOOGLE_API_KEY="my-key"' in settings_env_file.read_text()

    def test_put_writes_notes_dir_to_env_file(self, client, settings_env_file):
        """PUT writes NOTES_DIR to the .env file."""
        client.put("/api/v1/settings", json={"notes_dir": "/my/notes"})
        assert 'NOTES_DIR="/my/notes"' in settings_env_file.read_text()

    def test_put_writes_bookmarks_profile_path(self, client, settings_env_file):
        """PUT writes BOOKMARKS_PROFILE_PATH to the .env file."""
        client.put("/api/v1/settings", json={"bookmarks_profile_path": "/ff/profile"})
        assert 'BOOKMARKS_PROFILE_PATH="/ff/profile"' in settings_env_file.read_text()

    def test_put_skips_empty_google_api_key(self, client, settings_env_file):
        """PUT with empty google_api_key does not write GOOGLE_API_KEY."""
        client.put("/api/v1/settings", json={"notes_dir": "/some/dir"})
        assert "GOOGLE_API_KEY" not in settings_env_file.read_text()

    def test_put_skips_empty_notes_dir(self, client, settings_env_file):
        """PUT with empty notes_dir does not write NOTES_DIR."""
        client.put("/api/v1/settings", json={"google_api_key": "k"})
        assert "NOTES_DIR" not in settings_env_file.read_text()

    def test_put_skips_empty_bookmarks_profile_path(self, client, settings_env_file):
        """PUT with empty bookmarks_profile_path does not write BOOKMARKS_PROFILE_PATH."""
        client.put("/api/v1/settings", json={"google_api_key": "k"})
        assert "BOOKMARKS_PROFILE_PATH" not in settings_env_file.read_text()

    def test_put_preserves_existing_keys_in_env_file(self, client, settings_env_file):
        """PUT does not remove unrelated keys from the .env file."""
        settings_env_file.write_text('CHROMA_PATH="/data/chroma"\n')
        client.put("/api/v1/settings", json={"google_api_key": "k"})
        assert 'CHROMA_PATH="/data/chroma"' in settings_env_file.read_text()

    def test_put_updates_existing_key_in_place(self, client, settings_env_file):
        """PUT updates an existing key rather than appending a duplicate."""
        settings_env_file.write_text('GOOGLE_API_KEY="old"\n')
        client.put("/api/v1/settings", json={"google_api_key": "new"})
        content = settings_env_file.read_text()
        assert "old" not in content
        assert content.count("GOOGLE_API_KEY") == 1

    def test_put_creates_env_file_if_missing(self, client, settings_env_file):
        """PUT creates the .env file when it does not exist."""
        assert not settings_env_file.exists()
        client.put("/api/v1/settings", json={"google_api_key": "k"})
        assert settings_env_file.exists()


class TestBrowseDirectoryEndpoint:
    def test_returns_200(self, client):
        """POST /api/v1/settings/browse-directory returns HTTP 200."""
        with (
            patch("lexora.routers.settings.sys") as mock_sys,
            patch("lexora.routers.settings.subprocess.run") as mock_run,
        ):
            mock_sys.platform = "darwin"
            mock_run.return_value = MagicMock(returncode=0, stdout="/sel/path\n")
            response = client.post("/api/v1/settings/browse-directory")
        assert response.status_code == 200

    def test_returns_path_when_osascript_succeeds(self, client):
        """Returns the selected path (stripped) when osascript exits 0."""
        with (
            patch("lexora.routers.settings.sys") as mock_sys,
            patch("lexora.routers.settings.subprocess.run") as mock_run,
        ):
            mock_sys.platform = "darwin"
            mock_run.return_value = MagicMock(returncode=0, stdout="/Users/me/notes\n")
            body = client.post("/api/v1/settings/browse-directory").json()
        assert body["path"] == "/Users/me/notes"

    def test_returns_null_when_user_cancels(self, client):
        """Returns null when osascript exits non-zero (user cancelled)."""
        with (
            patch("lexora.routers.settings.sys") as mock_sys,
            patch("lexora.routers.settings.subprocess.run") as mock_run,
        ):
            mock_sys.platform = "darwin"
            mock_run.return_value = MagicMock(returncode=1, stdout="")
            body = client.post("/api/v1/settings/browse-directory").json()
        assert body["path"] is None

    def test_returns_null_on_non_macos(self, client):
        """Returns null without calling subprocess on non-macOS platforms."""
        with (
            patch("lexora.routers.settings.sys") as mock_sys,
            patch("lexora.routers.settings.subprocess.run") as mock_run,
        ):
            mock_sys.platform = "linux"
            body = client.post("/api/v1/settings/browse-directory").json()
        assert body["path"] is None
        mock_run.assert_not_called()
