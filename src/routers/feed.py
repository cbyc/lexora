import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from src.app_state import AppState
from src.feed.models import DuplicateFeedError
from src.models import AddFeedRequest, AddFeedResponse

router = APIRouter(prefix="/api/v1")

logger = structlog.get_logger(__name__)


def get_app_state(request: Request) -> AppState:
    return request.app.state.app_state


@router.get("/rss")
async def get_rss(
    range: str = "",
    from_: str = "",
    to: str = "",
    state: AppState = Depends(get_app_state),
):
    try:
        result = await state.feed_service.get_posts(
            range_param=range,
            from_param=from_,
            to_param=to,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    posts = [
        {
            "feed_name": p.feed_name,
            "title": p.title,
            "url": p.url,
            "published_at": p.published_at.isoformat(),
        }
        for p in result.posts
    ]

    headers = {}
    if result.errors and not result.posts:
        headers["X-Feed-Errors"] = "all-feeds-failed"

    return JSONResponse(content=posts, headers=headers)


@router.put("/rss", status_code=201)
async def put_rss(
    body: AddFeedRequest,
    state: AppState = Depends(get_app_state),
) -> AddFeedResponse:
    try:
        feed = await state.feed_service.add_feed(body.name, body.url)
    except DuplicateFeedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    logger.info("feed_added", name=feed.name, url=feed.url)
    return AddFeedResponse(
        message="Feed added successfully",
        feed={"name": feed.name, "url": feed.url},
    )
