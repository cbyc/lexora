from typing import Protocol
from src.models import AskResponse, Chunk
from src.feed.models import Feed, FeedError, Post


class Chunker(Protocol):
    def chunk(self, text: str) -> list[str]: ...


class EmbeddingModel(Protocol):
    async def encode(self, text: str) -> list[float]: ...


class DocumentStore(Protocol):
    def ensure_collection(self) -> None: ...

    def add_chunks(
        self, chunks: list[Chunk], embeddings: list[list[float]]
    ) -> None: ...

    def search(
        self, query_embedding: list[float], top_k: int = 5, score_threshold: float = 0.0
    ) -> list[Chunk]: ...


class AskAgent(Protocol):
    async def answer(self, question: str, chunks: list[Chunk]) -> AskResponse: ...


class FeedStore(Protocol):
    def load_feeds(self) -> list[Feed]: ...

    def save_feeds(self, feeds: list[Feed]) -> None: ...

    def add_feed(self, feed: Feed) -> None: ...

    def ensure_data_file(self) -> None: ...


class FeedFetcher(Protocol):
    async def fetch_feed(
        self, feed_name: str, feed_url: str, max_posts: int
    ) -> list[Post]: ...

    async def validate_feed(self, name: str, url: str) -> None: ...

    async def fetch_all_feeds(
        self, feeds: list[Feed], max_posts_per_feed: int, timeout: float
    ) -> tuple[list[Post], list[FeedError]]: ...
