"""Tests for document loading from filesystem."""

import time
from pathlib import Path

import pytest

from src.loaders.notes import load_notes
from src.loaders.models import Document


class TestLoadNotes:
    """Tests for the load_notes function."""

    def test_returns_list_of_documents(self, test_data_dir: Path, tmp_path: Path):
        """load_notes should return a list of Document objects."""
        docs = load_notes(test_data_dir, sync_state_path=tmp_path / "state.json")
        assert isinstance(docs, list)
        assert len(docs) > 0
        assert all(isinstance(d, Document) for d in docs)

    def test_finds_all_txt_files(self, test_data_dir: Path, tmp_path: Path):
        """Should find all 4 synthetic test files on first run."""
        docs = load_notes(test_data_dir, sync_state_path=tmp_path / "state.json")
        assert len(docs) == 4

    def test_content_not_empty(self, test_data_dir: Path, tmp_path: Path):
        """Each loaded document should have non-empty content."""
        docs = load_notes(test_data_dir, sync_state_path=tmp_path / "state.json")
        for doc in docs:
            assert len(doc.content) > 0

    def test_source_is_set(self, test_data_dir: Path, tmp_path: Path):
        """Each document should have its source file path set."""
        docs = load_notes(test_data_dir, sync_state_path=tmp_path / "state.json")
        for doc in docs:
            assert doc.source != ""
            assert doc.source.endswith(".txt")

    def test_nonexistent_dir_raises(self, tmp_path: Path):
        """Should raise FileNotFoundError for a nonexistent directory."""
        with pytest.raises(FileNotFoundError):
            load_notes("/nonexistent/path", sync_state_path=tmp_path / "state.json")

    def test_empty_dir_returns_empty_list(self, tmp_path: Path):
        """Should return empty list for directory with no .txt files."""
        notes_dir = tmp_path / "notes"
        notes_dir.mkdir()
        docs = load_notes(notes_dir, sync_state_path=tmp_path / "state.json")
        assert docs == []

    def test_second_call_returns_no_docs_when_nothing_changed(self, tmp_path: Path):
        """Second call with no file changes should return an empty list."""
        notes_dir = tmp_path / "notes"
        notes_dir.mkdir()
        (notes_dir / "a.txt").write_text("hello")
        state = tmp_path / "state.json"

        first = load_notes(notes_dir, sync_state_path=state)
        assert len(first) == 1

        second = load_notes(notes_dir, sync_state_path=state)
        assert second == []

    def test_new_file_picked_up_on_next_call(self, tmp_path: Path):
        """A file created after the last sync should be returned on the next call."""
        notes_dir = tmp_path / "notes"
        notes_dir.mkdir()
        (notes_dir / "a.txt").write_text("first")
        state = tmp_path / "state.json"

        load_notes(notes_dir, sync_state_path=state)

        # Small sleep so the new file's mtime is strictly after the saved timestamp
        time.sleep(0.05)
        (notes_dir / "b.txt").write_text("second")

        docs = load_notes(notes_dir, sync_state_path=state)
        assert len(docs) == 1
        assert docs[0].content == "second"

    def test_modified_file_picked_up_on_next_call(self, tmp_path: Path):
        """A file modified after the last sync should be returned on the next call."""
        notes_dir = tmp_path / "notes"
        notes_dir.mkdir()
        note = notes_dir / "a.txt"
        note.write_text("original")
        state = tmp_path / "state.json"

        load_notes(notes_dir, sync_state_path=state)

        time.sleep(0.05)
        note.write_text("updated")

        docs = load_notes(notes_dir, sync_state_path=state)
        assert len(docs) == 1
        assert docs[0].content == "updated"
