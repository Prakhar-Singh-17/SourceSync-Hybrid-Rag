from fastapi import APIRouter, Depends, Response

from app.sessions import set_session_cookie, session_cookie
from app.state import session_store, settings


router = APIRouter(prefix="/api/session", tags=["sessions"])


@router.post("")
async def create_session(response: Response, cookie: str | None = Depends(session_cookie)) -> dict[str, str]:
    session = session_store.get_or_create(cookie)
    set_session_cookie(response, session, secure=settings.session_cookie_secure)
    return {"status": "ok", "expires_at": session.expires_at.isoformat()}


@router.get("")
async def get_session(cookie: str | None = Depends(session_cookie)) -> dict[str, str]:
    session = session_store.require(cookie)
    return {"status": "ok", "expires_at": session.expires_at.isoformat()}
