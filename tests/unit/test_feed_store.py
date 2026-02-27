"""Tests for YamlFeedStore."""

from pathlib import Path

import pytest

from feed.models import DuplicateFeedError, Feed
from feed.store import YamlFeedStore


class TestYamlFeedStore:
    def test_missing_file_returns_empty_list(self, tmp_path: Path):
        """load_feeds should return an empty list when the data file does not exist."""
        store = YamlFeedStore(tmp_path / "feeds.yaml")
        assert store.load_feeds() == []

    def test_empty_file_returns_empty_list(self, tmp_path: Path):
        """load_feeds should return an empty list for an empty YAML file."""
        path = tmp_path / "feeds.yaml"
        path.write_text("")
        store = YamlFeedStore(path)
        assert store.load_feeds() == []

    def test_valid_yaml_parses_feeds(self, tmp_path: Path):
        """load_feeds should parse a valid YAML file into Feed objects."""
        path = tmp_path / "feeds.yaml"
        path.write_text(
            "feeds:\n  - name: Tech\n    url: https://tech.example.com/rss\n"
        )
        store = YamlFeedStore(path)
        feeds = store.load_feeds()
        assert len(feeds) == 1
        assert feeds[0].name == "Tech"
        assert feeds[0].url == "https://tech.example.com/rss"

    def test_save_and_load_round_trip(self, tmp_path: Path):
        """Feeds saved by save_feeds should be recovered by load_feeds."""
        path = tmp_path / "feeds.yaml"
        store = YamlFeedStore(path)
        feeds = [
            Feed(name="Feed A", url="https://a.example.com/rss"),
            Feed(name="Feed B", url="https://b.example.com/rss"),
        ]
        store.save_feeds(feeds)
        loaded = store.load_feeds()
        assert len(loaded) == 2
        assert loaded[0].name == "Feed A"
        assert loaded[1].url == "https://b.example.com/rss"

    def test_add_new_feed(self, tmp_path: Path):
        """add_feed should append a new feed to the store."""
        path = tmp_path / "feeds.yaml"
        store = YamlFeedStore(path)
        store.add_feed(Feed(name="New Feed", url="https://new.example.com/rss"))
        feeds = store.load_feeds()
        assert len(feeds) == 1
        assert feeds[0].name == "New Feed"

    def test_add_duplicate_url_raises(self, tmp_path: Path):
        """add_feed should raise DuplicateFeedError when the URL already exists."""
        path = tmp_path / "feeds.yaml"
        store = YamlFeedStore(path)
        feed = Feed(name="Feed A", url="https://example.com/rss")
        store.add_feed(feed)
        with pytest.raises(DuplicateFeedError):
            store.add_feed(Feed(name="Feed A Duplicate", url="https://example.com/rss"))

    def test_ensure_data_file_creates_file(self, tmp_path: Path):
        """ensure_data_file should create the file if it does not exist."""
        path = tmp_path / "subdir" / "feeds.yaml"
        store = YamlFeedStore(path)
        store.ensure_data_file()
        assert path.exists()

    def test_ensure_data_file_preserves_existing(self, tmp_path: Path):
        """ensure_data_file should not overwrite an existing file."""
        path = tmp_path / "feeds.yaml"
        path.write_text(
            "feeds:\n  - name: Existing\n    url: https://example.com/rss\n"
        )
        store = YamlFeedStore(path)
        store.ensure_data_file()
        feeds = store.load_feeds()
        assert len(feeds) == 1
        assert feeds[0].name == "Existing"
