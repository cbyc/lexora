from dataclasses import dataclass
from datetime import datetime


@dataclass
class Feed:
    name: str
    url: str


@dataclass
class Post:
    feed_name: str
    title: str
    url: str
    published_at: datetime


@dataclass
class FeedError:
    feed_name: str
    url: str
    error: str


class DuplicateFeedError(Exception):
    pass
