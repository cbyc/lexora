"""Firefox bookmark loader — reads bookmarks and extracts web content."""

import structlog
import platform
import shutil
import sqlite3
import tempfile
from dataclasses import dataclass
from pathlib import Path

import trafilatura

from src.knowledge.loaders.sync_state import load_sync_state, save_sync_state
from src.knowledge.loaders.models import Document

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


def resolve_profile_path(path: str | Path | None) -> Path | None:
    """Resolve a caller-supplied profile path to an existing profile directory.

    Accepts three forms:
    - ``None`` or ``"auto"``: auto-detect the default Firefox profile.
    - A path to ``places.sqlite`` directly: returns the parent directory.
    - A path to the profile directory: returns it unchanged.

    Returns ``None`` (and logs a warning) if the path cannot be resolved to
    an existing directory.

    Args:
        path: Caller-supplied path hint, or None/``"auto"`` for auto-detection.

    Returns:
        Resolved profile directory path, or None if unavailable.
    """
    if path is None or str(path) == "auto":
        resolved_path = find_firefox_profile()
        if resolved_path is None:
            logger.info("firefox_profile_not_found", path=path)
            return None
    else:
        resolved_path = Path(path)
        # Accept path to places.sqlite directly or to the profile directory
        if resolved_path.name == "places.sqlite" and resolved_path.is_file():
            resolved_path = resolved_path.parent
        if not resolved_path.exists():
            logger.warning("firefox_profile_not_found", path=resolved_path)
            return None
    return resolved_path


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


def filter_bookmarks(
    bookmarks: list[BookmarkRecord], last_sync_time: float | None
) -> tuple[list[BookmarkRecord], float]:
    """Filter bookmarks to only those added after the last sync, and track the latest timestamp.

    Args:
        bookmarks: Full list of bookmark records to filter.
        last_sync_time: Timestamp of the previous sync (microseconds since epoch),
            or None if this is the first sync.

    Returns:
        A tuple of (filtered_bookmarks, latest_timestamp) where:
        - filtered_bookmarks contains only records whose date_added is strictly
          greater than last_sync_time.
        - latest_timestamp is the maximum date_added among the filtered records,
          or last_sync_time (or 0) if no records passed the filter.
    """
    filtered_bookmarks = []
    since = last_sync_time or 0
    latest = since
    for b in bookmarks:
        if b.date_added > since:
            filtered_bookmarks.append(b)
            latest = max(latest, b.date_added)
    return (filtered_bookmarks, latest)


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
            logger.warning("fetch_url_returns_none", url=url)
            return None

        text = trafilatura.extract(downloaded)
        if text is None:
            logger.warning("extract_url_returns_none", url=url)
            return None

        if len(text) > max_length:
            text = text[:max_length]

        return text
    except Exception as e:
        logger.warning("fetch_url_failed", url=url, error=e)
        return None


def fetch_documents(
    bookmarks: list[BookmarkRecord], timeout: int, max_length: int
) -> list[Document]:
    """Fetch web content for a list of bookmarks and return them as Documents.

    Bookmarks whose content cannot be fetched or extracted are silently skipped.

    Args:
        bookmarks: Bookmark records to fetch content for.
        timeout: HTTP request timeout in seconds.
        max_length: Maximum number of characters to retain per page.

    Returns:
        List of Document objects, one per successfully fetched bookmark.
    """
    documents = []
    for bookmark in bookmarks:
        content = fetch_page_content(
            bookmark.url,
            timeout=timeout,
            max_length=max_length,
        )
        if content:
            documents.append(
                Document(
                    content=content,
                    source=bookmark.url,
                )
            )
    return documents


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
    resolved_path = resolve_profile_path(profile_path)

    # Load sync state
    last_sync = load_sync_state(sync_state_path)

    # Read bookmarks (incremental if we have a last sync timestamp)
    bookmarks = read_bookmarks(resolved_path, since_timestamp=last_sync)
    if not bookmarks:
        logger.info("bookmarks_not_found")
        return []

    # Filter bookmarks from the last sync timestamp
    filtered_bookmarks, latest_timestamp = filter_bookmarks(bookmarks, last_sync)
    logger.info("bokkmarks_found", count=len(bookmarks))

    # Fetch content and create documents
    documents = fetch_documents(filtered_bookmarks, fetch_timeout, max_content_length)

    # Save sync state with the latest timestamp
    save_sync_state(sync_state_path, latest_timestamp)

    logger.info("bookmarks_fetched", count=len(documents))
    return documents
