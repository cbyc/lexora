# Lexora-Link

A personal knowledge and feed aggregation server. Ingests documents from local notes and Firefox bookmarks, embeds them into a vector store, and exposes semantic search, LLM-powered question answering, and an RSS feed reader — all served from a single process including a web frontend.

## Setup

Requires Python 3.13+ and [`uv`](https://docs.astral.sh/uv/).

```bash
uv sync
```

## Configuration

All settings are read from environment variables or a `.env` file in the project root.

```bash
# .env (all values shown are their defaults — only set what you want to change)
LOG_LEVEL=WARNING
HOST=0.0.0.0
PORT=9002

# Embeddings — GOOGLE_API_KEY is required
GOOGLE_API_KEY=                        # required
GEMINI_EMBEDDING_MODEL=models/text-embedding-004
EMBEDDING_DIMENSION=768

# Vector store — omit CHROMA_PATH to use ephemeral in-memory mode
CHROMA_PATH=./data/chroma
CHROMA_COLLECTION=lexora

# Knowledge sources
NOTES_DIR=./data/notes
NOTES_SYNC_STATE_PATH=./data/notes_sync.json
BOOKMARKS_PROFILE_PATH=               # leave empty to auto-detect Firefox profile
BOOKMARKS_SYNC_STATE_PATH=./data/bm_sync.json
BOOKMARKS_FETCH_TIMEOUT=15
BOOKMARKS_MAX_CONTENT_LENGTH=50000

# Chunking
CHUNK_SIZE=500
CHUNK_OVERLAP=50

# LLM — provider API key is read from the environment by pydantic-ai
LLM_MODEL=google-gla:gemini-2.0-flash

# Feed reader
FEED_DATA_FILE=./data/feeds.yaml
FEED_MAX_POSTS_PER_FEED=50
FEED_FETCH_TIMEOUT_SEC=10
FEED_DEFAULT_RANGE=last_month
```

## Data sources

| Source | Default path |
|---|---|
| Plain-text notes | `data/notes/*.txt` |
| Firefox profile | auto-detected, or set `BOOKMARKS_PROFILE_PATH` |
| RSS/Atom feeds | managed via `PUT /api/v1/rss`; stored in `data/feeds.yaml` |

Incremental sync state is persisted to `data/notes_sync.json` and `data/bm_sync.json`. Delete these files to force a full reindex.

## Running

```bash
uv run python api.py
```

The server starts on port `9002` by default and serves the web frontend at `/`.

## API

### Knowledge

#### `POST /api/v1/reindex`

Loads notes and bookmarks, chunks and embeds them, and upserts into the vector store.

```bash
curl -X POST http://localhost:9002/api/v1/reindex
```

```json
{"notes_indexed": 4, "bookmarks_indexed": 12}
```

#### `POST /api/v1/query`

Semantic search over indexed documents.

```bash
curl -X POST http://localhost:9002/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"question": "sourdough starter hydration"}'
```

```json
[
  {"text": "...", "source": "data/notes/recipe_sourdough.txt", "chunk_index": 0}
]
```

`question` must be between 1 and 1024 characters. Returns up to 5 ranked chunks.

#### `POST /api/v1/ask`

LLM-augmented question answering. Retrieves relevant chunks, passes them to the configured LLM, and returns a grounded answer with source citations. The LLM answers strictly from the retrieved context — if the context does not contain a relevant answer, it returns a not-found response.

```bash
curl -X POST http://localhost:9002/api/v1/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "sourdough starter hydration"}'
```

```json
{
  "text": "A 100% hydration starter uses equal weights of flour and water ...",
  "sources": ["data/notes/recipe_sourdough.txt"]
}
```

If the context does not contain a relevant answer:

```json
{"text": "I couldn't find relevant information.", "sources": []}
```

`question` must be between 1 and 1024 characters.

### Feed Reader

#### `GET /api/v1/rss`

Fetches posts from all configured feeds.

```bash
curl http://localhost:9002/api/v1/rss?range=last_week
```

```json
{
  "posts": [
    {
      "feed_name": "Hacker News",
      "title": "...",
      "url": "https://...",
      "published_at": "2026-02-20T10:00:00Z"
    }
  ],
  "errors": []
}
```

Query params:
- `range` — preset: `today`, `last_week`, `last_month` (default), `last_3_months`, `last_6_months`, `last_year`, or omit for all time
- `from` / `to` — explicit ISO 8601 date range (overrides `range`)

#### `PUT /api/v1/rss`

Add a new RSS or Atom feed.

```bash
curl -X PUT http://localhost:9002/api/v1/rss \
  -H "Content-Type: application/json" \
  -d '{"name": "Hacker News", "url": "https://news.ycombinator.com/rss"}'
```

Returns `201` on success, `409` if the URL already exists, `400` if the URL is not a valid feed.

## Development

```bash
# Run unit tests (no external dependencies required)
uv run pytest

# Run LLM evals (requires a provider API key)
LLM_MODEL=google-gla:gemini-2.0-flash GOOGLE_API_KEY=... uv run pytest tests/evals/

# Lint / format
uv run ruff check .
uv run ruff format .
```

The vector store runs in-memory by default — data is lost on restart. Call `/api/v1/reindex` each time the server starts, or set `CHROMA_PATH` to a directory for persistent local storage.
