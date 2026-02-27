from fastapi import APIRouter, Depends, Request

from src.app_state import AppState
from src.config import Settings
from src.knowledge.loaders.bookmarks import load_bookmarks
from src.knowledge.loaders.notes import load_notes
from src.models import AskResponse, QueryRequest, ReindexResponse

router = APIRouter(prefix="/api/v1")


def get_app_state(request: Request) -> AppState:
    return request.app.state.app_state


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


@router.post("/query")
async def query(request: QueryRequest, state: AppState = Depends(get_app_state)):
    return await state.pipeline.search_document_store(request.question)


@router.post("/ask")
async def ask(
    request: QueryRequest, state: AppState = Depends(get_app_state)
) -> AskResponse:
    return await state.pipeline.ask(request.question)


@router.post("/reindex")
async def reindex(
    state: AppState = Depends(get_app_state),
    cfg: Settings = Depends(get_settings),
):
    import structlog

    logger = structlog.get_logger(__name__)

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
    await state.pipeline.add_docs(docs)

    return ReindexResponse(notes_indexed=len(notes), bookmarks_indexed=len(bookmarks))
