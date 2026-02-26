# LLM
LLM_MODEL                    ?= google-gla:gemini-2.0-flash
# Embeddings
EMBEDDING_MODEL_NAME         ?= sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DIMENSION          ?= 384
HF_HUB_OFFLINE               ?= 1
# Qdrant
QDRANT_URL                   ?= http://localhost:6333
QDRANT_COLLECTION            ?= lexora
# Chunking
CHUNK_SIZE                   ?= 500
CHUNK_OVERLAP                ?= 50
# Data
NOTES_DIR                    ?= ./data/notes
NOTES_SYNC_STATE_PATH        ?= ./data/notes_sync.json
BOOKMARKS_SYNC_STATE_PATH    ?= ./data/bm_sync.json
BOOKMARKS_FETCH_TIMEOUT      ?= 15
BOOKMARKS_MAX_CONTENT_LENGTH ?= 50000
# API
HOST                         ?= 0.0.0.0
PORT                         ?= 9002

# Collected env flags used by both run targets
ENVFLAGS = \
	LLM_MODEL=$(LLM_MODEL) \
	EMBEDDING_MODEL_NAME=$(EMBEDDING_MODEL_NAME) \
	EMBEDDING_DIMENSION=$(EMBEDDING_DIMENSION) \
	QDRANT_URL="" \
	QDRANT_COLLECTION=$(QDRANT_COLLECTION) \
	CHUNK_SIZE=$(CHUNK_SIZE) \
	CHUNK_OVERLAP=$(CHUNK_OVERLAP) \
	NOTES_DIR=$(NOTES_DIR) \
	NOTES_SYNC_STATE_PATH=$(NOTES_SYNC_STATE_PATH) \
	BOOKMARKS_SYNC_STATE_PATH=$(BOOKMARKS_SYNC_STATE_PATH) \
	BOOKMARKS_FETCH_TIMEOUT=$(BOOKMARKS_FETCH_TIMEOUT) \
	BOOKMARKS_MAX_CONTENT_LENGTH=$(BOOKMARKS_MAX_CONTENT_LENGTH) \
	HOST=$(HOST) \
	PORT=$(PORT)

.PHONY: build run-image run test evals lint

## Build a minimal Docker image for the API server
build:
	docker build -t lexora-link .

## Run the API server via Docker (provider API key passed from environment)
run-image:
	docker run --rm -d \
		-p $(PORT):80 \
		-v $(PWD)/data:/app/data \
		$(foreach v,$(ENVFLAGS),-e $(v)) \
		-e GOOGLE_API_KEY=$(GOOGLE_API_KEY) \
		lexora-link

## Run the API server on the local machine
run:
	$(ENVFLAGS) HF_HUB_OFFLINE=$(HF_HUB_OFFLINE) \
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
