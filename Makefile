# LLM
LLM_MODEL                    ?= google-gla:gemini-2.0-flash
# Embeddings
GEMINI_EMBEDDING_MODEL       ?= models/text-embedding-004
EMBEDDING_DIMENSION          ?= 768
# ChromaDB
CHROMA_PATH                  ?= ./data/chroma
CHROMA_COLLECTION            ?= lexora
# Chunking
CHUNK_SIZE                   ?= 500
CHUNK_OVERLAP                ?= 50
# Data
NOTES_DIR                    ?= ./data/notes
NOTES_SYNC_STATE_PATH        ?= ./data/notes_sync.json
BOOKMARKS_SYNC_STATE_PATH    ?= ./data/bm_sync.json
BOOKMARKS_FETCH_TIMEOUT      ?= 15
BOOKMARKS_MAX_CONTENT_LENGTH ?= 50000
# Feed
FEED_DATA_FILE               ?= ./data/feeds.yaml
FEED_MAX_POSTS_PER_FEED      ?= 50
FEED_FETCH_TIMEOUT_SEC       ?= 10
FEED_DEFAULT_RANGE           ?= last_month
# API
HOST                         ?= 0.0.0.0
PORT                         ?= 9002

# Collected env flags used by the run target
ENVFLAGS = \
	LLM_MODEL=$(LLM_MODEL) \
	GEMINI_EMBEDDING_MODEL=$(GEMINI_EMBEDDING_MODEL) \
	EMBEDDING_DIMENSION=$(EMBEDDING_DIMENSION) \
	CHROMA_PATH="" \
	CHROMA_COLLECTION=$(CHROMA_COLLECTION) \
	CHUNK_SIZE=$(CHUNK_SIZE) \
	CHUNK_OVERLAP=$(CHUNK_OVERLAP) \
	NOTES_DIR=$(NOTES_DIR) \
	NOTES_SYNC_STATE_PATH=$(NOTES_SYNC_STATE_PATH) \
	BOOKMARKS_SYNC_STATE_PATH=$(BOOKMARKS_SYNC_STATE_PATH) \
	BOOKMARKS_FETCH_TIMEOUT=$(BOOKMARKS_FETCH_TIMEOUT) \
	BOOKMARKS_MAX_CONTENT_LENGTH=$(BOOKMARKS_MAX_CONTENT_LENGTH) \
	FEED_DATA_FILE=$(FEED_DATA_FILE) \
	FEED_MAX_POSTS_PER_FEED=$(FEED_MAX_POSTS_PER_FEED) \
	FEED_FETCH_TIMEOUT_SEC=$(FEED_FETCH_TIMEOUT_SEC) \
	FEED_DEFAULT_RANGE=$(FEED_DEFAULT_RANGE) \
	HOST=$(HOST) \
	PORT=$(PORT)

.PHONY: run test evals lint

## Run the API server on the local machine
run:
	$(ENVFLAGS) \
		GOOGLE_API_KEY=$(GOOGLE_API_KEY) \
		uv run uvicorn api:app --host $(HOST) --port $(PORT)

## Run unit tests
test:
	uv run pytest

## Run LLM eval tests (requires a provider API key)
evals:
	LLM_MODEL=$(LLM_MODEL) \
		GOOGLE_API_KEY=$(GOOGLE_API_KEY) \
		uv run pytest tests/evals/

## Lint and format
lint:
	uv run ruff check . && uv run ruff format .
