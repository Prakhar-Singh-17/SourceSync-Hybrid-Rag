"""Anonymous temporary sessions, signed rather than stored.

A session exists only to keep one visitor's sources separate from everyone
else's.  There are no accounts and nothing personal in it, so there is nothing
worth keeping on the server: the cookie itself carries the session id and its
expiry, signed with HMAC so a visitor cannot forge one and read another
session's documents.

The previous design held sessions in a dictionary in memory, which broke in a
specific and confusing way on a free Render instance: the service sleeps after
fifteen minutes of inactivity, so the dictionary was wiped regularly while the
documents those sessions had indexed stayed behind in Qdrant forever.  Visitors
silently lost access to their own uploads.  A signed cookie has no such state to
lose, works across restarts and across multiple workers, and is less code.
"""

import hmac
from base64 import urlsafe_b64encode
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import compare_digest, token_urlsafe

COOKIE_NAME = "sourcesync_session"
SESSION_ID_BYTES = 16


@dataclass(frozen=True)
class Session:
    id: str
    expires_at: datetime

    @property
    def expires_at_unix(self) -> int:
        return int(self.expires_at.timestamp())

    @property
    def max_age_seconds(self) -> int:
        return max(0, int((self.expires_at - datetime.now(UTC)).total_seconds()))


def new_session(ttl_minutes: int) -> Session:
    # Truncated to whole seconds on purpose: the signed token carries a unix
    # timestamp, so sub-second precision would be lost on the first round trip
    # and the reported expiry would appear to change between requests.
    expires_at = (datetime.now(UTC) + timedelta(minutes=ttl_minutes)).replace(microsecond=0)
    return Session(id=token_urlsafe(SESSION_ID_BYTES), expires_at=expires_at)


def encode(session: Session, secret: str) -> str:
    """Serialise a session into ``id.expiry.signature``."""
    payload = f"{session.id}.{session.expires_at_unix}"
    return f"{payload}.{_sign(payload, secret)}"


def decode(token: str | None, secret: str) -> Session | None:
    """Return the session a token represents, or ``None`` if it is invalid.

    Invalid covers forged, tampered with, malformed and expired -- the caller
    treats all of them the same way, by starting a new session.
    """
    if not token:
        return None
    parts = token.rsplit(".", 2)
    if len(parts) != 3:
        return None
    session_id, expiry, signature = parts

    if not compare_digest(_sign(f"{session_id}.{expiry}", secret), signature):
        return None
    try:
        expires_at = datetime.fromtimestamp(int(expiry), UTC)
    except (ValueError, OverflowError, OSError):
        return None
    if expires_at <= datetime.now(UTC):
        return None
    return Session(id=session_id, expires_at=expires_at)


def _sign(payload: str, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), sha256).digest()
    return urlsafe_b64encode(digest).decode("ascii").rstrip("=")
