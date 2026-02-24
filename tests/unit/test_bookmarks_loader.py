"""Tests for the Firefox bookmark loader."""

import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from src.loaders.bookmarks import (
    BookmarkRecord,
    _query_bookmarks,
    fetch_page_content,
    read_bookmarks,
)
from src.loaders.sync_state import load_sync_state, save_sync_state


@pytest.fixture
def firefox_db(tmp_path: Path) -> Path:
    """Create a test Firefox places.sqlite with sample bookmarks."""
    db_path = tmp_path / "places.sqlite"
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE moz_places (
            id INTEGER PRIMARY KEY,
            url TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE moz_bookmarks (
            id INTEGER PRIMARY KEY,
            type INTEGER NOT NULL,
            fk INTEGER,
            title TEXT,
            dateAdded INTEGER,
            FOREIGN KEY (fk) REFERENCES moz_places(id)
        )
    """)
    # Insert test data
    conn.execute(
        "INSERT INTO moz_places (id, url) VALUES (1, 'https://example.com/article1')"
    )
    conn.execute(
        "INSERT INTO moz_places (id, url) VALUES (2, 'https://example.com/article2')"
    )
    conn.execute(
        "INSERT INTO moz_places (id, url) VALUES (3, 'place:sort=8')"
    )  # folder/separator
    conn.execute("INSERT INTO moz_places (id, url) VALUES (4, 'about:config')")

    # type=1 is bookmarks, type=2 is folders
    conn.execute(
        "INSERT INTO moz_bookmarks (id, type, fk, title, dateAdded) "
        "VALUES (1, 1, 1, 'Article One', 1700000000000000)"
    )
    conn.execute(
        "INSERT INTO moz_bookmarks (id, type, fk, title, dateAdded) "
        "VALUES (2, 1, 2, 'Article Two', 1700100000000000)"
    )
    conn.execute(
        "INSERT INTO moz_bookmarks (id, type, fk, title, dateAdded) "
        "VALUES (3, 2, 3, 'Folder', 1700000000000000)"  # folder, not bookmark
    )
    conn.execute(
        "INSERT INTO moz_bookmarks (id, type, fk, title, dateAdded) "
        "VALUES (4, 1, 4, 'About Config', 1700000000000000)"  # about: URL
    )
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def firefox_profile(tmp_path: Path, firefox_db: Path) -> Path:
    """Create a test Firefox profile directory."""
    profile_dir = tmp_path / "profile"
    profile_dir.mkdir()
    # Copy the test DB to the profile
    import shutil

    shutil.copy2(firefox_db, profile_dir / "places.sqlite")
    return profile_dir


class TestQueryBookmarks:
    """Tests for the _query_bookmarks function."""

    def test_reads_bookmarks(self, firefox_db: Path):
        """Should read bookmark entries from the database."""
        bookmarks = _query_bookmarks(firefox_db)
        assert len(bookmarks) == 2  # Only type=1, excluding place: and about: URLs

    def test_filters_by_type(self, firefox_db: Path):
        """Should only return type=1 (bookmarks, not folders)."""
        bookmarks = _query_bookmarks(firefox_db)
        # Folder (type=2) should be excluded
        assert all(isinstance(b, BookmarkRecord) for b in bookmarks)

    def test_filters_place_urls(self, firefox_db: Path):
        """Should exclude place: and about: URLs."""
        bookmarks = _query_bookmarks(firefox_db)
        urls = [b.url for b in bookmarks]
        assert not any(u.startswith("place:") for u in urls)
        assert not any(u.startswith("about:") for u in urls)

    def test_incremental_filter(self, firefox_db: Path):
        """Should only return bookmarks after the given timestamp."""
        bookmarks = _query_bookmarks(firefox_db, since_timestamp=1700050000000000)
        assert len(bookmarks) == 1
        assert bookmarks[0].title == "Article Two"

    def test_bookmark_fields(self, firefox_db: Path):
        """Should populate all BookmarkRecord fields."""
        bookmarks = _query_bookmarks(firefox_db)
        b = bookmarks[0]
        assert b.url == "https://example.com/article1"
        assert b.title == "Article One"
        assert b.date_added == 1700000000000000


class TestReadBookmarks:
    """Tests for the read_bookmarks function."""

    def test_reads_from_profile(self, firefox_profile: Path):
        """Should read bookmarks from a Firefox profile directory."""
        bookmarks = read_bookmarks(firefox_profile)
        assert len(bookmarks) == 2

    def test_missing_database_raises(self, tmp_path: Path):
        """Should raise FileNotFoundError for missing places.sqlite."""
        with pytest.raises(FileNotFoundError):
            read_bookmarks(tmp_path)


class TestSyncState:
    """Tests for sync state persistence."""

    def test_load_missing_state(self, tmp_path: Path):
        """Should return None when no sync state exists."""
        result = load_sync_state(tmp_path / "nonexistent.json")
        assert result is None

    def test_save_and_load_state(self, tmp_path: Path):
        """Should save and load timestamp correctly."""
        state_path = tmp_path / "sync_state.json"
        save_sync_state(state_path, 1700000000000000)
        result = load_sync_state(state_path)
        assert result == 1700000000000000

    def test_update_state(self, tmp_path: Path):
        """Should update the timestamp when saving again."""
        state_path = tmp_path / "sync_state.json"
        save_sync_state(state_path, 1700000000000000)
        save_sync_state(state_path, 1700100000000000)
        result = load_sync_state(state_path)
        assert result == 1700100000000000

    def test_invalid_json(self, tmp_path: Path):
        """Should return None for invalid JSON."""
        state_path = tmp_path / "sync_state.json"
        state_path.write_text("not json")
        result = load_sync_state(state_path)
        assert result is None


class TestFetchPageContent:
    """Tests for fetch_page_content with mocked HTTP."""

    @patch("src.loaders.bookmarks.trafilatura.fetch_url")
    @patch("src.loaders.bookmarks.trafilatura.extract")
    def test_successful_extraction(self, mock_extract, mock_fetch):
        """Should return extracted text on success."""
        mock_fetch.return_value = "<html><body>Hello world</body></html>"
        mock_extract.return_value = "Hello world"
        result = fetch_page_content("https://example.com")
        assert result == "Hello world"

    @patch("src.loaders.bookmarks.trafilatura.fetch_url")
    def test_failed_download(self, mock_fetch):
        """Should return None on download failure."""
        mock_fetch.return_value = None
        result = fetch_page_content("https://example.com/broken")
        assert result is None

    @patch("src.loaders.bookmarks.trafilatura.fetch_url")
    @patch("src.loaders.bookmarks.trafilatura.extract")
    def test_content_truncation(self, mock_extract, mock_fetch):
        """Should truncate content exceeding max_length."""
        mock_fetch.return_value = "<html><body>text</body></html>"
        mock_extract.return_value = "x" * 100
        result = fetch_page_content("https://example.com", max_length=50)
        assert result is not None
        assert len(result) == 50
