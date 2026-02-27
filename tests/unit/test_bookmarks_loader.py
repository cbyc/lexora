"""Tests for the Firefox bookmark loader."""

import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

from src.knowledge.loaders.bookmarks import (
    BookmarkRecord,
    _query_bookmarks,
    fetch_documents,
    fetch_page_content,
    filter_bookmarks,
    read_bookmarks,
    resolve_profile_path,
)
from src.knowledge.loaders.models import Document
from src.knowledge.loaders.sync_state import load_sync_state, save_sync_state


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

    @patch("src.knowledge.loaders.bookmarks.trafilatura.fetch_url")
    @patch("src.knowledge.loaders.bookmarks.trafilatura.extract")
    def test_successful_extraction(self, mock_extract, mock_fetch):
        """Should return extracted text on success."""
        mock_fetch.return_value = "<html><body>Hello world</body></html>"
        mock_extract.return_value = "Hello world"
        result = fetch_page_content("https://example.com")
        assert result == "Hello world"

    @patch("src.knowledge.loaders.bookmarks.trafilatura.fetch_url")
    def test_failed_download(self, mock_fetch):
        """Should return None on download failure."""
        mock_fetch.return_value = None
        result = fetch_page_content("https://example.com/broken")
        assert result is None

    @patch("src.knowledge.loaders.bookmarks.trafilatura.fetch_url")
    @patch("src.knowledge.loaders.bookmarks.trafilatura.extract")
    def test_content_truncation(self, mock_extract, mock_fetch):
        """Should truncate content exceeding max_length."""
        mock_fetch.return_value = "<html><body>text</body></html>"
        mock_extract.return_value = "x" * 100
        result = fetch_page_content("https://example.com", max_length=50)
        assert result is not None
        assert len(result) == 50


class TestResolveProfilePath:
    """Tests for resolve_profile_path."""

    def test_none_triggers_auto_detect(self, tmp_path: Path):
        """None should delegate to find_firefox_profile."""
        with patch(
            "src.knowledge.loaders.bookmarks.find_firefox_profile",
            return_value=tmp_path,
        ):
            result = resolve_profile_path(None)
        assert result == tmp_path

    def test_auto_string_triggers_auto_detect(self, tmp_path: Path):
        """'auto' should behave identically to None."""
        with patch(
            "src.knowledge.loaders.bookmarks.find_firefox_profile",
            return_value=tmp_path,
        ):
            result = resolve_profile_path("auto")
        assert result == tmp_path

    def test_returns_none_when_no_profile_found(self):
        """Should return None when auto-detection finds no profile."""
        with patch(
            "src.knowledge.loaders.bookmarks.find_firefox_profile", return_value=None
        ):
            result = resolve_profile_path(None)
        assert result is None

    def test_places_sqlite_path_returns_parent_directory(self, tmp_path: Path):
        """A direct path to places.sqlite should resolve to its parent directory."""
        db = tmp_path / "places.sqlite"
        db.touch()
        result = resolve_profile_path(db)
        assert result == tmp_path

    def test_profile_directory_returned_as_is(self, tmp_path: Path):
        """An existing profile directory path should be returned unchanged."""
        result = resolve_profile_path(tmp_path)
        assert result == tmp_path

    def test_nonexistent_path_returns_none(self):
        """A path that does not exist on disk should return None."""
        result = resolve_profile_path("/nonexistent/path/to/profile")
        assert result is None


class TestFilterBookmarks:
    """Tests for filter_bookmarks."""

    def test_empty_list_returns_empty_and_zero(self):
        """An empty input should return an empty list and 0 as the latest timestamp."""
        result, latest = filter_bookmarks([], None)
        assert result == []
        assert latest == 0

    def test_no_last_sync_returns_all_bookmarks(self):
        """With no prior sync, all bookmarks should be returned."""
        bookmarks = [
            BookmarkRecord("https://a.com", "A", 1700000000000000),
            BookmarkRecord("https://b.com", "B", 1700100000000000),
        ]
        result, _ = filter_bookmarks(bookmarks, None)
        assert len(result) == 2

    def test_filters_bookmarks_at_or_before_last_sync(self):
        """Bookmarks added at or before last_sync_time should be excluded."""
        bookmarks = [
            BookmarkRecord("https://a.com", "A", 1700000000000000),
            BookmarkRecord("https://b.com", "B", 1700100000000000),
        ]
        result, _ = filter_bookmarks(bookmarks, 1700000000000000)
        assert len(result) == 1
        assert result[0].url == "https://b.com"

    def test_bookmark_exactly_at_last_sync_is_excluded(self):
        """A bookmark whose date_added equals last_sync_time must not be included."""
        bookmarks = [BookmarkRecord("https://a.com", "A", 1700000000000000)]
        result, _ = filter_bookmarks(bookmarks, 1700000000000000)
        assert result == []

    def test_returns_max_timestamp_of_filtered_bookmarks(self):
        """The returned latest timestamp should be the max date_added of accepted bookmarks."""
        bookmarks = [
            BookmarkRecord("https://a.com", "A", 1700100000000000),
            BookmarkRecord("https://b.com", "B", 1700200000000000),
            BookmarkRecord("https://c.com", "C", 1700300000000000),
        ]
        _, latest = filter_bookmarks(bookmarks, 1700000000000000)
        assert latest == 1700300000000000

    def test_returns_last_sync_time_when_nothing_passes_filter(self):
        """When no bookmark passes the filter, latest should equal last_sync_time."""
        bookmarks = [BookmarkRecord("https://a.com", "A", 1700000000000000)]
        _, latest = filter_bookmarks(bookmarks, 1700100000000000)
        assert latest == 1700100000000000


class TestFetchDocuments:
    """Tests for fetch_documents."""

    def test_empty_list_returns_empty(self):
        """An empty bookmark list should return an empty document list."""
        result = fetch_documents([], timeout=15, max_length=50000)
        assert result == []

    @patch("src.knowledge.loaders.bookmarks.fetch_page_content")
    def test_successful_fetch_produces_document(self, mock_fetch):
        """A bookmark whose content is fetched should produce one Document."""
        mock_fetch.return_value = "page content"
        bookmarks = [BookmarkRecord("https://example.com", "Example", 1700000000000000)]
        result = fetch_documents(bookmarks, timeout=15, max_length=50000)
        assert len(result) == 1
        assert isinstance(result[0], Document)
        assert result[0].content == "page content"
        assert result[0].source == "https://example.com"

    @patch("src.knowledge.loaders.bookmarks.fetch_page_content")
    def test_failed_fetch_is_skipped(self, mock_fetch):
        """A bookmark whose content cannot be fetched should be omitted."""
        mock_fetch.return_value = None
        bookmarks = [BookmarkRecord("https://broken.com", "Broken", 1700000000000000)]
        result = fetch_documents(bookmarks, timeout=15, max_length=50000)
        assert result == []

    @patch("src.knowledge.loaders.bookmarks.fetch_page_content")
    def test_partial_failures_return_successful_only(self, mock_fetch):
        """Only bookmarks with successful fetches should appear in the result."""
        mock_fetch.side_effect = ["content for a", None, "content for c"]
        bookmarks = [
            BookmarkRecord("https://a.com", "A", 1700000000000000),
            BookmarkRecord("https://b.com", "B", 1700100000000000),
            BookmarkRecord("https://c.com", "C", 1700200000000000),
        ]
        result = fetch_documents(bookmarks, timeout=15, max_length=50000)
        assert len(result) == 2
        assert result[0].source == "https://a.com"
        assert result[1].source == "https://c.com"

    @patch("src.knowledge.loaders.bookmarks.fetch_page_content")
    def test_passes_timeout_and_max_length_to_fetch(self, mock_fetch):
        """timeout and max_length should be forwarded to fetch_page_content."""
        mock_fetch.return_value = "content"
        bookmarks = [BookmarkRecord("https://example.com", "Example", 1700000000000000)]
        fetch_documents(bookmarks, timeout=30, max_length=1000)
        mock_fetch.assert_called_once_with(
            "https://example.com", timeout=30, max_length=1000
        )
