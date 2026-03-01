from typing import NamedTuple

from lexora.knowledge.pipeline import Pipeline
from lexora.feed.service import FeedService
from lexora.ports import FileInterpreter


class AppState(NamedTuple):
    pipeline: Pipeline | None
    feed_service: FeedService
    file_interpreter: FileInterpreter | None = None
