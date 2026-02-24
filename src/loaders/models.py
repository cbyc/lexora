from dataclasses import dataclass


@dataclass
class Document:
    content: str
    source: str  # file path for notes, URL for bookmarks
