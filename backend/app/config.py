from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from the repository root .env file."""

    model_config = SettingsConfigDict(
        env_file="../.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    qdrant_url: str | None = None
    qdrant_api_key: str | None = None
    gemini_api_key: str | None = None
    embedding_model: str = "gemini-embedding-2"
    gemini_model: str = "gemini-3.5-flash"
    qdrant_collection: str = "sourcesync_chunks"
    cors_origins: str = "http://localhost:5173"
    session_ttl_minutes: int = 60
    session_cookie_secure: bool = False

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
