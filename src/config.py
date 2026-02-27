from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Server
    host: str = "0.0.0.0"
    port: int = 9002
    log_level: str = "WARNING"

    # Vector store — chroma_path=None uses in-memory mode
    chroma_path: str | None = None
    chroma_collection: str = "lexora"
    embedding_dimension: int = 768

    # Chunker
    chunk_size: int = 500
    chunk_overlap: int = 50

    # Embedding model
    gemini_embedding_model: str = "models/text-embedding-004"
    google_api_key: str | None = None

    # Notes loader
    notes_dir: str = "./data/notes"
    notes_sync_state_path: str = "./data/notes_sync.json"

    # Bookmarks loader
    bookmarks_profile_path: str | None = None  # None = auto-detect
    bookmarks_sync_state_path: str = "./data/bm_sync.json"
    bookmarks_fetch_timeout: int = 15
    bookmarks_max_content_length: int = 50000

    # Feed
    feed_data_file: str = "./data/feeds.yaml"
    feed_max_posts_per_feed: int = 50
    feed_fetch_timeout_sec: int = 10
    feed_default_range: str = "last_month"

    # LLM
    llm_model: str = "google-gla:gemini-2.0-flash"
