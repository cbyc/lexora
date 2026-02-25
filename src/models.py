from dataclasses import dataclass
from pydantic import BaseModel, Field, model_validator


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


NOT_FOUND = "I couldn't find relevant information."


class AskResponse(BaseModel):
    text: str
    sources: list[str]

    @model_validator(mode="after")
    def sources_required_when_answered(self) -> "AskResponse":
        if not self.sources and self.text != NOT_FOUND:
            raise ValueError("sources must not be empty when an answer is provided")
        return self
