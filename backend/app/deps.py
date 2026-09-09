"""FastAPI dependencies.

The expensive objects -- HTTP clients to Gemini and Qdrant -- are built once
during startup and handed to every request from here.  The previous version
constructed a fresh Qdrant client and three separate Gemini clients on every
single request, which meant a new connection pool and TLS handshake per
question.
"""

from fastapi import HTTPException, Request, status

from app.config import Settings, get_settings
from app.sessions import COOKIE_NAME, Session, decode
from app.services.pipeline import Pipeline


def settings_dependency() -> Settings:
    return get_settings()


def get_pipeline(request: Request) -> Pipeline:
    """Return the shared pipeline, or explain what configuration is missing."""
    pipeline: Pipeline | None = getattr(request.app.state, "pipeline", None)
    if pipeline is None:
        missing = ", ".join(get_settings().missing_credentials) or "credentials"
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"The server is missing configuration: {missing}.",
        )
    return pipeline


def current_session(request: Request) -> Session:
    """Require a valid, unexpired session cookie."""
    session = decode(request.cookies.get(COOKIE_NAME), get_settings().signing_secret)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your session has expired. Reload the page to start a new one.",
        )
    return session
