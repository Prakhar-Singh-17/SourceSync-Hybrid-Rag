import httpx
import logging
from fastapi import APIRouter, Depends, HTTPException
from qdrant_client import AsyncQdrantClient

from app.embeddings import GeminiEmbedder
from app.ingestion import ingest_repository
from app.repositories import MAX_ARCHIVE_BYTES, validate_github_url
from app.schemas import RepositoryRequest
from app.sessions import session_cookie
from app.state import session_store, settings


router = APIRouter(prefix="/api/repositories", tags=["repositories"])
logger = logging.getLogger(__name__)


def require_services() -> None:
    if not settings.gemini_api_key:
        raise HTTPException(status_code=503, detail="Gemini is not configured.")
    if not settings.qdrant_url or not settings.qdrant_api_key:
        raise HTTPException(status_code=503, detail="Qdrant is not configured.")


@router.post("/validate")
async def validate_repository(
    request: RepositoryRequest,
    cookie: str | None = Depends(session_cookie),
) -> dict[str, str]:
    session_store.require(cookie)
    return {"status": "accepted", **validate_github_url(request.url)}


@router.post("/ingest")
async def ingest_github_repository(
    request: RepositoryRequest,
    cookie: str | None = Depends(session_cookie),
) -> dict[str, object]:
    session = session_store.require(cookie)
    repository = validate_github_url(request.url)
    require_services()
    archive_url = f"https://api.github.com/repos/{repository['owner']}/{repository['repository']}/zipball"
    archive = bytearray()
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=60) as client:
            async with client.stream("GET", archive_url, headers={"Accept": "application/vnd.github+json"}) as response:
                response.raise_for_status()
                async for chunk in response.aiter_bytes():
                    archive.extend(chunk)
                    if len(archive) > MAX_ARCHIVE_BYTES:
                        raise HTTPException(status_code=413, detail="Repository archives must be 50 MB or smaller.")
    except HTTPException:
        raise
    except httpx.HTTPStatusError as error:
        logger.exception("GitHub archive request failed for %s", repository["url"])
        raise HTTPException(
            status_code=502,
            detail=f"GitHub returned HTTP {error.response.status_code} while downloading the repository.",
        ) from error
    except httpx.HTTPError as error:
        logger.exception("GitHub archive download failed for %s", repository["url"])
        raise HTTPException(status_code=502, detail="Unable to download the GitHub repository.") from error

    qdrant = AsyncQdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
    try:
        file_count, chunk_count = await ingest_repository(
            archive=bytes(archive),
            repository_name=f"{repository['owner']}/{repository['repository']}",
            session_id=session.session_id,
            qdrant=qdrant,
            embedder=GeminiEmbedder(settings.gemini_api_key, settings.embedding_model),
            collection_name=settings.qdrant_collection,
        )
    except HTTPException:
        raise
    except Exception as error:
        logger.exception("Repository ingestion failed for %s", repository["url"])
        raise HTTPException(status_code=502, detail="Repository ingestion failed.") from error
    finally:
        await qdrant.close()
    return {"status": "indexed", "repository": f"{repository['owner']}/{repository['repository']}", "file_count": file_count, "chunk_count": chunk_count}
