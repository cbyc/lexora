"""Shared sync state helpers for incremental loaders."""

import json
from pathlib import Path


def load_sync_state(sync_state_path: str | Path) -> float | None:
    """Load the last sync timestamp from the sync state file.

    Args:
        sync_state_path: Path to the sync state JSON file.

    Returns:
        The last sync timestamp, or None if no state exists.
    """
    path = Path(sync_state_path)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        return data.get("last_sync_timestamp")
    except (json.JSONDecodeError, OSError):
        return None


def save_sync_state(sync_state_path: str | Path, timestamp: float) -> None:
    """Save the sync timestamp to the state file.

    Args:
        sync_state_path: Path to the sync state JSON file.
        timestamp: The timestamp to save.
    """
    path = Path(sync_state_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"last_sync_timestamp": timestamp}, indent=2))
