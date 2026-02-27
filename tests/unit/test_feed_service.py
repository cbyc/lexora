"""Tests for FeedService application layer."""

import asyncio
from datetime import datetime, timezone

import pytest

from src.feed.models import DuplicateFeedError, Feed, FeedError, Post
from src.feed.service import FeedService


class FakeFeedStore:
    def __init__(self, feeds: list[Feed] | None = None):
        self._feeds = feeds or []
        self.saved: list[Feed] = []

    def load_feeds(self) -> list[Feed]:
        return list(self._feeds)

    def save_feeds(self, feeds: list[Feed]) -> None:
        self._feeds = list(feeds)

    def add_feed(self, feed: Feed) -> None:
        for existing in self._feeds:
            if existing.url == feed.url:
                raise DuplicateFeedError(f"Feed with URL '{feed.url}' already exists")
        self._feeds.append(feed)

    def ensure_data_file(self) -> None:
        pass


class FakeFeedFetcher:
    def __init__(
        self,
        posts: list[Post] | None = None,
        errors: list[FeedError] | None = None,
        validate_raises: Exception | None = None,
    ):
        self._posts = posts or []
        self._errors = errors or []
        self._validate_raises = validate_raises

    async def fetch_feed(
        self, feed_name: str, feed_url: str, max_posts: int
    ) -> list[Post]:
        return list(self._posts)

    async def validate_feed(self, name: str, url: str) -> None:
        if self._validate_raises is not None:
            raise self._validate_raises

    async def fetch_all_feeds(
        self, feeds: list[Feed], max_posts_per_feed: int, timeout: float
    ) -> tuple[list[Post], list[FeedError]]:
        return list(self._posts), list(self._errors)


def make_post(feed_name: str, title: str, published_at: datetime) -> Post:
    return Post(
        feed_name=feed_name,
        title=title,
        url=f"https://example.com/{title}",
        published_at=published_at,
    )


class TestFeedServiceGetPosts:
    def test_returns_posts_and_errors(self):
        """get_posts should return posts and errors from fetcher."""
        post = make_post(
            "Feed A", "Article", datetime(2026, 2, 20, tzinfo=timezone.utc)
        )
        error = FeedError("Bad Feed", "https://bad.com/rss", "timeout")
        service = FeedService(
            store=FakeFeedStore([Feed("Feed A", "https://a.com/rss")]),
            fetcher=FakeFeedFetcher(posts=[post], errors=[error]),
        )
        result = asyncio.run(
            service.get_posts("last_month", "", "", "last_month", 50, 10.0)
        )
        assert len(result.posts) == 1
        assert len(result.errors) == 1

    def test_date_filtering_excludes_old_posts(self):
        """Posts before the from date should be filtered out."""
        old_post = make_post("Feed A", "Old", datetime(2020, 1, 1, tzinfo=timezone.utc))
        service = FeedService(
            store=FakeFeedStore([Feed("Feed A", "https://a.com/rss")]),
            fetcher=FakeFeedFetcher(posts=[old_post]),
        )
        result = asyncio.run(
            service.get_posts("last_month", "", "", "last_month", 50, 10.0)
        )
        assert result.posts == []

    def test_no_feeds_returns_empty(self):
        """With no feeds configured, get_posts returns empty posts and errors."""
        service = FeedService(
            store=FakeFeedStore([]),
            fetcher=FakeFeedFetcher(),
        )
        result = asyncio.run(
            service.get_posts("last_month", "", "", "last_month", 50, 10.0)
        )
        assert result.posts == []
        assert result.errors == []


class TestFeedServiceAddFeed:
    def test_add_feed_validates_then_saves(self):
        """add_feed should validate the URL and then store the feed."""
        store = FakeFeedStore()
        service = FeedService(store=store, fetcher=FakeFeedFetcher())
        asyncio.run(service.add_feed("New Feed", "https://new.example.com/rss"))
        feeds = store.load_feeds()
        assert len(feeds) == 1
        assert feeds[0].name == "New Feed"

    def test_add_feed_duplicate_raises_duplicate_feed_error(self):
        """add_feed should raise DuplicateFeedError for a duplicate URL."""
        store = FakeFeedStore([Feed("Existing", "https://existing.com/rss")])
        service = FeedService(store=store, fetcher=FakeFeedFetcher())
        with pytest.raises(DuplicateFeedError):
            asyncio.run(service.add_feed("Duplicate", "https://existing.com/rss"))

    def test_add_feed_invalid_url_raises_value_error(self):
        """add_feed should raise ValueError when the URL is not a valid feed."""
        store = FakeFeedStore()
        fetcher = FakeFeedFetcher(validate_raises=ValueError("not a valid feed"))
        service = FeedService(store=store, fetcher=fetcher)
        with pytest.raises(ValueError, match="not a valid feed"):
            asyncio.run(service.add_feed("Bad Feed", "https://bad.example.com/rss"))
