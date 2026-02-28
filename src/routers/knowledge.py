import structlog
from fastapi import APIRouter, Depends, HTTPException, Request

from app_state import AppState
from config import Settings
from knowledge.loaders.bookmarks import load_bookmarks
from knowledge.loaders.notes import load_notes
from knowledge.pipeline import Pipeline
from models import AskResponse, QueryRequest, ReindexResponse

router = APIRouter(prefix="/api/v1")

logger = structlog.get_logger(__name__)


def get_app_state(request: Request) -> AppState:
    return request.app.state.app_state


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def _require_pipeline(state: AppState) -> Pipeline:
    if state.pipeline is None:
        raise HTTPException(
            status_code=503,
            detail="Mind feature is disabled: GOOGLE_API_KEY not configured",
        )
    return state.pipeline


@router.post("/query")
async def query(request: QueryRequest, state: AppState = Depends(get_app_state)):
    pipeline = _require_pipeline(state)
    return await pipeline.search_document_store(request.question)


@router.post("/ask")
async def ask(
    request: QueryRequest, state: AppState = Depends(get_app_state)
) -> AskResponse:
    pipeline = _require_pipeline(state)
    return await pipeline.ask(request.question)


@router.post("/reindex")
async def reindex(
    state: AppState = Depends(get_app_state),
    cfg: Settings = Depends(get_settings),
):
    pipeline = _require_pipeline(state)

    notes = await load_notes(
        cfg.notes_dir, cfg.notes_sync_state_path, state.file_interpreter
    )
    logger.info("notes_loaded", count=len(notes))

    bookmarks = load_bookmarks(
        cfg.bookmarks_profile_path,
        cfg.bookmarks_sync_state_path,
        cfg.bookmarks_fetch_timeout,
        cfg.bookmarks_max_content_length,
    )
    logger.info("bookmarks_found", count=len(bookmarks))

    docs = notes + bookmarks
    await pipeline.add_docs(docs)

    return ReindexResponse(notes_indexed=len(notes), bookmarks_indexed=len(bookmarks))
