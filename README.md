# Lexora-Link

A personal knowledge retrieval API. Ingests documents from local notes and Firefox bookmarks, embeds them into a vector store, and exposes a semantic search endpoint.

## Setup

Requires Python 3.13+ and [`uv`](https://docs.astral.sh/uv/).

```bash
uv sync
```

## Configuration

All settings are read from environment variables or a `.env` file in the project root. Every setting has a default so the server starts with no configuration needed.

```bash
# .env (all values shown are their defaults — only set what you want to change)
LOG_LEVEL=WARNING
HOST=0.0.0.0
PORT=9002

# Vector store — omit QDRANT_URL to use ephemeral in-memory mode
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION=lexora

# Paths
NOTES_DIR=./data/notes
NOTES_SYNC_STATE_PATH=./data/notes_sync.json
BOOKMARKS_PROFILE_PATH=        # leave empty to auto-detect Firefox profile
BOOKMARKS_SYNC_STATE_PATH=./data/bm_sync.json

# Tuning
CHUNK_SIZE=500
CHUNK_OVERLAP=50
BOOKMARKS_FETCH_TIMEOUT=15
BOOKMARKS_MAX_CONTENT_LENGTH=50000
```

## Data sources

Place your data in the following locations (or configure different paths via env vars):

| Source | Default path |
|---|---|
| Plain-text notes | `data/notes/*.txt` |
| Firefox profile | auto-detected, or set `BOOKMARKS_PROFILE_PATH` |

Incremental sync state is persisted to `data/notes_sync.json` and `data/bm_sync.json`. Delete these files to force a full reindex.

## Running

```bash
uv run python api.py
```

The API starts on port `9002` by default.

## API

### `POST /api/v1/reindex`

Loads notes and bookmarks, chunks and embeds them, and upserts into the vector store.

```bash
curl -X POST http://localhost:9002/api/v1/reindex
```

```json
{"notes_indexed": 4, "bookmarks_indexed": 12}
```

### `POST /api/v1/query`

Semantic search over indexed documents.

```bash
curl -X POST http://localhost:9002/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"question": "sourdough starter hydration"}'
```

```json
[
  {"text": "...", "source": "data/notes/recipe_sourdough.txt", "chunk_index": 0},
  ...
]
```

`question` must be between 1 and 1024 characters. Returns up to 5 ranked chunks.

## Development

```bash
# Run tests
uv run pytest

# Lint / format
uv run ruff check .
uv run ruff format .
```

The vector store runs in-memory by default — data is lost on restart. Call `/api/v1/reindex` each time the server starts, or set `QDRANT_URL` to persist to a running Qdrant server.
