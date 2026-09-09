"""Liveness and dependency checks."""

from fastapi import APIRouter, Request

from app.config import get_settings
from app.schemas import HealthResponse

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Always answers, even when credentials are missing, so a deploy can be probed."""
    missing = get_settings().missing_credentials
    return HealthResponse(
        status="ok" if not missing else "degraded",
        service="sourcesync-api",
        detail=None if not missing else f"Missing configuration: {', '.join(missing)}.",
    )


@router.get("/qdrant", response_model=HealthResponse)
async def qdrant_health_check(request: Request) -> HealthResponse:
    client = getattr(request.app.state, "qdrant", None)
    if client is None:
        return HealthResponse(
            status="unconfigured",
            service="qdrant",
            detail="Set QDRANT_URL and QDRANT_API_KEY.",
        )
    try:
        await client.get_collections()
    except Exception as error:
        return HealthResponse(status="unreachable", service="qdrant", detail=str(error)[:200])
    return HealthResponse(status="ok", service="qdrant")
