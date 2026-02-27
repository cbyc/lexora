from typing import NamedTuple

from knowledge.pipeline import Pipeline
from feed.service import FeedService


class AppState(NamedTuple):
    pipeline: Pipeline
    feed_service: FeedService
