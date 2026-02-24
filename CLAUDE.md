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
uv run pytest tests/unit/test_vector_store.py

# Run a specific test
uv run pytest tests/unit/test_vector_store.py::TestVectorStore::test_add_and_search

# Lint
uv run ruff check .

# Format
uv run ruff format .
```

## Architecture

Lexora-Link is a personal knowledge retrieval API. It ingests documents from two sources (local notes, Firefox bookmarks), embeds them into a vector store, and exposes a semantic search endpoint.

### Data Flow

1. **Loaders** (`src/loaders/`) read source data and produce `Document` objects.
   - `notes.py`: Reads `.txt` files from `data/notes/`. Incremental sync via `data/notes_sync.json`.
   - `bookmarks.py`: Reads Firefox's `places.sqlite`, fetches each URL's content via `trafilatura`, and produces documents. Incremental sync via `data/bm_sync.json`. The DB is copied to a temp file before reading to avoid lock conflicts with Firefox.
   - `sync_state.py`: Shared helper that persists a `last_sync_timestamp` to a JSON file for both loaders.

2. **Chunker** (`src/chunker.py`): Splits document content into overlapping fixed-size character chunks (`chunk_size=500`, `overlap=50` as called from `VectorStore.add_docs`).

3. **Vector Store** (`src/vector_store.py`): Wraps Qdrant. Defaults to in-memory mode (`use_memory=True`) for development/testing. Point IDs are deterministic `uuid5` hashes of `source:chunk_index:text`, enabling idempotent upserts. The embedding model is `sentence-transformers/all-MiniLM-L6-v2` (384-dimensional vectors, cosine distance).

4. **API** (`api.py`): FastAPI app on port `9002`.
   - `POST /api/v1/query` — Accepts `{"question": "..."}`, embeds it, and returns matching `Chunk` objects. Max question length: 1024 chars.
   - `POST /api/v1/reindex` — Triggers a full reload of notes + bookmarks into the vector store.

### Key Models

- `src/loaders/models.py` — `Document(content, source)`: raw loaded document.
- `src/models.py` — `Chunk(text, source, chunk_index)`: a chunked piece of a document; also `QueryRequest`.
- Root `models.py` is an unused duplicate of `src/models.py`.

### Notes

- `LOGLEVEL` env var controls log verbosity (default: `WARNING`).
- `VectorStore` is initialized once at startup via FastAPI's `lifespan` context and held as a module-level global.
- Tests use in-memory Qdrant and `tmp_path` fixtures — no external services needed.
