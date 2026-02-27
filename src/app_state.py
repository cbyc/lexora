from typing import NamedTuple

from src.knowledge.pipeline import Pipeline
from src.feed.service import FeedService


class AppState(NamedTuple):
    pipeline: Pipeline
    feed_service: FeedService
