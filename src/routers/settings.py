import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from config import Settings

router = APIRouter(prefix="/api/v1")


class SettingsResponse(BaseModel):
    google_api_key_set: bool
    notes_dir: str
    bookmarks_profile_path: str | None


class SettingsUpdateRequest(BaseModel):
    google_api_key: str = ""
    notes_dir: str = ""
    bookmarks_profile_path: str = ""


class SettingsSaveResponse(BaseModel):
    saved: bool
    restart_required: bool


class BrowseResponse(BaseModel):
    path: str | None


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_env_file() -> Path:
    return Path(".env")


def _write_env(path: Path, updates: dict[str, str]) -> None:
    lines: list[str] = (
        path.read_text(encoding="utf-8").splitlines(keepends=True)
        if path.exists()
        else []
    )
    updated: set[str] = set()
    new_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#") or "=" not in stripped:
            new_lines.append(line)
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in updates:
            new_lines.append(f'{key}="{updates[key]}"\n')
            updated.add(key)
        else:
            new_lines.append(line)
    for key, value in updates.items():
        if key not in updated:
            new_lines.append(f'{key}="{value}"\n')
    path.write_text("".join(new_lines), encoding="utf-8")


@router.get("/settings", response_model=SettingsResponse)
def get_settings_endpoint(cfg: Settings = Depends(get_settings)) -> SettingsResponse:
    return SettingsResponse(
        google_api_key_set=cfg.google_api_key is not None,
        notes_dir=cfg.notes_dir,
        bookmarks_profile_path=cfg.bookmarks_profile_path,
    )


@router.put("/settings", response_model=SettingsSaveResponse)
def put_settings_endpoint(
    body: SettingsUpdateRequest,
    env_file: Path = Depends(get_env_file),
) -> SettingsSaveResponse:
    updates: dict[str, str] = {}
    if body.google_api_key:
        updates["GOOGLE_API_KEY"] = body.google_api_key
    if body.notes_dir:
        updates["NOTES_DIR"] = body.notes_dir
    if body.bookmarks_profile_path:
        updates["BOOKMARKS_PROFILE_PATH"] = body.bookmarks_profile_path
    if updates:
        _write_env(env_file, updates)
    return SettingsSaveResponse(saved=True, restart_required=True)


@router.post("/settings/browse-directory", response_model=BrowseResponse)
def browse_directory_endpoint() -> BrowseResponse:
    if sys.platform != "darwin":
        return BrowseResponse(path=None)
    try:
        result = subprocess.run(
            [
                "osascript",
                "-e",
                'POSIX path of (choose folder with prompt "Select a folder:")',
            ],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode == 0:
            return BrowseResponse(path=result.stdout.strip())
    except (subprocess.TimeoutExpired, OSError):
        pass
    return BrowseResponse(path=None)
