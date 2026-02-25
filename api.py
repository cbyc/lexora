import logging
from contextlib import asynccontextmanager

import structlog
import uvicorn
from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware

from src.config import Settings
from src.vector_store import VectorStore
from src.loaders.notes import load_notes
from src.loaders.bookmarks import load_bookmarks
from src.models import QueryRequest, ReindexResponse
from src.chunker import SimpleChunker
from src.pipeline import Pipeline
from src.embedder import SentenceTransformerEmbeddingModel

settings = Settings()

logging.basicConfig(level=settings.log_level.upper())
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    chunker = SimpleChunker(settings.chunk_size, settings.chunk_overlap)
    embedding_model = SentenceTransformerEmbeddingModel(settings.embedding_model_name)

    if settings.qdrant_url:
        vectorstore = VectorStore.from_url(
            settings.qdrant_url,
            settings.qdrant_collection,
            settings.embedding_dimension,
        )
    else:
        vectorstore = VectorStore.in_memory(
            settings.qdrant_collection,
            settings.embedding_dimension,
        )
    vectorstore.ensure_collection()

    app.state.pipeline = Pipeline(chunker, embedding_model, vectorstore)
    app.state.settings = settings
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


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


@app.post("/api/v1/query")
async def query(request: QueryRequest, pipeline: Pipeline = Depends(get_pipeline)):
    result = pipeline.search_document_store(request.question)
    return result


@app.post("/api/v1/reindex")
async def reindex(
    pipeline: Pipeline = Depends(get_pipeline),
    cfg: Settings = Depends(get_settings),
):
    notes = load_notes(cfg.notes_dir, cfg.notes_sync_state_path)
    logger.info("notes_loaded", count=len(notes))

    bookmarks = load_bookmarks(
        cfg.bookmarks_profile_path,
        cfg.bookmarks_sync_state_path,
        cfg.bookmarks_fetch_timeout,
        cfg.bookmarks_max_content_length,
    )
    logger.info("bookmarks_found", count=len(bookmarks))

    docs = notes + bookmarks
    pipeline.add_docs(docs)

    return ReindexResponse(notes_indexed=len(notes), bookmarks_indexed=len(bookmarks))


if __name__ == "__main__":
    uvicorn.run(app, host=settings.host, port=settings.port)
