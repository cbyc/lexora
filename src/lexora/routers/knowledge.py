import asyncio

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request

from lexora.app_state import AppState
from lexora.config import Settings
from lexora.knowledge.loaders.bookmarks import load_bookmarks
from lexora.knowledge.loaders.notes import load_notes
from lexora.knowledge.pipeline import Pipeline
from lexora.models import AskResponse, QueryRequest

router = APIRouter(prefix="/api/v1")

logger = structlog.get_logger(__name__)

_reindex_task: asyncio.Task | None = None


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


async def _run_reindex(pipeline: Pipeline, cfg: Settings, state: AppState) -> None:
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

    await pipeline.add_docs(notes + bookmarks)
    logger.info("reindex_complete", notes=len(notes), bookmarks=len(bookmarks))


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


@router.post("/reindex", status_code=202)
async def reindex(
    state: AppState = Depends(get_app_state),
    cfg: Settings = Depends(get_settings),
):
    global _reindex_task
    pipeline = _require_pipeline(state)
    if _reindex_task is not None and not _reindex_task.done():
        raise HTTPException(status_code=409, detail="Reindex already in progress")
    _reindex_task = asyncio.create_task(_run_reindex(pipeline, cfg, state))
    return {"status": "started"}
