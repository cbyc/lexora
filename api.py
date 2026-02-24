import os
import structlog
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sentence_transformers import SentenceTransformer

from src.vector_store import VectorStore
from src.loaders.notes import load_notes
from src.loaders.bookmarks import load_bookmarks
from src.models import QueryRequest

MAX_QUERY_LENGTH = 1024


log_level = os.environ.get("LOGLEVEL", "WARNING").upper()
logging.basicConfig(level=log_level)
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global embedding_model, vectorstore
    embedding_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    vectorstore = VectorStore()
    yield


app = FastAPI(title="Lexora Mind API", lifespan=lifespan)


def _configure_cors():
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )


_configure_cors()


@app.post("/api/v1/query")
async def query(request: QueryRequest):
    if len(request.question) > MAX_QUERY_LENGTH:
        return JSONResponse(
            status_code=400,
            content={
                "error": "bad_request",
                "detail": f"Question exceeds maximum length of {MAX_QUERY_LENGTH} characters.",
            },
        )

    question_embedding = embedding_model.encode(request.question)
    result = vectorstore.search(question_embedding)

    return result


@app.post("/api/v1/reindex")
async def reindex():
    vectorstore.ensure_collection()

    notes = load_notes("./data/notes", "./data/notes_sync.json")
    logger.info(f"{len(notes)} notes found.")

    bookmarks = load_bookmarks("./data/ff/places.sqlite", "./data/bm_sync.json")
    logger.info(f"{len(bookmarks)} bookmarks found.")

    docs = notes + bookmarks
    vectorstore.add_docs(docs, embedding_model)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9002)
