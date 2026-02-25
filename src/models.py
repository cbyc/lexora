from dataclasses import dataclass
from pydantic import BaseModel, Field


@dataclass
class Chunk:
    text: str
    source: str  # file path or URL
    chunk_index: int


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1024)


class ReindexResponse(BaseModel):
    notes_indexed: int
    bookmarks_indexed: int
