# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

This project uses `uv` for package management and `ruff` for linting.

```bash
# Run the API server
uv run lexora

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

Lexora is a personal knowledge and feed aggregation server. It ingests documents from local notes and Firefox bookmarks, embeds them via the Gemini API, and serves both a semantic search/QA API and an RSS feed reader from a single process, including a static web frontend.

### Ports (Abstractions)

`src/lexora/ports.py` defines seven `Protocol` classes that form the boundary between the application and infrastructure:

- `Chunker` — `chunk(text) -> list[str]`
- `EmbeddingModel` — `async encode(text) -> list[float]`
- `DocumentStore` — `ensure_collection()`, `add_chunks(...)`, `search(...)`
- `AskAgent` — `async answer(question, chunks) -> AskResponse`
- `FeedStore` — `load_feeds()`, `save_feeds()`, `add_feed()`, `ensure_data_file()`
- `FeedFetcher` — `async fetch_feed(...)`, `async validate_feed(...)`, `async fetch_all_feeds(...)`
- `FileInterpreter` — `async interpret(file_bytes, filename, system_prompt) -> str`

All application logic depends only on these protocols. Concrete implementations are wired at startup in `src/lexora/main.py`.

### Package Structure

```
src/
└── lexora/              # top-level installable package
    ├── __init__.py
    ├── app_state.py
    ├── config.py
    ├── models.py
    ├── ports.py
    ├── main.py          # composition root + serve() CLI entry point
    ├── static/          # bundled frontend assets
    ├── feed/
    ├── knowledge/
    └── routers/
```

### Domain Packages

- `src/lexora/knowledge/` — knowledge retrieval domain
  - `chunker.py` — `SimpleChunker`
  - `embedder.py` — `GeminiEmbeddingModel` (async, wraps `google.genai`)
  - `pipeline.py` — `Pipeline` application orchestrator
  - `vector_store.py` — `VectorStore` (ChromaDB)
  - `ask_agent.py` — `PydanticAIAskAgent`
  - `file_interpreter.py` — `GeminiFileInterpreter` (multimodal PDF extraction via Gemini)
  - `loaders/` — `notes.py`, `bookmarks.py`, `sync_state.py`, `models.py`

- `src/lexora/feed/` — RSS/Atom feed domain
  - `models.py` — `Feed`, `Post`, `FeedError`, `DuplicateFeedError`
  - `store.py` — `YamlFeedStore`
  - `fetcher.py` — `HttpFeedFetcher` (httpx + feedparser)
  - `date_range.py` — `parse_date_range()`
  - `service.py` — `FeedService` application orchestrator

### Data Flow

1. **Loaders** (`src/lexora/knowledge/loaders/`) read source data and produce `Document` objects.
   - `notes.py`: Async loader. Traverses `data/notes/` recursively via `rglob`. Supports `.txt` (read directly), `.md` (converted to plain text via mistune), and `.pdf` (delegated to `FileInterpreter`). PDF files are skipped with a warning when no interpreter is available. Incremental sync via `data/notes_sync.json`.
   - `bookmarks.py`: Reads Firefox's `places.sqlite`, fetches each URL's content via `trafilatura`, and produces documents. Incremental sync via `data/bm_sync.json`. The DB is copied to a temp file before reading to avoid lock conflicts with Firefox.
   - `sync_state.py`: Shared helper that persists a `last_sync_timestamp` to a JSON file for both loaders.

2. **Chunker** (`src/lexora/knowledge/chunker.py`): `SimpleChunker` implements `Chunker`. Splits text into overlapping fixed-size character windows.

3. **Embedder** (`src/lexora/knowledge/embedder.py`): `GeminiEmbeddingModel` implements `EmbeddingModel`. Wraps `google.genai`, produces 768-dimensional vectors. `encode` is `async` (uses `asyncio.to_thread` to wrap the synchronous SDK call).

4. **Pipeline** (`src/lexora/knowledge/pipeline.py`): Application-layer orchestrator. Accepts the four knowledge ports via constructor injection. `add_docs` and `search_document_store` are `async` because they `await self._embedding_model.encode(...)`.

5. **Vector Store** (`src/lexora/knowledge/vector_store.py`): `VectorStore` implements `DocumentStore`. Wraps ChromaDB. Point IDs are deterministic `uuid5` hashes of `source:chunk_index:text`, enabling idempotent upserts. Use the factory classmethods:
   - `VectorStore.in_memory()` — ephemeral, for development and tests (appends a UUID suffix to avoid ChromaDB singleton state leakage)
   - `VectorStore.from_path(path)` — persistent local storage (no server required)

6. **Ask Agent** (`src/lexora/knowledge/ask_agent.py`): `PydanticAIAskAgent` implements `AskAgent`. Uses pydantic-ai to run an LLM with structured output (`AskResponse`). Formats retrieved chunks as `SOURCE: <path>\n<text>` blocks and instructs the LLM to answer strictly from the provided context. Provider and model are selected via the `LLM_MODEL` env var; API keys are read from the environment by pydantic-ai automatically.

7. **FeedService** (`src/lexora/feed/service.py`): Application-layer orchestrator for the feed domain. Stores `default_range`, `max_posts_per_feed`, and `timeout` as instance attributes so the router doesn't need settings injection.

8. **Main** (`src/lexora/main.py`): Thin composition root — no route handlers. Constructs all concrete implementations, wraps them in `AppState`, and stores on `app.state`. Includes routers and mounts the static frontend:
   - `app.include_router(knowledge.router)`
   - `app.include_router(feed.router)`
   - `app.include_router(capabilities.router)`
   - `app.include_router(settings.router)`
   - `app.mount("/", StaticFiles(directory=_STATIC_DIR, html=True))`
   - `serve()` function is the CLI entry point for `lexora` command.

### Routers

- `src/lexora/routers/knowledge.py` — `POST /api/v1/query`, `/api/v1/ask`, `/api/v1/reindex`
- `src/lexora/routers/feed.py` — `GET /api/v1/rss`, `PUT /api/v1/rss`
- `src/lexora/routers/capabilities.py` — `GET /api/v1/capabilities`
- `src/lexora/routers/settings.py` — `GET /api/v1/settings`, `PUT /api/v1/settings`, `POST /api/v1/settings/browse-directory`

Each router has its own `get_app_state` dependency function (not shared) to allow independent injection in tests.

#### Reindex behaviour

`POST /api/v1/reindex` is non-blocking and idempotent:
- A module-level `_reindex_task: asyncio.Task | None` sentinel tracks the running task.
- If no task is running, `asyncio.create_task(_run_reindex(...))` is called and `{"status": "started"}` is returned with **202**.
- If a task is already running (`.done()` is `False`), **409** is returned immediately.
- The task completes in the background even if the client disconnects.

### AppState

`src/lexora/app_state.py` — `AppState(NamedTuple)` with:
- `pipeline: Pipeline | None`
- `feed_service: FeedService`
- `file_interpreter: FileInterpreter | None` — wired when `GOOGLE_API_KEY` is set; passed to the notes loader for PDF extraction.

Stored on `app.state.app_state` at startup.

### Key Models

- `src/lexora/knowledge/loaders/models.py` — `Document(content, source)`: raw loaded document.
- `src/lexora/models.py` — `Chunk(text, source, chunk_index)`; `QueryRequest`; `AskResponse(text, sources)` with a validator that rejects answers with empty sources; `NOT_FOUND` sentinel string; `AddFeedRequest`; `AddFeedResponse`.
- `src/lexora/feed/models.py` — `Feed(name, url)`, `Post(feed_name, title, url, published_at)`, `FeedError(feed_name, url, error)`, `DuplicateFeedError`.

### Testing Approach

- Unit tests live in `tests/unit/` and run with no external dependencies.
- `Pipeline` tests use inline **fake** implementations of all four knowledge ports. Fake `encode` is `async def`.
- `VectorStore` tests use `VectorStore.in_memory()`.
- `PydanticAIAskAgent` tests mock pydantic-ai's `Agent` with `AsyncMock` — no real LLM call.
- `GeminiEmbeddingModel` tests mock `google.genai.Client` — no real API call.
- API tests (`tests/unit/test_api.py`) use FastAPI's `TestClient` with `app.dependency_overrides` for `knowledge_get_app_state`, `feed_get_app_state`, `capabilities_get_app_state`, plus `unittest.mock.patch` for loader functions. Patch targets use the full module path: `lexora.routers.knowledge.load_notes`, etc.
- `TestReindexEndpoint` patches `asyncio.create_task` to prevent background task execution; uses an `autouse` fixture to reset `_reindex_task` to `None` between tests.
- `TestRunReindex` tests `_run_reindex` directly by awaiting it; uses `@pytest.mark.anyio`.
- Loader tests use `tmp_path` and SQLite fixtures.
- Feed tests use `FakeFeedStore`, `FakeFeedFetcher`, and `httpx.MockTransport`.
- Eval tests live in `tests/evals/` and require a real LLM API key. Run them separately: `uv run pytest tests/evals/`.

### Configuration

`src/lexora/config.py` defines a `Settings(BaseSettings)` class (via `pydantic-settings`). Settings are read from environment variables or a `.env` file in the project root. The `Settings` instance is created once at module level in `src/lexora/main.py` and injected into route handlers via the `get_settings` FastAPI dependency. The `PUT /api/v1/settings` endpoint writes non-empty values back to `.env`; a server restart is required for changes to take effect.

| Env var | Default | Description |
|---|---|---|
| `HOST` | `0.0.0.0` | Server bind address |
| `PORT` | `9002` | Server port |
| `LOG_LEVEL` | `WARNING` | Log verbosity |
| `GOOGLE_API_KEY` | _(none)_ | **Required.** Used for Gemini embeddings and PDF extraction. |
| `GEMINI_EMBEDDING_MODEL` | `models/text-embedding-004` | Gemini embedding model ID |
| `EMBEDDING_DIMENSION` | `768` | Embedding vector size |
| `CHROMA_PATH` | _(none)_ | ChromaDB persistence directory; omit to use in-memory mode |
| `CHROMA_COLLECTION` | `lexora` | ChromaDB collection name |
| `CHUNK_SIZE` | `500` | Characters per chunk |
| `CHUNK_OVERLAP` | `50` | Overlap between chunks |
| `NOTES_DIR` | `./data/notes` | Root directory for `.txt`, `.md`, `.pdf` notes (recursive) |
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

### Import Convention

All imports use the `lexora.` namespace:

```python
from lexora.knowledge.pipeline import Pipeline   # correct
from knowledge.pipeline import Pipeline          # wrong
```

This is enforced by:
- `pyproject.toml`: `[tool.hatch.build.targets.wheel] packages = ["src/lexora"]` — wheel contains the `lexora` package
- `pyproject.toml`: `[tool.pytest.ini_options] pythonpath = ["src"]` — pytest adds `src/` to `sys.path`

Mock patch strings follow the same convention: `patch("lexora.routers.knowledge.load_notes")`.

### Notes

- Logging uses structlog's keyword-argument style throughout: `logger.info("event_name", key=value)`.
- `docs/MONOLITH_PLAN.md` tracks the consolidation plan and implementation history.
- `docs/LLM_PLAN.md` describes the design and implementation of the `/ask` endpoint.
- The static frontend lives in `src/lexora/static/`. It is a vanilla JS app with no build step.
