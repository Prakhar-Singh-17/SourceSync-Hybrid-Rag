from fastapi import APIRouter, HTTPException
from qdrant_client import AsyncQdrantClient

from app.state import settings


router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "sourcesync-api"}


@router.get("/qdrant")
async def qdrant_health_check() -> dict[str, str]:
    if not settings.qdrant_url or not settings.qdrant_api_key:
        raise HTTPException(
            status_code=503,
            detail="Qdrant is not configured. Add QDRANT_URL and QDRANT_API_KEY to .env.",
        )

    client = AsyncQdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
    try:
        await client.get_collections()
    except Exception as error:
        raise HTTPException(status_code=503, detail="Unable to connect to Qdrant.") from error
    finally:
        await client.close()
    return {"status": "ok", "service": "qdrant"}
