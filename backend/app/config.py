"""Application configuration.

Every tuning knob that affects retrieval quality is here rather than scattered
as constants through the code, so the behaviour of the system can be changed and
described without reading it.
"""

import logging
import secrets
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# Resolved from this file rather than the working directory, so the app starts
# the same way from the repository root, from backend/, or under a process
# manager that chose its own working directory.
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"

# Used only when SESSION_SECRET is unset. Regenerated on every process start,
# which invalidates existing cookies on restart -- fine locally, wrong in
# production, hence the warning at startup.
_EPHEMERAL_SECRET = secrets.token_urlsafe(32)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- credentials ---------------------------------------------------------
    qdrant_url: str | None = None
    qdrant_api_key: str | None = None
    gemini_api_key: str | None = None

    # --- models --------------------------------------------------------------
    embedding_model: str = "gemini-embedding-2"
    # The -lite model is the default deliberately. Free-tier request quotas are
    # per model per day, and the full gemini-3.5-flash allows only 20 generate
    # calls a day -- roughly ten questions once reranking is counted. The lite
    # model has far more headroom, and answers here are tightly constrained by
    # the supplied sources, which is the case lite models handle well.
    gemini_model: str = "gemini-3.5-flash-lite"
    # Optional: run reranking on a different (cheaper) model than answering.
    # Falls back to gemini_model when unset.
    rerank_model: str | None = None

    # The embedding model emits 3072 numbers per passage by default. It supports
    # truncation to shorter widths that stay usable for retrieval, and 768 makes
    # every vector four times smaller -- the difference between fitting a free
    # Qdrant cluster and not.
    embedding_dimensions: int = 768

    # Concurrent embedding requests during ingestion. Higher finishes sooner but
    # runs into the free tier's per-minute rate limit, which costs more time in
    # backoff than the concurrency saved.
    embedding_concurrency: int = 4

    # --- storage -------------------------------------------------------------
    qdrant_collection: str = "sourcesync_hybrid"
    max_session_passages: int = 4_000

    # --- retrieval tuning ----------------------------------------------------
    # How many passages each of the two searches returns before fusion. Larger
    # gives fusion and the reranker more to work with, at the cost of a bigger
    # rerank prompt.
    retrieval_candidates: int = 20
    # How many survive reranking and are actually shown to the model.
    context_passages: int = 6
    # Deliberately generous: the answer format asks for an explanation, and too
    # small a budget truncates answers mid-sentence.
    answer_max_tokens: int = 1_200
    # Gemini can reason before answering. A budget of 0 disables it (fastest and
    # cheapest) but the -lite models reject that with HTTP 400, so the default of
    # -1 means "send no thinking setting at all and let the model decide", which
    # is the only value safe on every model.
    answer_thinking_budget: int = -1

    # --- web -----------------------------------------------------------------
    cors_origins: str = "http://localhost:5173"
    session_ttl_minutes: int = 60
    session_cookie_secure: bool = False
    session_secret: str | None = None

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def signing_secret(self) -> str:
        return self.session_secret or _EPHEMERAL_SECRET

    @property
    def missing_credentials(self) -> list[str]:
        names = {
            "GEMINI_API_KEY": self.gemini_api_key,
            "QDRANT_URL": self.qdrant_url,
            "QDRANT_API_KEY": self.qdrant_api_key,
        }
        return [name for name, value in names.items() if not value]

    def warn_about_gaps(self) -> None:
        if self.missing_credentials:
            logger.warning(
                "Missing configuration: %s. Ingestion and querying will return 503.",
                ", ".join(self.missing_credentials),
            )
        if not self.session_secret:
            logger.warning(
                "SESSION_SECRET is not set; using a random per-process secret. "
                "Sessions will not survive a restart."
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()
