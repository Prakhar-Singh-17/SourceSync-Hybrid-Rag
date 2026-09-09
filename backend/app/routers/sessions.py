"""Session lifecycle: start one, check it, or clear its indexed sources."""

from fastapi import APIRouter, Depends, Request, Response

from app.config import Settings
from app.deps import current_session, get_pipeline, settings_dependency
from app.schemas import SessionResponse
from app.sessions import COOKIE_NAME, Session, decode, encode, new_session
from app.services.pipeline import Pipeline

router = APIRouter(prefix="/api/session", tags=["session"])


@router.post("", response_model=SessionResponse)
async def start_session(
    request: Request,
    response: Response,
    settings: Settings = Depends(settings_dependency),
) -> SessionResponse:
    """Return the current session, creating one if the cookie is missing or expired."""
    session = decode(request.cookies.get(COOKIE_NAME), settings.signing_secret) or new_session(
        settings.session_ttl_minutes
    )
    _set_cookie(response, session, settings)
    return SessionResponse(
        expires_at=session.expires_at.isoformat(),
        passage_count=await _count(request, session),
    )


@router.get("", response_model=SessionResponse)
async def read_session(
    request: Request,
    session: Session = Depends(current_session),
) -> SessionResponse:
    return SessionResponse(
        expires_at=session.expires_at.isoformat(),
        passage_count=await _count(request, session),
    )


@router.delete("", response_model=SessionResponse)
async def clear_session(
    session: Session = Depends(current_session),
    pipeline: Pipeline = Depends(get_pipeline),
) -> SessionResponse:
    """Delete everything this session indexed, keeping the session itself."""
    await pipeline.clear(session.id)
    return SessionResponse(expires_at=session.expires_at.isoformat(), passage_count=0)


def _set_cookie(response: Response, session: Session, settings: Settings) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=encode(session, settings.signing_secret),
        max_age=session.max_age_seconds,
        httponly=True,
        # A browser only sends a cookie on a cross-origin fetch when it is
        # marked SameSite=None, and only accepts that combination over HTTPS.
        # Local development is same-site over plain HTTP, so it uses Lax.
        samesite="none" if settings.session_cookie_secure else "lax",
        secure=settings.session_cookie_secure,
    )


async def _count(request: Request, session: Session) -> int:
    """Best-effort passage count; a session is still usable if Qdrant is down."""
    pipeline: Pipeline | None = getattr(request.app.state, "pipeline", None)
    if pipeline is None:
        return 0
    try:
        return await pipeline.passage_count(session.id)
    except Exception:
        return 0
