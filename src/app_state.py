from typing import NamedTuple

from knowledge.pipeline import Pipeline
from feed.service import FeedService
from ports import FileInterpreter


class AppState(NamedTuple):
    pipeline: Pipeline | None
    feed_service: FeedService
    file_interpreter: FileInterpreter | None = None
