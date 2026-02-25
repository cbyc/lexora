# Lexora-Link

A personal knowledge retrieval API. Ingests documents from local notes and Firefox bookmarks, embeds them into a vector store, and exposes a semantic search endpoint.

## Setup

Requires Python 3.13+ and [`uv`](https://docs.astral.sh/uv/).

```bash
uv sync
```

## Data sources

Place your data in the following locations before running a reindex:

| Source | Path |
|---|---|
| Plain-text notes | `data/notes/*.txt` |
| Firefox bookmarks DB | `data/ff/places.sqlite` |

Incremental sync state is persisted to `data/notes_sync.json` and `data/bm_sync.json`. Delete these files to force a full reindex.

## Running

```bash
uv run python api.py
```

The API starts on port `9002`.

Set `LOGLEVEL=INFO` (or `DEBUG`) to see structured log output.

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

The vector store runs in-memory by default — data is lost on restart. Call `/api/v1/reindex` each time the server starts, or wire `VectorStore.from_url(url)` in `api.py` to persist to a Qdrant server.
