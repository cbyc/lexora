# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

This project uses `uv` for package management and `ruff` for linting.

```bash
# Run the API server
uv run python api.py

# Run all tests
uv run pytest

# Run a single test file
uv run pytest tests/unit/test_pipeline.py

# Run a specific test
uv run pytest tests/unit/test_pipeline.py::TestPipelineSearch::test_returns_results_from_store

# Lint
uv run ruff check .

# Format
uv run ruff format .
```

## Architecture

Lexora-Link is a personal knowledge and feed aggregation server. It ingests documents from local notes and Firefox bookmarks, embeds them via the Gemini API, and serves both a semantic search/QA API and an RSS feed reader from a single process, including a static web frontend.

### Ports (Abstractions)

`src/ports.py` defines six `Protocol` classes that form the boundary between the application and infrastructure:

- `Chunker` — `chunk(text) -> list[str]`
- `EmbeddingModel` — `async encode(text) -> list[float]`
- `DocumentStore` — `ensure_collection()`, `add_chunks(...)`, `search(...)`
- `AskAgent` — `async answer(question, chunks) -> AskResponse`
- `FeedStore` — `load_feeds()`, `save_feeds()`, `add_feed()`, `ensure_data_file()`
- `FeedFetcher` — `async fetch_feed(...)`, `async validate_feed(...)`, `async fetch_all_feeds(...)`

All application logic depends only on these protocols. Concrete implementations are wired at startup in `api.py`.

### Domain Packages

- `src/knowledge/` — knowledge retrieval domain
  - `chunker.py` — `SimpleChunker`
  - `embedder.py` — `GeminiEmbeddingModel` (async, wraps `google.genai`)
  - `pipeline.py` — `Pipeline` application orchestrator
  - `vector_store.py` — `VectorStore` (ChromaDB)
  - `ask_agent.py` — `PydanticAIAskAgent`
  - `loaders/` — `notes.py`, `bookmarks.py`, `sync_state.py`, `models.py`

- `src/feed/` — RSS/Atom feed domain
  - `models.py` — `Feed`, `Post`, `FeedError`, `DuplicateFeedError`
  - `store.py` — `YamlFeedStore`
  - `fetcher.py` — `HttpFeedFetcher` (httpx + feedparser)
  - `date_range.py` — `parse_date_range()`
  - `service.py` — `FeedService` application orchestrator

### Data Flow

1. **Loaders** (`src/knowledge/loaders/`) read source data and produce `Document` objects.
   - `notes.py`: Reads `.txt` files from `data/notes/`. Incremental sync via `data/notes_sync.json`.
   - `bookmarks.py`: Reads Firefox's `places.sqlite`, fetches each URL's content via `trafilatura`, and produces documents. Incremental sync via `data/bm_sync.json`. The DB is copied to a temp file before reading to avoid lock conflicts with Firefox.
   - `sync_state.py`: Shared helper that persists a `last_sync_timestamp` to a JSON file for both loaders.

2. **Chunker** (`src/knowledge/chunker.py`): `SimpleChunker` implements `Chunker`. Splits text into overlapping fixed-size character windows.

3. **Embedder** (`src/knowledge/embedder.py`): `GeminiEmbeddingModel` implements `EmbeddingModel`. Wraps `google.genai`, produces 768-dimensional vectors. `encode` is `async` (uses `asyncio.to_thread` to wrap the synchronous SDK call).

4. **Pipeline** (`src/knowledge/pipeline.py`): Application-layer orchestrator. Accepts the four knowledge ports via constructor injection. `add_docs` and `search_document_store` are `async` because they `await self._embedding_model.encode(...)`.

5. **Vector Store** (`src/knowledge/vector_store.py`): `VectorStore` implements `DocumentStore`. Wraps ChromaDB. Point IDs are deterministic `uuid5` hashes of `source:chunk_index:text`, enabling idempotent upserts. Use the factory classmethods:
   - `VectorStore.in_memory()` — ephemeral, for development and tests (appends a UUID suffix to avoid ChromaDB singleton state leakage)
   - `VectorStore.from_path(path)` — persistent local storage (no server required)

6. **Ask Agent** (`src/knowledge/ask_agent.py`): `PydanticAIAskAgent` implements `AskAgent`. Uses pydantic-ai to run an LLM with structured output (`AskResponse`). Formats retrieved chunks as `SOURCE: <path>\n<text>` blocks and instructs the LLM to answer strictly from the provided context. Provider and model are selected via the `LLM_MODEL` env var; API keys are read from the environment by pydantic-ai automatically.

7. **FeedService** (`src/feed/service.py`): Application-layer orchestrator for the feed domain. Stores `default_range`, `max_posts_per_feed`, and `timeout` as instance attributes so the router doesn't need settings injection.

8. **API** (`api.py`): Thin composition root — no route handlers. Constructs all concrete implementations, wraps them in `AppState`, and stores on `app.state`. Includes routers and mounts the static frontend:
   - `app.include_router(knowledge.router)`
   - `app.include_router(feed.router)`
   - `app.mount("/", StaticFiles(directory="static", html=True))`

### Routers

- `src/routers/knowledge.py` — `GET/POST /api/v1/query`, `/api/v1/ask`, `/api/v1/reindex`
- `src/routers/feed.py` — `GET /api/v1/rss`, `PUT /api/v1/rss`

Each router has its own `get_app_state` dependency function (not shared) to allow independent injection in tests.

### AppState

`src/app_state.py` — `AppState(NamedTuple)` with `pipeline: Pipeline` and `feed_service: FeedService`. Stored on `app.state.app_state` at startup.

### Key Models

- `src/knowledge/loaders/models.py` — `Document(content, source)`: raw loaded document.
- `src/models.py` — `Chunk(text, source, chunk_index)`; `QueryRequest`; `ReindexResponse`; `AskResponse(text, sources)` with a validator that rejects answers with empty sources; `NOT_FOUND` sentinel string; `AddFeedRequest`; `AddFeedResponse`.
- `src/feed/models.py` — `Feed(name, url)`, `Post(feed_name, title, url, published_at)`, `FeedError(feed_name, url, error)`, `DuplicateFeedError`.

### Testing Approach

- Unit tests live in `tests/unit/` and run with no external dependencies.
- `Pipeline` tests use inline **fake** implementations of all four knowledge ports. Fake `encode` is `async def`.
- `VectorStore` tests use `VectorStore.in_memory()`.
- `PydanticAIAskAgent` tests mock pydantic-ai's `Agent` with `AsyncMock` — no real LLM call.
- `GeminiEmbeddingModel` tests mock `google.genai.Client` — no real API call.
- API tests (`tests/unit/test_api.py`) use FastAPI's `TestClient` with `app.dependency_overrides` for both `knowledge_get_app_state` and `feed_get_app_state`, plus `unittest.mock.patch` for loader functions. Patch targets use the router module path: `src.routers.knowledge.load_notes`, etc.
- Loader tests use `tmp_path` and SQLite fixtures.
- Feed tests use `FakeFeedStore`, `FakeFeedFetcher`, and `httpx.MockTransport`.
- Eval tests live in `tests/evals/` and require a real LLM API key. Run them separately: `uv run pytest tests/evals/`.

### Configuration

`src/config.py` defines a `Settings(BaseSettings)` class (via `pydantic-settings`). Settings are read from environment variables or a `.env` file in the project root. The `Settings` instance is created once at module level in `api.py` and injected into route handlers via the `get_settings` FastAPI dependency.

| Env var | Default | Description |
|---|---|---|
| `HOST` | `0.0.0.0` | Server bind address |
| `PORT` | `9002` | Server port |
| `LOG_LEVEL` | `WARNING` | Log verbosity |
| `GOOGLE_API_KEY` | _(none)_ | **Required.** Used for Gemini embeddings. |
| `GEMINI_EMBEDDING_MODEL` | `models/text-embedding-004` | Gemini embedding model ID |
| `EMBEDDING_DIMENSION` | `768` | Embedding vector size |
| `CHROMA_PATH` | _(none)_ | ChromaDB persistence directory; omit to use in-memory mode |
| `CHROMA_COLLECTION` | `lexora` | ChromaDB collection name |
| `CHUNK_SIZE` | `500` | Characters per chunk |
| `CHUNK_OVERLAP` | `50` | Overlap between chunks |
| `NOTES_DIR` | `./data/notes` | Directory of `.txt` notes |
| `NOTES_SYNC_STATE_PATH` | `./data/notes_sync.json` | Notes incremental sync state |
| `BOOKMARKS_PROFILE_PATH` | _(none)_ | Firefox profile path; omit to auto-detect |
| `BOOKMARKS_SYNC_STATE_PATH` | `./data/bm_sync.json` | Bookmarks incremental sync state |
| `BOOKMARKS_FETCH_TIMEOUT` | `15` | HTTP timeout per bookmark (seconds) |
| `BOOKMARKS_MAX_CONTENT_LENGTH` | `50000` | Max characters extracted per page |
| `LLM_MODEL` | `google-gla:gemini-2.0-flash` | pydantic-ai model string for `/ask` |
| `FEED_DATA_FILE` | `./data/feeds.yaml` | YAML file storing feed URLs |
| `FEED_MAX_POSTS_PER_FEED` | `50` | Max posts fetched per feed |
| `FEED_FETCH_TIMEOUT_SEC` | `10` | Per-feed fetch timeout (seconds) |
| `FEED_DEFAULT_RANGE` | `last_month` | Default date range for feed queries |

### Notes

- Logging uses structlog's keyword-argument style throughout: `logger.info("event_name", key=value)`.
- `docs/MONOLITH_PLAN.md` tracks the consolidation plan and implementation history.
- `docs/LLM_PLAN.md` describes the design and implementation of the `/ask` endpoint.
- The static frontend lives in `static/`. It is a vanilla JS app with no build step.
