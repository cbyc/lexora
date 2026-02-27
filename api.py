import logging
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from src.app_state import AppState
from src.config import Settings
from src.feed.fetcher import HttpFeedFetcher
from src.feed.service import FeedService
from src.feed.store import YamlFeedStore
from src.knowledge.ask_agent import PydanticAIAskAgent
from src.knowledge.chunker import SimpleChunker
from src.knowledge.embedder import GeminiEmbeddingModel
from src.knowledge.pipeline import Pipeline
from src.knowledge.vector_store import VectorStore
from src.routers import feed, knowledge

settings = Settings()

logging.basicConfig(level=settings.log_level.upper())
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.google_api_key is None:
        raise RuntimeError(
            "GOOGLE_API_KEY is required but not set. "
            "Set it in your environment or .env file."
        )

    chunker = SimpleChunker(settings.chunk_size, settings.chunk_overlap)
    embedding_model = GeminiEmbeddingModel(
        model_name=settings.gemini_embedding_model,
        api_key=settings.google_api_key,
    )

    if settings.chroma_path:
        vectorstore = VectorStore.from_path(
            settings.chroma_path,
            settings.chroma_collection,
            settings.embedding_dimension,
        )
    else:
        vectorstore = VectorStore.in_memory(
            settings.chroma_collection,
            settings.embedding_dimension,
        )
    vectorstore.ensure_collection()

    ask_agent = PydanticAIAskAgent(settings.llm_model)
    pipeline = Pipeline(chunker, embedding_model, vectorstore, ask_agent)

    feed_store = YamlFeedStore(settings.feed_data_file)
    feed_store.ensure_data_file()
    feed_fetcher = HttpFeedFetcher()
    feed_service = FeedService(
        store=feed_store,
        fetcher=feed_fetcher,
        default_range=settings.feed_default_range,
        max_posts_per_feed=settings.feed_max_posts_per_feed,
        timeout=float(settings.feed_fetch_timeout_sec),
    )

    app.state.app_state = AppState(pipeline=pipeline, feed_service=feed_service)
    app.state.settings = settings

    logger.info(
        "startup_complete",
        embedding_model=settings.gemini_embedding_model,
        llm_model=settings.llm_model,
        feed_data_file=settings.feed_data_file,
    )
    yield


app = FastAPI(title="Lexora API", lifespan=lifespan)

app.include_router(knowledge.router)
app.include_router(feed.router)
app.mount("/", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="static")


if __name__ == "__main__":
    uvicorn.run(app, host=settings.host, port=settings.port)
