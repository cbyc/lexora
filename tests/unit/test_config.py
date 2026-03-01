"""Tests for Settings defaults and path expansion."""

import os
from pathlib import Path

from lexora.config import Settings

_HOME = Path.home()


def _defaults(**overrides) -> Settings:
    """Create Settings with no .env so only defaults and overrides apply."""
    return Settings(_env_file=None, **overrides)


class TestSettingsDefaults:
    def test_gemini_embedding_model(self):
        assert _defaults().gemini_embedding_model == "models/text-embedding-004"

    def test_chroma_path_points_to_config_dir(self):
        assert _defaults().chroma_path == str(_HOME / ".config/lexora/chroma")

    def test_notes_dir_points_to_config_dir(self):
        assert _defaults().notes_dir == str(_HOME / ".config/lexora/notes")

    def test_notes_sync_state_path_points_to_config_dir(self):
        assert _defaults().notes_sync_state_path == str(
            _HOME / ".config/lexora/notes_sync.json"
        )

    def test_bookmarks_sync_state_path_points_to_config_dir(self):
        assert _defaults().bookmarks_sync_state_path == str(
            _HOME / ".config/lexora/bookmarks_sync.json"
        )

    def test_feed_data_file_points_to_config_dir(self):
        assert _defaults().feed_data_file == str(_HOME / ".config/lexora/feeds.yaml")

    def test_feed_default_range_is_last_week(self):
        assert _defaults().feed_default_range == "last_week"


class TestSettingsPathExpansion:
    def test_tilde_in_chroma_path_is_expanded(self):
        s = _defaults(chroma_path="~/custom/chroma")
        assert not s.chroma_path.startswith("~")
        assert s.chroma_path == os.path.expanduser("~/custom/chroma")

    def test_tilde_in_notes_dir_is_expanded(self):
        s = _defaults(notes_dir="~/my/notes")
        assert not s.notes_dir.startswith("~")
        assert s.notes_dir == os.path.expanduser("~/my/notes")

    def test_tilde_in_notes_sync_state_path_is_expanded(self):
        s = _defaults(notes_sync_state_path="~/my/sync.json")
        assert not s.notes_sync_state_path.startswith("~")

    def test_tilde_in_bookmarks_sync_state_path_is_expanded(self):
        s = _defaults(bookmarks_sync_state_path="~/bm_sync.json")
        assert not s.bookmarks_sync_state_path.startswith("~")

    def test_tilde_in_feed_data_file_is_expanded(self):
        s = _defaults(feed_data_file="~/feeds.yaml")
        assert not s.feed_data_file.startswith("~")

    def test_none_chroma_path_stays_none(self):
        assert _defaults(chroma_path=None).chroma_path is None

    def test_relative_path_without_tilde_is_unchanged(self):
        s = _defaults(notes_dir="./data/notes")
        assert s.notes_dir == "./data/notes"
