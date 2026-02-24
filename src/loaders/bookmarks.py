"""Firefox bookmark loader — reads bookmarks and extracts web content."""

import structlog
import platform
import shutil
import sqlite3
import tempfile
from dataclasses import dataclass
from pathlib import Path

import trafilatura

from src.loaders.sync_state import load_sync_state, save_sync_state
from src.loaders.models import Document

logger = structlog.get_logger(__name__)


@dataclass
class BookmarkRecord:
    """A raw bookmark record from Firefox."""

    url: str
    title: str
    date_added: int  # microseconds since epoch


def find_firefox_profile() -> Path | None:
    """Auto-detect the default Firefox profile directory.

    Returns:
        Path to the Firefox profile directory, or None if not found.
    """
    system = platform.system()
    home = Path.home()

    if system == "Darwin":
        profiles_dir = home / "Library" / "Application Support" / "Firefox" / "Profiles"
    elif system == "Linux":
        profiles_dir = home / ".mozilla" / "firefox"
    elif system == "Windows":
        profiles_dir = home / "AppData" / "Roaming" / "Mozilla" / "Firefox" / "Profiles"
    else:
        return None

    if not profiles_dir.exists():
        return None

    # Look for default profile (usually ends with .default or .default-release)
    for profile_dir in sorted(profiles_dir.iterdir()):
        if profile_dir.is_dir() and (
            profile_dir.name.endswith(".default")
            or profile_dir.name.endswith(".default-release")
        ):
            places_db = profile_dir / "places.sqlite"
            if places_db.exists():
                return profile_dir

    # Fallback: use first profile with places.sqlite
    for profile_dir in sorted(profiles_dir.iterdir()):
        if profile_dir.is_dir():
            places_db = profile_dir / "places.sqlite"
            if places_db.exists():
                return profile_dir

    return None


def read_bookmarks(
    profile_path: Path,
    since_timestamp: int | None = None,
) -> list[BookmarkRecord]:
    """Read bookmarks from Firefox's places.sqlite.

    Copies the database first to avoid lock conflicts with running Firefox.

    Args:
        profile_path: Path to the Firefox profile directory.
        since_timestamp: Only return bookmarks added after this timestamp
            (microseconds since epoch). If None, return all bookmarks.

    Returns:
        List of BookmarkRecord objects.

    Raises:
        FileNotFoundError: If places.sqlite doesn't exist.
    """
    places_db = profile_path / "places.sqlite"
    if not places_db.exists():
        raise FileNotFoundError(f"Firefox places.sqlite not found at: {places_db}")

    # Copy to temp file to avoid Firefox lock issues
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        shutil.copy2(places_db, tmp_path)
        return _query_bookmarks(tmp_path, since_timestamp)
    finally:
        tmp_path.unlink(missing_ok=True)


def _query_bookmarks(
    db_path: Path,
    since_timestamp: int | None = None,
) -> list[BookmarkRecord]:
    """Query bookmarks from a SQLite database.

    Args:
        db_path: Path to the SQLite database file.
        since_timestamp: Only return bookmarks after this timestamp.

    Returns:
        List of BookmarkRecord objects.
    """
    conn = sqlite3.connect(str(db_path))
    try:
        query = """
            SELECT p.url, b.title, b.dateAdded
            FROM moz_bookmarks b
            JOIN moz_places p ON b.fk = p.id
            WHERE b.type = 1
              AND p.url NOT LIKE 'place:%'
              AND p.url NOT LIKE 'about:%'
        """
        params: list = []
        if since_timestamp is not None:
            query += " AND b.dateAdded > ?"
            params.append(since_timestamp)

        query += " ORDER BY b.dateAdded"

        cursor = conn.execute(query, params)
        bookmarks = []
        for url, title, date_added in cursor:
            bookmarks.append(
                BookmarkRecord(
                    url=url,
                    title=title or url,
                    date_added=date_added,
                )
            )
        return bookmarks
    finally:
        conn.close()


def fetch_page_content(
    url: str,
    timeout: int = 15,
    max_length: int = 50000,
) -> str | None:
    """Download a URL and extract readable text content.

    Uses trafilatura for clean article text extraction.

    Args:
        url: The URL to fetch.
        timeout: Download timeout in seconds.
        max_length: Maximum characters to return.

    Returns:
        Extracted text content, or None on failure.
    """
    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded is None:
            logger.warning("Failed to download: %s", url)
            return None

        text = trafilatura.extract(downloaded)
        if text is None:
            logger.warning("Failed to extract content from: %s", url)
            return None

        if len(text) > max_length:
            text = text[:max_length]

        return text
    except Exception as e:
        logger.warning("Error fetching %s: %s", url, e)
        return None


def load_bookmarks(
    profile_path: str | Path | None = None,
    sync_state_path: str | Path = "data/bookmarks_sync_state.json",
    fetch_timeout: int = 15,
    max_content_length: int = 50000,
) -> list[Document]:
    """Load Firefox bookmarks as Documents, with incremental sync.

    On first run, processes all bookmarks. On subsequent runs,
    only processes bookmarks added after the last sync.

    Args:
        profile_path: Path to Firefox profile. None to auto-detect.
        sync_state_path: Path to the sync state JSON file.
        fetch_timeout: Timeout for fetching each page.
        max_content_length: Max characters per page.

    Returns:
        List of Document objects from newly synced bookmarks.
    """
    # Resolve profile path
    if profile_path is None or str(profile_path) == "auto":
        resolved_path = find_firefox_profile()
        if resolved_path is None:
            logger.info("No Firefox profile found. Skipping bookmark sync.")
            return []
    else:
        resolved_path = Path(profile_path)
        # Accept path to places.sqlite directly or to the profile directory
        if resolved_path.name == "places.sqlite" and resolved_path.is_file():
            resolved_path = resolved_path.parent
        if not resolved_path.exists():
            logger.warning("Firefox profile not found at: %s", resolved_path)
            return []

    # Load sync state
    last_sync = load_sync_state(sync_state_path)

    # Read bookmarks (incremental if we have a last sync timestamp)
    bookmarks = read_bookmarks(resolved_path, since_timestamp=last_sync)
    if not bookmarks:
        logger.info("No new bookmarks found since last sync.")
        return []

    logger.info("Found %d new bookmarks to process.", len(bookmarks))

    # Fetch content and create documents
    documents = []
    max_timestamp = last_sync or 0

    for bookmark in bookmarks:
        content = fetch_page_content(
            bookmark.url,
            timeout=fetch_timeout,
            max_length=max_content_length,
        )
        if content:
            documents.append(
                Document(
                    content=content,
                    source=bookmark.url,
                )
            )
        max_timestamp = max(max_timestamp, bookmark.date_added)

    # Save sync state with the latest timestamp
    if max_timestamp > (last_sync or 0):
        save_sync_state(sync_state_path, max_timestamp)

    logger.info("Loaded %d bookmark documents.", len(documents))
    return documents
