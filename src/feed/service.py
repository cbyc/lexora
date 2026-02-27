"""FeedService application layer — orchestrates store and fetcher."""

from feed.date_range import parse_date_range
from feed.models import Feed, FeedError, Post
from ports import FeedFetcher, FeedStore


class FeedResult:
    def __init__(self, posts: list[Post], errors: list[FeedError]):
        self.posts = posts
        self.errors = errors


class FeedService:
    def __init__(
        self,
        store: FeedStore,
        fetcher: FeedFetcher,
        default_range: str = "last_month",
        max_posts_per_feed: int = 50,
        timeout: float = 10.0,
    ):
        self._store = store
        self._fetcher = fetcher
        self._default_range = default_range
        self._max_posts_per_feed = max_posts_per_feed
        self._timeout = timeout

    async def get_posts(
        self,
        range_param: str,
        from_param: str,
        to_param: str,
        default_range: str | None = None,
        max_posts_per_feed: int | None = None,
        timeout: float | None = None,
    ) -> FeedResult:
        feeds = self._store.load_feeds()
        if not feeds:
            return FeedResult(posts=[], errors=[])

        from_dt, to_dt = parse_date_range(
            range_param,
            from_param,
            to_param,
            default_range or self._default_range,
        )

        posts, errors = await self._fetcher.fetch_all_feeds(
            feeds,
            max_posts_per_feed or self._max_posts_per_feed,
            timeout or self._timeout,
        )

        filtered = [
            p
            for p in posts
            if (from_dt is None or p.published_at >= from_dt)
            and (to_dt is None or p.published_at <= to_dt)
        ]

        return FeedResult(posts=filtered, errors=errors)

    async def add_feed(self, name: str, url: str) -> Feed:
        await self._fetcher.validate_feed(name, url)
        feed = Feed(name=name, url=url)
        self._store.add_feed(feed)
        return feed
