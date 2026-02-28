from fastapi import APIRouter, Depends, Request

from app_state import AppState

router = APIRouter(prefix="/api/v1")


def get_app_state(request: Request) -> AppState:
    return request.app.state.app_state


@router.get("/capabilities")
def capabilities(state: AppState = Depends(get_app_state)) -> dict:
    return {
        "mind_enabled": state.pipeline is not None,
        "feed_enabled": True,
    }
