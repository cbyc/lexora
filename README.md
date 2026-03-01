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

Settings can also be changed at runtime via the **Settings** page in the web UI, which persists updates to `.env`. A server restart is required for changes to take effect.

## Data sources

| Source | Supported formats | Default path |
|---|---|---|
| Notes | `.txt`, `.md`, `.pdf` (recursive) | `data/notes/` |
| Firefox bookmarks | page content via trafilatura | auto-detected, or set `BOOKMARKS_PROFILE_PATH` |
| RSS/Atom feeds | managed via UI or `PUT /api/v1/rss` | stored in `data/feeds.yaml` |

The notes loader traverses subdirectories. Markdown files are converted to plain text; PDF files are extracted via the Gemini multimodal API (requires `GOOGLE_API_KEY`). PDFs are skipped with a warning when the API key is not configured.

Incremental sync state is persisted to `data/notes_sync.json` and `data/bm_sync.json`. Delete these files to force a full reindex.

## Running

```bash
uv run python api.py
```

The server starts on port `9002` by default and serves the web frontend at `/`.

## API

### Knowledge

#### `POST /api/v1/reindex`

Starts a background reindex of notes and bookmarks (chunking, embedding, upsert into the vector store). Returns immediately — the reindex continues even if the client disconnects.

```bash
curl -X POST http://localhost:9002/api/v1/reindex
```

```json
{"status": "started"}
```

Returns `202 Accepted` on success. Returns `409 Conflict` if a reindex is already running. Returns `503` if `GOOGLE_API_KEY` is not configured.

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

#### `GET /api/v1/capabilities`

Reports which optional features are active.

```bash
curl http://localhost:9002/api/v1/capabilities
```

```json
{"mind_enabled": true, "feed_enabled": true}
```

`mind_enabled` is `false` when `GOOGLE_API_KEY` is not set.

### Settings

#### `GET /api/v1/settings`

Returns the current runtime configuration.

```bash
curl http://localhost:9002/api/v1/settings
```

```json
{
  "google_api_key_set": true,
  "notes_dir": "./data/notes",
  "bookmarks_profile_path": null
}
```

#### `PUT /api/v1/settings`

Persists non-empty fields to the `.env` file. A server restart is required for changes to take effect.

```bash
curl -X PUT http://localhost:9002/api/v1/settings \
  -H "Content-Type: application/json" \
  -d '{"notes_dir": "/home/user/notes"}'
```

```json
{"saved": true, "restart_required": true}
```

Only the fields you supply are written; omitted or empty fields are left unchanged.

#### `POST /api/v1/settings/browse-directory`

Opens a native macOS folder picker and returns the chosen path. Returns `{"path": null}` on non-macOS platforms or if the dialog is cancelled.

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

The vector store runs in-memory by default — data is lost on restart. Call `POST /api/v1/reindex` each time the server starts (or use the Reindex button in Settings), or set `CHROMA_PATH` to a directory for persistent local storage.

## License

MIT — see [LICENSE.txt](LICENSE.txt).
