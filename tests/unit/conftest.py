"""Shared fixtures for ingest unit tests."""

from pathlib import Path

import pytest


@pytest.fixture
def test_data_dir(tmp_path: Path) -> Path:
    """Create a temporary directory with 4 synthetic .txt note files."""
    notes_dir = tmp_path / "notes"
    notes_dir.mkdir()
    (notes_dir / "note1.txt").write_text("This is the first note.")
    (notes_dir / "note2.txt").write_text("This is the second note.")
    (notes_dir / "note3.txt").write_text("This is the third note.")
    (notes_dir / "note4.txt").write_text("This is the fourth note.")
    return notes_dir
