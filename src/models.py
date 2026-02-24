from dataclasses import dataclass
from pydantic import BaseModel, Field


@dataclass
class Chunk:
    text: str
    source: str  # file path or URL
    chunk_index: int


class QueryRequest(BaseModel):
    question: str = Field(min_length=1)
