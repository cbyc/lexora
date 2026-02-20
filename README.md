# Lexora Feed

A lightweight RSS/Atom feed aggregator with a REST API. Fetches posts from multiple feeds in parallel and returns them filtered by date range.

## Running

**Locally:**
```bash
go run .
```

**With Make (supports env var overrides):**
```bash
make run-local
```

**Docker:**
```bash
make run-container
```

The server starts on `localhost:9001` by default. Override via env vars:

```bash
RSS_PORT=8080 RSS_MAX_POSTS_PER_FEED=100 make run-local
```

## API

```
GET /rss?range=last_month       # fetch posts (preset range)
GET /rss?from=2026-01-01T00:00:00Z&to=2026-02-01T00:00:00Z  # explicit range
PUT /rss                        # add a feed
```

Valid ranges: `today`, `last_week`, `last_month`, `last_3_months`, `last_6_months`, `last_year`.

`PUT` body:
```json
{ "name": "Go Blog", "url": "https://go.dev/blog/feed.atom" }
```

## Configuration

All settings can be overridden via environment variables. A `config.yaml` file in the working directory is also supported, but env vars take precedence.

| Variable | Default | Description |
|---|---|---|
| `RSS_HOST` | `localhost` | Host address the server binds to |
| `RSS_PORT` | `9001` | Port the server listens on |
| `RSS_DATA_DIR` | `./data` | Directory for `feeds.yaml` and log files |
| `RSS_MAX_POSTS_PER_FEED` | `50` | Maximum number of posts fetched per feed |
| `RSS_FETCH_TIMEOUT_SEC` | `10` | Per-feed HTTP fetch timeout in seconds |
| `RSS_DEFAULT_RANGE` | `last_month` | Date range used when no `range` param is given |

## Testing

```bash
# Unit tests
go test ./...

# Single test
go test ./api/ -run TestGetRSS_Success

# Integration tests
go test -tags integration ./...
```
