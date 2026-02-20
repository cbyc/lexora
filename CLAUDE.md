# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Lexora Feed is a lightweight Go RSS/Atom feed aggregation service. It fetches posts from multiple feeds in parallel, stores the feed list in YAML, and exposes a REST API for querying posts with date range filtering. Uses pure Go stdlib for HTTP (no web framework), gofeed for parsing, and viper for configuration.

## Commands

```bash
# Run locally
go run .

# Build binary
go build -o lexora-feed

# Unit tests
go test ./...

# Run a single test
go test ./api/ -run TestGetRSS_Success

# Integration tests (spin up a real server internally — no running server needed)
go test -tags integration ./...

# Makefile targets (env vars default via ?= — override by setting them beforehand)
make run-local        # runs go run . with env vars
make build-image      # builds Docker image
make run-container    # builds image and runs container on :9001
```

## Architecture

**Entry point:** [main.go](main.go) — loads config, initializes logging, seeds feeds file, registers routes, starts HTTP server with graceful shutdown (SIGINT/SIGTERM).

**Modules:**
- [config/](config/) — Viper config cascade: defaults → `config.yaml` → env vars (prefix `RSS_`, e.g. `RSS_PORT=8080`). Config file errors fall back to defaults rather than failing.
- [feed/](feed/) — Feed fetching and storage
  - [fetcher.go](feed/fetcher.go) — Parallel fetching via goroutines+WaitGroup; per-feed context timeout. Posts sorted newest-first. Feed name overridden with user-configured name (not the feed's own title).
  - [store.go](feed/store.go) — YAML-based feed list (path from `cfg.DataFile`), duplicate detection by URL.
- [api/](api/) — Handlers registered on `http.ServeMux`
  - [rss.go](api/rss.go) — `GET /rss` (fetch + date filter), `PUT /rss` (validate feed URL before adding). All routes dispatched via a single `mux.HandleFunc("/rss", ...)`.
  - [cors.go](api/cors.go) — CORS middleware wrapping the mux (allow all origins, GET/PUT/OPTIONS).
- [logging/](logging/) — Structured `slog` loggers writing to `{dataDir}/errors.log`, `{dataDir}/warnings.log`, `{dataDir}/info.log`.

**API:**
- `GET /rss?range=last_month` — Preset ranges: `today`, `last_week`, `last_month`, `last_3_months`, `last_6_months`, `last_year`. Explicit `from`/`to` RFC3339 params take precedence over `range`. When all feeds fail, returns 200 with empty array and `X-Feed-Errors: all-feeds-failed` header.
- `PUT /rss` — Body: `{"name": "...", "url": "..."}`. Validates the URL is a real feed before saving. Returns 201/400/409/422.

**Data:** Feed list at `data/feeds.yaml`. Logs in `data/` (same level, not a subdirectory).

## Configuration Defaults

| Key | Default | Env var |
|-----|---------|---------|
| Host | `localhost` | `RSS_HOST` |
| Port | `9001` | `RSS_PORT` |
| DataFile | `./data/feeds.yaml` | `RSS_DATA_FILE` |
| MaxPostsPerFeed | `50` | `RSS_MAX_POSTS_PER_FEED` |
| FetchTimeoutSec | `10` | `RSS_FETCH_TIMEOUT_SEC` |
| DefaultRange | `last_month` | `RSS_DEFAULT_RANGE` |

The Makefile uses `?=` for all vars, so any env var set in the shell before running `make` will be respected.
