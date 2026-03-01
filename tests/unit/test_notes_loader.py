"""Tests for the unified notes loader (txt, md, pdf, subdirs)."""

import asyncio
import time
from pathlib import Path
import pytest

from lexora.knowledge.loaders.notes import load_notes
from lexora.knowledge.loaders.models import Document


class FakeFileInterpreter:
    def __init__(self, return_text: str = "interpreted pdf content"):
        self._return_text = return_text
        self.calls: list[dict] = []

    async def interpret(
        self, file_bytes: bytes, filename: str, system_prompt: str
    ) -> str:
        self.calls.append(
            {
                "file_bytes": file_bytes,
                "filename": filename,
                "system_prompt": system_prompt,
            }
        )
        return self._return_text


class TestLoadNotesTxt:
    """Tests for .txt file loading behaviour."""

    def test_returns_list_of_documents(self, test_data_dir: Path, tmp_path: Path):
        """load_notes should return a list of Document objects."""
        docs = asyncio.run(
            load_notes(test_data_dir, sync_state_path=tmp_path / "state.json")
        )
        assert isinstance(docs, list)
        assert len(docs) > 0
        assert all(isinstance(d, Document) for d in docs)

    def test_finds_all_txt_files(self, test_data_dir: Path, tmp_path: Path):
        """Should find all 4 synthetic .txt files on first run."""
        docs = asyncio.run(
            load_notes(test_data_dir, sync_state_path=tmp_path / "state.json")
        )
        assert len(docs) == 4

    def test_content_not_empty(self, test_data_dir: Path, tmp_path: Path):
        """Each loaded document should have non-empty content."""
        docs = asyncio.run(
            load_notes(test_data_dir, sync_state_path=tmp_path / "state.json")
        )
        for doc in docs:
            assert len(doc.content) > 0

    def test_source_is_set_for_txt(self, test_data_dir: Path, tmp_path: Path):
        """Each .txt document should have its source file path ending in .txt."""
        docs = asyncio.run(
            load_notes(test_data_dir, sync_state_path=tmp_path / "state.json")
        )
        txt_docs = [d for d in docs if d.source.endswith(".txt")]
        assert len(txt_docs) == 4
        for doc in txt_docs:
            assert doc.source != ""

    def test_nonexistent_dir_raises(self, tmp_path: Path):
        """Should raise FileNotFoundError for a nonexistent directory."""
        with pytest.raises(FileNotFoundError):
            asyncio.run(
                load_notes("/nonexistent/path", sync_state_path=tmp_path / "state.json")
            )

    def test_empty_dir_returns_empty_list(self, tmp_path: Path):
        """Should return empty list for directory with no supported files."""
        notes_dir = tmp_path / "notes"
        notes_dir.mkdir()
        docs = asyncio.run(
            load_notes(notes_dir, sync_state_path=tmp_path / "state.json")
        )
        assert docs == []

    def test_second_call_returns_no_docs_when_nothing_changed(self, tmp_path: Path):
        """Second call with no file changes should return an empty list."""
        notes_dir = tmp_path / "notes"
        notes_dir.mkdir()
        (notes_dir / "a.txt").write_text("hello")
        state = tmp_path / "state.json"

        first = asyncio.run(load_notes(notes_dir, sync_state_path=state))
        assert len(first) == 1

        second = asyncio.run(load_notes(notes_dir, sync_state_path=state))
        assert second == []

    def test_new_file_picked_up_on_next_call(self, tmp_path: Path):
        """A file created after the last sync should be returned on the next call."""
        notes_dir = tmp_path / "notes"
        notes_dir.mkdir()
        (notes_dir / "a.txt").write_text("first")
        state = tmp_path / "state.json"

        asyncio.run(load_notes(notes_dir, sync_state_path=state))

        time.sleep(0.05)
        (notes_dir / "b.txt").write_text("second")

        docs = asyncio.run(load_notes(notes_dir, sync_state_path=state))
        assert len(docs) == 1
        assert docs[0].content == "second"

    def test_modified_file_picked_up_on_next_call(self, tmp_path: Path):
        """A file modified after the last sync should be returned on the next call."""
        notes_dir = tmp_path / "notes"
        notes_dir.mkdir()
        note = notes_dir / "a.txt"
        note.write_text("original")
        state = tmp_path / "state.json"

        asyncio.run(load_notes(notes_dir, sync_state_path=state))

        time.sleep(0.05)
        note.write_text("updated")

        docs = asyncio.run(load_notes(notes_dir, sync_state_path=state))
        assert len(docs) == 1
        assert docs[0].content == "updated"

    def test_unknown_file_type_skipped(self, tmp_path: Path):
        """Files with unsupported extensions (e.g. .csv) are silently ignored."""
        notes_dir = tmp_path / "notes"
        notes_dir.mkdir()
        (notes_dir / "data.csv").write_text("col1,col2")
        (notes_dir / "note.txt").write_text("hello")
        state = tmp_path / "state.json"

        docs = asyncio.run(load_notes(notes_dir, sync_state_path=state))
        assert len(docs) == 1
        assert docs[0].source.endswith(".txt")


class TestLoadNotesMd:
    """Tests for .md (Markdown) file loading."""

    def test_loads_md_file_as_plain_text(self, tmp_path: Path):
        """A .md file should be loaded and converted to plain text."""
        notes_dir = tmp_path / "notes"
        notes_dir.mkdir()
        (notes_dir / "readme.md").write_text("# Hello\n\nThis is **bold** text.")
        state = tmp_path / "state.json"

        docs = asyncio.run(load_notes(notes_dir, sync_state_path=state))
        assert len(docs) == 1
        assert docs[0].source.endswith(".md")
        # Markdown headings and bold stripped; plain words present
        assert "Hello" in docs[0].content
        assert "bold" in docs[0].content
        # Should not contain raw HTML or markdown syntax
        assert "<h1>" not in docs[0].content
        assert "**" not in docs[0].content

    def test_md_source_path_set_correctly(self, tmp_path: Path):
        """Document source for a .md file should point to the .md file."""
        notes_dir = tmp_path / "notes"
        notes_dir.mkdir()
        md_file = notes_dir / "note.md"
        md_file.write_text("# Note")
        state = tmp_path / "state.json"

        docs = asyncio.run(load_notes(notes_dir, sync_state_path=state))
        assert docs[0].source == str(md_file)

    def test_loads_txt_and_md_together(self, tmp_path: Path):
        """Both .txt and .md files in the same directory should be loaded."""
        notes_dir = tmp_path / "notes"
        notes_dir.mkdir()
        (notes_dir / "a.txt").write_text("plain text")
        (notes_dir / "b.md").write_text("# Markdown")
        state = tmp_path / "state.json"

        docs = asyncio.run(load_notes(notes_dir, sync_state_path=state))
        assert len(docs) == 2
        suffixes = {Path(d.source).suffix for d in docs}
        assert suffixes == {".txt", ".md"}


class TestLoadNotesPdf:
    """Tests for .pdf file loading via FileInterpreter."""

    def test_pdf_loaded_via_interpreter(self, tmp_path: Path):
        """A .pdf file should be passed to the interpreter and its text returned."""
        notes_dir = tmp_path / "notes"
        notes_dir.mkdir()
        pdf_bytes = b"%PDF-1.4 fake pdf content"
        (notes_dir / "doc.pdf").write_bytes(pdf_bytes)
        state = tmp_path / "state.json"

        interpreter = FakeFileInterpreter("extracted pdf text")
        docs = asyncio.run(
            load_notes(notes_dir, sync_state_path=state, interpreter=interpreter)
        )

        assert len(docs) == 1
        assert docs[0].content == "extracted pdf text"
        assert docs[0].source.endswith(".pdf")

    def test_pdf_interpreter_receives_file_bytes(self, tmp_path: Path):
        """The interpreter should receive the raw PDF bytes."""
        notes_dir = tmp_path / "notes"
        notes_dir.mkdir()
        pdf_bytes = b"%PDF-1.4 specific content"
        (notes_dir / "doc.pdf").write_bytes(pdf_bytes)
        state = tmp_path / "state.json"

        interpreter = FakeFileInterpreter()
        asyncio.run(
            load_notes(notes_dir, sync_state_path=state, interpreter=interpreter)
        )

        assert interpreter.calls[0]["file_bytes"] == pdf_bytes

    def test_pdf_interpreter_receives_filename(self, tmp_path: Path):
        """The interpreter should receive the PDF filename."""
        notes_dir = tmp_path / "notes"
        notes_dir.mkdir()
        (notes_dir / "my_report.pdf").write_bytes(b"pdf")
        state = tmp_path / "state.json"

        interpreter = FakeFileInterpreter()
        asyncio.run(
            load_notes(notes_dir, sync_state_path=state, interpreter=interpreter)
        )

        assert interpreter.calls[0]["filename"] == "my_report.pdf"

    def test_pdf_skipped_when_no_interpreter(self, tmp_path: Path):
        """PDF files should be skipped (not error) when interpreter is None."""
        notes_dir = tmp_path / "notes"
        notes_dir.mkdir()
        (notes_dir / "doc.pdf").write_bytes(b"pdf content")
        (notes_dir / "note.txt").write_text("hello")
        state = tmp_path / "state.json"

        docs = asyncio.run(
            load_notes(notes_dir, sync_state_path=state, interpreter=None)
        )

        # Only the txt file should be loaded; pdf silently skipped
        assert len(docs) == 1
        assert docs[0].source.endswith(".txt")

    def test_pdf_source_path_set_correctly(self, tmp_path: Path):
        """Document source for a .pdf should point to the .pdf file path."""
        notes_dir = tmp_path / "notes"
        notes_dir.mkdir()
        pdf_path = notes_dir / "paper.pdf"
        pdf_path.write_bytes(b"pdf")
        state = tmp_path / "state.json"

        interpreter = FakeFileInterpreter("text")
        docs = asyncio.run(
            load_notes(notes_dir, sync_state_path=state, interpreter=interpreter)
        )

        assert docs[0].source == str(pdf_path)


class TestLoadNotesSubdirectories:
    """Tests for recursive directory traversal."""

    def test_finds_files_in_subdirectory(self, tmp_path: Path):
        """load_notes should find files in subdirectories."""
        notes_dir = tmp_path / "notes"
        notes_dir.mkdir()
        sub = notes_dir / "sub"
        sub.mkdir()
        (sub / "nested.txt").write_text("nested content")
        state = tmp_path / "state.json"

        docs = asyncio.run(load_notes(notes_dir, sync_state_path=state))
        assert len(docs) == 1
        assert "nested content" == docs[0].content

    def test_finds_files_in_multiple_levels(self, tmp_path: Path):
        """load_notes should traverse multiple levels of subdirectories."""
        notes_dir = tmp_path / "notes"
        notes_dir.mkdir()
        (notes_dir / "root.txt").write_text("root")
        deep = notes_dir / "a" / "b"
        deep.mkdir(parents=True)
        (deep / "deep.md").write_text("# Deep")
        state = tmp_path / "state.json"

        docs = asyncio.run(load_notes(notes_dir, sync_state_path=state))
        assert len(docs) == 2

    def test_mixes_types_across_directories(self, tmp_path: Path):
        """Files of different types spread across directories are all loaded."""
        notes_dir = tmp_path / "notes"
        notes_dir.mkdir()
        (notes_dir / "a.txt").write_text("txt")
        sub = notes_dir / "sub"
        sub.mkdir()
        (sub / "b.md").write_text("# MD")
        pdf_bytes = b"pdf"
        (sub / "c.pdf").write_bytes(pdf_bytes)
        state = tmp_path / "state.json"

        interpreter = FakeFileInterpreter("pdf text")
        docs = asyncio.run(
            load_notes(notes_dir, sync_state_path=state, interpreter=interpreter)
        )
        assert len(docs) == 3
        suffixes = {Path(d.source).suffix for d in docs}
        assert suffixes == {".txt", ".md", ".pdf"}
