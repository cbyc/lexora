import os
import structlog
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware

from src.vector_store import VectorStore
from src.loaders.notes import load_notes
from src.loaders.bookmarks import load_bookmarks
from src.models import QueryRequest, ReindexResponse
from src.chunker import SimpleChunker
from src.pipeline import Pipeline
from src.embedder import SentenceTransformerEmbeddingModel


log_level = os.environ.get("LOGLEVEL", "WARNING").upper()
logging.basicConfig(level=log_level)
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    chunker = SimpleChunker()
    embedding_model = SentenceTransformerEmbeddingModel()
    vectorstore = VectorStore.in_memory()
    vectorstore.ensure_collection()

    app.state.pipeline = Pipeline(chunker, embedding_model, vectorstore)
    yield


app = FastAPI(title="Lexora Mind API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_pipeline(request: Request) -> Pipeline:
    return request.app.state.pipeline


@app.post("/api/v1/query")
async def query(request: QueryRequest, pipeline: Pipeline = Depends(get_pipeline)):
    result = pipeline.search_document_store(request.question)
    return result


@app.post("/api/v1/reindex")
async def reindex(pipeline: Pipeline = Depends(get_pipeline)):
    notes = load_notes("./data/notes", "./data/notes_sync.json")
    logger.info("notes_loaded", count=len(notes))

    bookmarks = load_bookmarks("./data/ff/places.sqlite", "./data/bm_sync.json")
    logger.info("bookmarks_found", count=len(bookmarks))

    docs = notes + bookmarks
    pipeline.add_docs(docs)

    return ReindexResponse(notes_indexed=len(notes), bookmarks_indexed=len(bookmarks))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9002)
