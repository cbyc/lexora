"""Notes loader — loads .txt files from a directory as Documents."""

import time
from pathlib import Path

from knowledge.loaders.sync_state import load_sync_state, save_sync_state
from knowledge.loaders.models import Document


def load_notes(
    directory: str | Path,
    sync_state_path: str | Path = "data/notes_sync_state.json",
) -> list[Document]:
    """Load new or modified .txt files from a directory since the last sync.

    On first run, loads all files. On subsequent runs, only loads files
    whose modification time is newer than the last sync timestamp.

    Args:
        directory: Path to the directory containing .txt files.
        sync_state_path: Path to the sync state JSON file.

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
    for file_path in sorted(dir_path.glob("*.txt")):
        if last_sync is None or file_path.stat().st_mtime > last_sync:
            documents.append(
                Document(content=file_path.read_text(), source=str(file_path))
            )

    save_sync_state(state_path, now)
    return documents
