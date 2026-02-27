"""RSS/Atom feed fetcher using httpx and feedparser."""

import asyncio
from datetime import datetime, timezone

import feedparser
import httpx

from feed.models import Feed, FeedError, Post

EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


class HttpFeedFetcher:
    def __init__(self, transport: httpx.AsyncBaseTransport | None = None):
        self._transport = transport

    def _parse_timestamp(self, entry) -> datetime:
        if entry.get("published_parsed"):
            return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        if entry.get("updated_parsed"):
            return datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
        return EPOCH

    async def fetch_feed(
        self, feed_name: str, feed_url: str, max_posts: int
    ) -> list[Post]:
        async with httpx.AsyncClient(transport=self._transport) as client:
            response = await client.get(feed_url)
            response.raise_for_status()
            content = response.text

        parsed = await asyncio.to_thread(feedparser.parse, content)
        if not parsed.version:
            raise ValueError(f"URL '{feed_url}' is not a valid feed")

        posts = []
        for entry in parsed.entries[:max_posts]:
            posts.append(
                Post(
                    feed_name=feed_name,
                    title=entry.get("title", ""),
                    url=entry.get("link", ""),
                    published_at=self._parse_timestamp(entry),
                )
            )
        return posts

    async def validate_feed(self, name: str, url: str) -> None:
        await self.fetch_feed(name, url, max_posts=1)

    async def fetch_all_feeds(
        self, feeds: list[Feed], max_posts_per_feed: int, timeout: float
    ) -> tuple[list[Post], list[FeedError]]:
        async def fetch_one(feed: Feed) -> tuple[list[Post], FeedError | None]:
            try:
                posts = await asyncio.wait_for(
                    self.fetch_feed(feed.name, feed.url, max_posts_per_feed),
                    timeout=timeout,
                )
                return posts, None
            except Exception as exc:
                return [], FeedError(feed_name=feed.name, url=feed.url, error=str(exc))

        results = await asyncio.gather(*(fetch_one(f) for f in feeds))

        all_posts: list[Post] = []
        all_errors: list[FeedError] = []
        for posts, error in results:
            all_posts.extend(posts)
            if error is not None:
                all_errors.append(error)

        all_posts.sort(key=lambda p: p.published_at, reverse=True)
        return all_posts, all_errors
