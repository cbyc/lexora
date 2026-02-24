"""Shared fixtures for ingest unit tests."""

from pathlib import Path

import pytest

from src.models import Chunk


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


@pytest.fixture
def sample_chunks() -> list[Chunk]:
    """A list of sample chunks for testing."""
    return [
        Chunk(text="First chunk of text about Python.", source="doc1.txt", chunk_index=0),
        Chunk(text="Second chunk about machine learning.", source="doc1.txt", chunk_index=1),
        Chunk(text="Third chunk about cooking recipes.", source="doc2.txt", chunk_index=0),
    ]


@pytest.fixture
def sample_embeddings() -> list[list[float]]:
    """Fake embeddings for testing (384-dimensional vectors with distinct elements)."""
    dim = 384
    return [
        [1.0] + [0.0] * (dim - 1),
        [0.0, 1.0] + [0.0] * (dim - 2),
        [0.0, 0.0, 1.0] + [0.0] * (dim - 3),
    ]
