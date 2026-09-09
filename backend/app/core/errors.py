"""Errors raised by the pure logic layer.

``app.core`` deliberately does not import FastAPI, so it cannot raise
``HTTPException``.  It raises these instead and the routers translate them into
status codes.  That keeps the interesting logic testable without a web server.
"""


class SourceError(ValueError):
    """The input is not something we can index (wrong type, corrupt, unreadable)."""


class SourceTooLarge(SourceError):
    """The input is valid but exceeds a limit set for the free-tier deployment."""
