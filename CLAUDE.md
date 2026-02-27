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

Lexora-Link is a personal knowledge retrieval API. It ingests documents from two sources (local notes, Firefox bookmarks), embeds them into a vector store, and exposes both a semantic search endpoint and an LLM-powered question-answering endpoint.

### Ports (Abstractions)

`src/ports.py` defines four `Protocol` classes that form the boundary between the application and infrastructure:

- `Chunker` — `chunk(text) -> list[str]`
- `EmbeddingModel` — `encode(text) -> list[float]`
- `DocumentStore` — `ensure_collection()`, `add_chunks(...)`, `search(...)`
- `AskAgent` — `async answer(question, chunks) -> AskResponse`

All application logic depends only on these protocols. Concrete implementations are wired at startup in `api.py`.

### Data Flow

1. **Loaders** (`src/loaders/`) read source data and produce `Document` objects.
   - `notes.py`: Reads `.txt` files from `data/notes/`. Incremental sync via `data/notes_sync.json`.
   - `bookmarks.py`: Reads Firefox's `places.sqlite`, fetches each URL's content via `trafilatura`, and produces documents. Incremental sync via `data/bm_sync.json`. The DB is copied to a temp file before reading to avoid lock conflicts with Firefox.
   - `sync_state.py`: Shared helper that persists a `last_sync_timestamp` to a JSON file for both loaders.

2. **Chunker** (`src/chunker.py`): `SimpleChunker` implements `Chunker`. Splits text into overlapping fixed-size character windows. Default parameters (`chunk_size=500`, `overlap=50`) are defined in `SimpleChunker` and can be overridden at construction time.

3. **Embedder** (`src/embedder.py`): `SentenceTransformerEmbeddingModel` implements `EmbeddingModel`. Wraps `sentence-transformers/all-MiniLM-L6-v2`, produces 384-dimensional `list[float]` vectors.

4. **Pipeline** (`src/pipeline.py`): Application-layer orchestrator. Accepts the four ports via constructor injection and owns the chunk → embed → store flow for indexing, the encode → search flow for querying, and the search → LLM flow for question answering. This is the only class that coordinates across all ports.

5. **Vector Store** (`src/vector_store.py`): `VectorStore` implements `DocumentStore`. Wraps ChromaDB. Point IDs are deterministic `uuid5` hashes of `source:chunk_index:text`, enabling idempotent upserts. Cosine distance. Use the factory classmethods rather than the constructor directly:
   - `VectorStore.in_memory()` — ephemeral, for development and tests
   - `VectorStore.from_path(path)` — persistent local storage (no server required)

6. **Ask Agent** (`src/ask_agent.py`): `PydanticAIAskAgent` implements `AskAgent`. Uses pydantic-ai to run an LLM with structured output (`AskResponse`). Formats retrieved chunks as `SOURCE: <path>\n<text>` blocks and instructs the LLM to answer strictly from the provided context. Provider and model are selected via the `LLM_MODEL` env var; API keys are read from the environment by pydantic-ai automatically.

7. **API** (`api.py`): FastAPI app on port `9002`. Constructs all concrete implementations and wires them into `Pipeline` inside the `lifespan` context, storing the result on `app.state.pipeline`. The `get_pipeline` dependency function exposes it to route handlers via `Depends`. Exposes three endpoints:
   - `POST /api/v1/query` — Semantic search; returns up to 5 ranked `Chunk` objects.
   - `POST /api/v1/ask` — LLM-augmented QA; returns `{"text": "...", "sources": [...]}`.
   - `POST /api/v1/reindex` — Loads notes and bookmarks, delegates to `pipeline.add_docs`. Returns `ReindexResponse(notes_indexed, bookmarks_indexed)`.

### Key Models

- `src/loaders/models.py` — `Document(content, source)`: raw loaded document.
- `src/models.py` — `Chunk(text, source, chunk_index)`; `QueryRequest`; `ReindexResponse`; `AskResponse(text, sources)` with a validator that rejects answers with empty sources; `NOT_FOUND` sentinel string.

### Testing Approach

- Unit tests live in `tests/unit/` and run with no external dependencies.
- `Pipeline` tests use inline **fake** implementations of all four ports.
- `VectorStore` tests use `VectorStore.in_memory()`.
- `PydanticAIAskAgent` tests mock pydantic-ai's `Agent` with `AsyncMock` — no real LLM call.
- API tests (`tests/unit/test_api.py`) use FastAPI's `TestClient` with `app.dependency_overrides[get_pipeline]` to inject a `FakePipeline` and `app.dependency_overrides[get_settings]` to inject a default `Settings()`, plus `unittest.mock.patch` for the loader functions.
- Loader tests use `tmp_path` and SQLite fixtures.
- Eval tests live in `tests/evals/` and require a real LLM API key. Run them separately: `uv run pytest tests/evals/`.

### Configuration

`src/config.py` defines a `Settings(BaseSettings)` class (via `pydantic-settings`). Settings are read from environment variables or a `.env` file in the project root. The `Settings` instance is created once at module level in `api.py` and injected into route handlers via the `get_settings` FastAPI dependency.

| Env var | Default | Description |
|---|---|---|
| `HOST` | `0.0.0.0` | Server bind address |
| `PORT` | `9002` | Server port |
| `LOG_LEVEL` | `WARNING` | Log verbosity |
| `CHROMA_PATH` | _(none)_ | ChromaDB persistence directory; omit to use in-memory mode |
| `CHROMA_COLLECTION` | `lexora` | ChromaDB collection name |
| `EMBEDDING_DIMENSION` | `384` | Embedding vector size |
| `CHUNK_SIZE` | `500` | Characters per chunk |
| `CHUNK_OVERLAP` | `50` | Overlap between chunks |
| `EMBEDDING_MODEL_NAME` | `sentence-transformers/all-MiniLM-L6-v2` | HuggingFace model ID |
| `NOTES_DIR` | `./data/notes` | Directory of `.txt` notes |
| `NOTES_SYNC_STATE_PATH` | `./data/notes_sync.json` | Notes incremental sync state |
| `BOOKMARKS_PROFILE_PATH` | _(none)_ | Firefox profile path; omit to auto-detect |
| `BOOKMARKS_SYNC_STATE_PATH` | `./data/bm_sync.json` | Bookmarks incremental sync state |
| `BOOKMARKS_FETCH_TIMEOUT` | `15` | HTTP timeout per bookmark (seconds) |
| `BOOKMARKS_MAX_CONTENT_LENGTH` | `50000` | Max characters extracted per page |
| `LLM_MODEL` | `google-gla:gemini-2.0-flash` | pydantic-ai model string for `/ask` |
| `GEMINI_API_KEY` | _(none)_ | Gemini API key (read by pydantic-ai) |
| `OPENAI_API_KEY` | _(none)_ | OpenAI API key (read by pydantic-ai) |
| `ANTHROPIC_API_KEY` | _(none)_ | Anthropic API key (read by pydantic-ai) |

### Notes

- Logging uses structlog's keyword-argument style throughout: `logger.info("event_name", key=value)`.
- `docs/PLAN.md` tracks the original architectural critique and the remediation history.
- `docs/LLM_PLAN.md` describes the design and implementation of the `/ask` endpoint.
