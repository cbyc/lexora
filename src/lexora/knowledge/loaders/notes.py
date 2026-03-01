"""Unified notes loader — loads .txt, .md, and .pdf files recursively."""

import re
import time
from pathlib import Path

import mistune
import structlog

from lexora.knowledge.loaders.sync_state import load_sync_state, save_sync_state
from lexora.knowledge.loaders.models import Document
from lexora.ports import FileInterpreter

logger = structlog.get_logger(__name__)

_PDF_SYSTEM_PROMPT = (
    "Extract and summarise all meaningful content from this PDF. "
    "Return plain text only, preserving all key information, facts, and ideas."
)
_WORD_SYSTEM_PROMPT = (
    "Extract all text content from this Word document. "
    "Return plain text preserving all key information, headings, paragraphs, and lists."
)
_EXCEL_SYSTEM_PROMPT = (
    "Extract all data from this Excel spreadsheet. "
    "Return the content as plain text, representing each sheet, row, and cell value clearly."
)
_IMAGE_SYSTEM_PROMPT = (
    "Describe all meaningful content visible in this image. "
    "Include any text, data, diagrams, or key visual information as plain text."
)

_INTERPRETER_PROMPTS: dict[str, str] = {
    ".pdf": _PDF_SYSTEM_PROMPT,
    ".docx": _WORD_SYSTEM_PROMPT,
    ".xlsx": _EXCEL_SYSTEM_PROMPT,
    ".png": _IMAGE_SYSTEM_PROMPT,
    ".jpg": _IMAGE_SYSTEM_PROMPT,
    ".jpeg": _IMAGE_SYSTEM_PROMPT,
}
_SUPPORTED_SUFFIXES = {".txt", ".md"} | set(_INTERPRETER_PROMPTS)

_md_parser = mistune.create_markdown()


def _md_to_plain(text: str) -> str:
    """Convert markdown to plain text by rendering to HTML then stripping tags."""
    html = _md_parser(text)
    plain = re.sub(r"<[^>]+>", " ", html)
    plain = re.sub(r"\s+", " ", plain).strip()
    return plain


async def load_notes(
    directory: str | Path,
    sync_state_path: str | Path = "data/notes_sync.json",
    interpreter: FileInterpreter | None = None,
) -> list[Document]:
    """Load new or modified .txt, .md, .pdf, .docx, .xlsx, .png, .jpg, .jpeg files from a directory tree.

    Traverses the directory and all subdirectories. On first run, loads all
    supported files. On subsequent runs, only loads files whose modification
    time is newer than the last sync timestamp.

    Args:
        directory: Root directory to search.
        sync_state_path: Path to the sync state JSON file.
        interpreter: Optional FileInterpreter for PDF, Word, Excel, and image files.
            These files are skipped with a warning when interpreter is None.

    Returns:
        List of Document objects for new or modified files.

    Raises:
        FileNotFoundError: If the directory does not exist.
    """
    dir_path = Path(directory)
    if not dir_path.exists():
        raise FileNotFoundError(f"Directory not found: {dir_path}")

    state_path = Path(sync_state_path)
    last_sync = load_sync_state(state_path)
    now = time.time()

    documents = []
    for file_path in sorted(dir_path.rglob("*")):
        if not file_path.is_file():
            continue
        suffix = file_path.suffix.lower()
        if suffix not in _SUPPORTED_SUFFIXES:
            continue
        if last_sync is not None and file_path.stat().st_mtime <= last_sync:
            continue

        if suffix == ".txt":
            documents.append(
                Document(content=file_path.read_text(), source=str(file_path))
            )
        elif suffix == ".md":
            plain = _md_to_plain(file_path.read_text())
            documents.append(Document(content=plain, source=str(file_path)))
        elif suffix in _INTERPRETER_PROMPTS:
            if interpreter is None:
                logger.warning("file_skipped_no_interpreter", path=str(file_path))
                continue
            text = await interpreter.interpret(
                file_bytes=file_path.read_bytes(),
                filename=file_path.name,
                system_prompt=_INTERPRETER_PROMPTS[suffix],
            )
            documents.append(Document(content=text, source=str(file_path)))

    save_sync_state(state_path, now)
    return documents
