from dataclasses import dataclass

@dataclass
class Chunk:
    text: str
    source: str  # file path or URL
    chunk_index: int
