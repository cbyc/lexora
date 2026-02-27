"""Tests for feed domain data models."""

from datetime import datetime

from src.feed.models import DuplicateFeedError, Feed, FeedError, Post


class TestFeedModels:
    def test_feed_creation(self):
        """Feed dataclass should store name and url."""
        feed = Feed(name="Tech News", url="https://example.com/rss")
        assert feed.name == "Tech News"
        assert feed.url == "https://example.com/rss"

    def test_post_creation(self):
        """Post dataclass should store all fields."""
        published = datetime(2024, 1, 15, 12, 0)
        post = Post(
            feed_name="Tech News",
            title="New Article",
            url="https://example.com/article",
            published_at=published,
        )
        assert post.feed_name == "Tech News"
        assert post.title == "New Article"
        assert post.url == "https://example.com/article"
        assert post.published_at == published

    def test_feed_error_creation(self):
        """FeedError dataclass should store feed_name, url, and error message."""
        error = FeedError(
            feed_name="Bad Feed",
            url="https://broken.com/rss",
            error="Connection timeout",
        )
        assert error.feed_name == "Bad Feed"
        assert error.url == "https://broken.com/rss"
        assert error.error == "Connection timeout"

    def test_duplicate_feed_error_is_exception(self):
        """DuplicateFeedError must be a subclass of Exception."""
        assert issubclass(DuplicateFeedError, Exception)

    def test_duplicate_feed_error_can_be_raised(self):
        """DuplicateFeedError must be raiseable with a message."""
        import pytest

        with pytest.raises(DuplicateFeedError, match="already exists"):
            raise DuplicateFeedError("Feed already exists")
