from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Server
    host: str = "0.0.0.0"
    port: int = 9002
    log_level: str = "WARNING"

    # Vector store — qdrant_url=None uses in-memory mode
    qdrant_url: str | None = None
    qdrant_collection: str = "lexora"
    embedding_dimension: int = 384

    # Chunker
    chunk_size: int = 500
    chunk_overlap: int = 50

    # Embedding model
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"

    # Notes loader
    notes_dir: str = "./data/notes"
    notes_sync_state_path: str = "./data/notes_sync.json"

    # Bookmarks loader
    bookmarks_profile_path: str | None = None  # None = auto-detect
    bookmarks_sync_state_path: str = "./data/bm_sync.json"
    bookmarks_fetch_timeout: int = 15
    bookmarks_max_content_length: int = 50000

    # LLM
    llm_model: str = "google-gla:gemini-2.0-flash"
