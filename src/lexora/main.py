import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from lexora.app_state import AppState
from lexora.config import Settings
from lexora.feed.fetcher import HttpFeedFetcher
from lexora.feed.service import FeedService
from lexora.feed.store import YamlFeedStore
from lexora.knowledge.ask_agent import PydanticAIAskAgent
from lexora.knowledge.chunker import SimpleChunker
from lexora.knowledge.embedder import GeminiEmbeddingModel
from lexora.knowledge.file_interpreter import GeminiFileInterpreter
from lexora.knowledge.pipeline import Pipeline
from lexora.knowledge.vector_store import VectorStore
from lexora.routers import capabilities, feed, knowledge, settings as settings_mod

settings = Settings()

logging.basicConfig(level=settings.log_level.upper())
logger = structlog.get_logger(__name__)

_STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.google_api_key is None:
        logger.warning("mind_disabled", reason="GOOGLE_API_KEY not set")
        pipeline = None
    else:
        # pydantic-settings reads .env into settings but does not inject values
        # back into os.environ; pydantic-ai's GoogleProvider reads os.environ
        # directly, so we bridge the gap here.
        os.environ.setdefault("GOOGLE_API_KEY", settings.google_api_key)
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

    file_interpreter = (
        GeminiFileInterpreter(
            model=settings.file_interpreter_model,
            api_key=settings.google_api_key,
        )
        if settings.google_api_key
        else None
    )

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

    app.state.app_state = AppState(
        pipeline=pipeline,
        feed_service=feed_service,
        file_interpreter=file_interpreter,
    )
    app.state.settings = settings

    log_kwargs = {"feed_data_file": settings.feed_data_file}
    if pipeline is not None:
        log_kwargs["embedding_model"] = settings.gemini_embedding_model
        log_kwargs["llm_model"] = settings.llm_model
    logger.info("startup_complete", **log_kwargs)
    yield


app = FastAPI(title="Lexora API", lifespan=lifespan)

app.include_router(capabilities.router)
app.include_router(knowledge.router)
app.include_router(feed.router)
app.include_router(settings_mod.router)
app.mount(
    "/",
    StaticFiles(directory=_STATIC_DIR, html=True),
    name="static",
)


def serve() -> None:
    """Entry point invoked by `lexora` CLI command."""
    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    serve()
