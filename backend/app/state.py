from app.config import get_settings
from app.sessions import SessionStore


settings = get_settings()
session_store = SessionStore(settings.session_ttl_minutes)
