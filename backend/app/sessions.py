from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import secrets

from fastapi import Cookie, HTTPException, Response, status


SESSION_COOKIE_NAME = "sourcesync_session"


@dataclass(frozen=True)
class Session:
    session_id: str
    expires_at: datetime


class SessionStore:
    def __init__(self, ttl_minutes: int) -> None:
        self._ttl = timedelta(minutes=ttl_minutes)
        self._sessions: dict[str, Session] = {}

    def create(self) -> Session:
        now = datetime.now(UTC)
        session = Session(
            session_id=secrets.token_urlsafe(32),
            expires_at=now + self._ttl,
        )
        self._sessions[session.session_id] = session
        return session

    def get_or_create(self, session_id: str | None) -> Session:
        self._remove_expired()
        if session_id and session_id in self._sessions:
            return self._sessions[session_id]
        return self.create()

    def require(self, session_id: str | None) -> Session:
        self._remove_expired()
        if not session_id or session_id not in self._sessions:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session expired. Start a new session.",
            )
        return self._sessions[session_id]

    def _remove_expired(self) -> None:
        now = datetime.now(UTC)
        expired_ids = [
            session_id
            for session_id, session in self._sessions.items()
            if session.expires_at <= now
        ]
        for session_id in expired_ids:
            del self._sessions[session_id]


def set_session_cookie(response: Response, session: Session, secure: bool = False) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session.session_id,
        max_age=max(0, int((session.expires_at - datetime.now(UTC)).total_seconds())),
        httponly=True,
        # Cross-origin frontend/backend requests require None; local HTTP uses Lax.
        samesite="none" if secure else "lax",
        secure=secure,
    )


def session_cookie(
    sourcesync_session: str | None = Cookie(default=None),
) -> str | None:
    return sourcesync_session
