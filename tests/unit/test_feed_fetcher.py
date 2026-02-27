"""Tests for HttpFeedFetcher — RSS fetching using mocked HTTP transport."""

import asyncio
from datetime import datetime, timezone

import httpx
import pytest

from src.feed.fetcher import HttpFeedFetcher
from src.feed.models import Feed

SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <item>
      <title>Post One</title>
      <link>https://example.com/1</link>
      <pubDate>Mon, 16 Feb 2026 10:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Post Two</title>
      <link>https://example.com/2</link>
      <pubDate>Sun, 15 Feb 2026 09:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Post Three</title>
      <link>https://example.com/3</link>
      <pubDate>Sat, 14 Feb 2026 08:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>"""

NOT_FEED_HTML = "<html><body>Not a feed</body></html>"


def make_transport(content: str, status_code: int = 200):
    """Create an httpx.MockTransport that serves the given content."""
    return httpx.MockTransport(
        lambda request: httpx.Response(
            status_code=status_code,
            content=content.encode(),
            headers={"Content-Type": "application/rss+xml"},
        )
    )


class TestFetchFeed:
    def test_valid_rss_returns_posts(self):
        """fetch_feed should return Post objects from valid RSS."""
        fetcher = HttpFeedFetcher(transport=make_transport(SAMPLE_RSS))
        posts = asyncio.run(
            fetcher.fetch_feed("Test Feed", "https://example.com/rss", max_posts=10)
        )
        assert len(posts) == 3
        assert posts[0].title == "Post One"
        assert posts[0].feed_name == "Test Feed"
        assert posts[0].url == "https://example.com/1"

    def test_max_posts_limits_results(self):
        """fetch_feed should return at most max_posts posts."""
        fetcher = HttpFeedFetcher(transport=make_transport(SAMPLE_RSS))
        posts = asyncio.run(
            fetcher.fetch_feed("Test Feed", "https://example.com/rss", max_posts=2)
        )
        assert len(posts) == 2

    def test_published_at_parsed_from_pubdate(self):
        """Posts should have their published_at set from pubDate."""
        fetcher = HttpFeedFetcher(transport=make_transport(SAMPLE_RSS))
        posts = asyncio.run(
            fetcher.fetch_feed("Test Feed", "https://example.com/rss", max_posts=1)
        )
        assert posts[0].published_at != datetime(1970, 1, 1, tzinfo=timezone.utc)

    def test_invalid_content_raises_value_error(self):
        """fetch_feed should raise ValueError for non-feed content."""
        fetcher = HttpFeedFetcher(transport=make_transport(NOT_FEED_HTML))
        with pytest.raises(ValueError, match="not a valid feed"):
            asyncio.run(
                fetcher.fetch_feed("Bad Feed", "https://example.com/bad", max_posts=10)
            )

    def test_http_error_raises(self):
        """fetch_feed should raise an error on non-200 HTTP responses."""
        fetcher = HttpFeedFetcher(transport=make_transport("", status_code=500))
        with pytest.raises(Exception):
            asyncio.run(
                fetcher.fetch_feed("Bad Feed", "https://example.com/bad", max_posts=10)
            )


class TestValidateFeed:
    def test_valid_feed_does_not_raise(self):
        """validate_feed should not raise for a valid RSS URL."""
        fetcher = HttpFeedFetcher(transport=make_transport(SAMPLE_RSS))
        asyncio.run(fetcher.validate_feed("Test Feed", "https://example.com/rss"))

    def test_invalid_feed_raises_value_error(self):
        """validate_feed should raise ValueError for non-feed content."""
        fetcher = HttpFeedFetcher(transport=make_transport(NOT_FEED_HTML))
        with pytest.raises(ValueError):
            asyncio.run(fetcher.validate_feed("Bad Feed", "https://example.com/bad"))


class TestFetchAllFeeds:
    def _make_rss(self, title: str, pub_date: str) -> str:
        return f"""<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <title>{title}</title>
    <item>
      <title>Post from {title}</title>
      <link>https://example.com/{title}</link>
      <pubDate>{pub_date}</pubDate>
    </item>
  </channel>
</rss>"""

    def test_all_succeed_returns_posts_sorted_newest_first(self):
        """fetch_all_feeds returns posts sorted newest-first when all succeed."""
        rss_a = self._make_rss("Feed A", "Mon, 16 Feb 2026 10:00:00 GMT")
        rss_b = self._make_rss("Feed B", "Tue, 17 Feb 2026 10:00:00 GMT")

        call_count = [0]

        def route(request):
            idx = call_count[0] % 2
            call_count[0] += 1
            content = rss_a if idx == 0 else rss_b
            return httpx.Response(200, content=content.encode())

        fetcher = HttpFeedFetcher(transport=httpx.MockTransport(route))
        feeds = [
            Feed(name="A", url="https://a.example.com/rss"),
            Feed(name="B", url="https://b.example.com/rss"),
        ]
        posts, errors = asyncio.run(
            fetcher.fetch_all_feeds(feeds, max_posts_per_feed=50, timeout=5.0)
        )
        assert len(errors) == 0
        assert len(posts) == 2
        # Feed B (newer) should be first
        assert posts[0].published_at >= posts[1].published_at

    def test_partial_failure_returns_posts_and_errors(self):
        """fetch_all_feeds returns posts for good feeds and errors for bad ones."""

        def route(request):
            if "good" in str(request.url):
                return httpx.Response(200, content=SAMPLE_RSS.encode())
            return httpx.Response(500, content=b"Error")

        fetcher = HttpFeedFetcher(transport=httpx.MockTransport(route))
        feeds = [
            Feed(name="Good", url="https://good.example.com/rss"),
            Feed(name="Bad", url="https://bad.example.com/rss"),
        ]
        posts, errors = asyncio.run(
            fetcher.fetch_all_feeds(feeds, max_posts_per_feed=50, timeout=5.0)
        )
        assert len(errors) == 1
        assert errors[0].feed_name == "Bad"
        assert len(posts) > 0

    def test_all_fail_returns_empty_posts_and_errors(self):
        """fetch_all_feeds returns empty posts and non-empty errors when all fail."""
        fetcher = HttpFeedFetcher(transport=make_transport("", status_code=500))
        feeds = [
            Feed(name="Bad1", url="https://bad1.example.com/rss"),
            Feed(name="Bad2", url="https://bad2.example.com/rss"),
        ]
        posts, errors = asyncio.run(
            fetcher.fetch_all_feeds(feeds, max_posts_per_feed=50, timeout=5.0)
        )
        assert posts == []
        assert len(errors) == 2

    def test_empty_feeds_returns_empty(self):
        """fetch_all_feeds returns empty lists for empty feed list."""
        fetcher = HttpFeedFetcher(transport=make_transport(SAMPLE_RSS))
        posts, errors = asyncio.run(
            fetcher.fetch_all_feeds([], max_posts_per_feed=50, timeout=5.0)
        )
        assert posts == []
        assert errors == []
