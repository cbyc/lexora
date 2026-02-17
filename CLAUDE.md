# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Lexora Feed is a lightweight Go RSS/Atom feed aggregation service. It fetches posts from multiple feeds in parallel, stores the feed list in YAML, and exposes a REST API for querying posts with date range filtering. Uses pure Go stdlib for HTTP (no web framework), gofeed for parsing, and viper for configuration.

## Commands

```bash
# Run
go run .

# Build
go build -o lexora-feed

# Unit tests
go test ./...

# Integration tests (require running server)
go test -tags integration ./...
```

## Architecture

**Entry point:** `main.go` — loads config, initializes logging, seeds feeds file, registers routes, starts HTTP server with graceful shutdown (SIGINT/SIGTERM).

**Modules:**
- `config/` — Configuration loaded via viper with cascade: defaults → `config.yaml` → env vars (prefix `RSS_`, e.g. `RSS_PORT=8080`)
- `feed/` — Feed fetching and storage
  - `fetcher.go` — Parallel feed fetching with goroutines+WaitGroup, context-aware timeouts
  - `store.go` — YAML-based feed list management (`data/feeds.yaml`), duplicate detection, seed data
- `api/` — HTTP handlers registered on `http.ServeMux`
  - `rss.go` — `GET /rss` (fetch posts with range filtering), `PUT /rss` (add new feed with validation)
  - `cors.go` — CORS middleware (allow all origins, GET/PUT/OPTIONS)
- `logging/` — Structured slog loggers writing to separate files (`data/logs/{errors,warnings,info}.log`)

**API:**
- `GET /rss?range=last_month` — Preset ranges: today, last_week, last_month, last_3_months, last_6_months, last_year. Also supports explicit `from`/`to` RFC3339 timestamps.
- `PUT /rss` — Body: `{"name": "...", "url": "..."}`. Returns 201/400/409/422.

**Data:** Feed list stored in `data/feeds.yaml`. Logs in `data/logs/`.

## Configuration Defaults

Host: `localhost`, Port: `9001`, DataDir: `./data`, MaxPostsPerFeed: 50, FetchTimeoutSec: 10, DefaultRange: `last_month`
