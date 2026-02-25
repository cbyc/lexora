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

Lexora-Link is a personal knowledge retrieval API. It ingests documents from two sources (local notes, Firefox bookmarks), embeds them into a vector store, and exposes a semantic search endpoint.

### Ports (Abstractions)

`src/ports.py` defines three `Protocol` classes that form the boundary between the application and infrastructure:

- `Chunker` — `chunk(text) -> list[str]`
- `EmbeddingModel` — `encode(text) -> list[float]`
- `DocumentStore` — `ensure_collection()`, `add_chunks(...)`, `search(...)`

All application logic depends only on these protocols. Concrete implementations are wired at startup in `api.py`.

### Data Flow

1. **Loaders** (`src/loaders/`) read source data and produce `Document` objects.
   - `notes.py`: Reads `.txt` files from `data/notes/`. Incremental sync via `data/notes_sync.json`.
   - `bookmarks.py`: Reads Firefox's `places.sqlite`, fetches each URL's content via `trafilatura`, and produces documents. Incremental sync via `data/bm_sync.json`. The DB is copied to a temp file before reading to avoid lock conflicts with Firefox.
   - `sync_state.py`: Shared helper that persists a `last_sync_timestamp` to a JSON file for both loaders.

2. **Chunker** (`src/chunker.py`): `SimpleChunker` implements `Chunker`. Splits text into overlapping fixed-size character windows. Parameters (`chunk_size=500`, `overlap=50`) are set at construction time in `api.py`.

3. **Embedder** (`src/embedder.py`): `SentenceTransformerEmbeddingModel` implements `EmbeddingModel`. Wraps `sentence-transformers/all-MiniLM-L6-v2`, produces 384-dimensional `list[float]` vectors.

4. **Pipeline** (`src/pipeline.py`): Application-layer orchestrator. Accepts the three ports via constructor injection and owns the chunk → embed → store flow for indexing, and the encode → search flow for querying. This is the only class that coordinates across all three ports.

5. **Vector Store** (`src/vector_store.py`): `VectorStore` implements `DocumentStore`. Wraps Qdrant. Defaults to in-memory mode (`use_memory=True`). Point IDs are deterministic `uuid5` hashes of `source:chunk_index:text`, enabling idempotent upserts. Cosine distance.

6. **API** (`api.py`): FastAPI app on port `9002`. Constructs all concrete implementations and wires them into `Pipeline` inside the `lifespan` context. Exposes two endpoints:
   - `POST /api/v1/query` — Accepts `{"question": "..."}`, delegates to `pipeline.search_document_store`. Max question length: 1024 chars.
   - `POST /api/v1/reindex` — Loads notes and bookmarks, delegates to `pipeline.add_docs`.

### Key Models

- `src/loaders/models.py` — `Document(content, source)`: raw loaded document.
- `src/models.py` — `Chunk(text, source, chunk_index)`: a chunked piece of a document; also `QueryRequest`.

### Testing Approach

- `Pipeline` tests use inline **fake** implementations of the three ports — no real model or Qdrant instance needed.
- `VectorStore` tests use Qdrant's in-memory mode.
- Loader tests use `tmp_path` and SQLite fixtures.
- No external services are required to run the full test suite.

### Notes

- `LOGLEVEL` env var controls log verbosity (default: `WARNING`).
- `pipeline` is held as a module-level global in `api.py`, initialised once in `lifespan`.
- `docs/PLAN.md` tracks the full architectural critique and the remaining remediation items.
