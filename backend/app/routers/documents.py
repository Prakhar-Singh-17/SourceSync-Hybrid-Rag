from pathlib import PurePath

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from qdrant_client import AsyncQdrantClient

from app.documents import validate_document
from app.embeddings import GeminiEmbedder
from app.ingestion import ingest_document
from app.sessions import session_cookie
from app.state import session_store, settings


router = APIRouter(prefix="/api/documents", tags=["documents"])


def require_services() -> None:
    if not settings.gemini_api_key:
        raise HTTPException(status_code=503, detail="Gemini is not configured.")
    if not settings.qdrant_url or not settings.qdrant_api_key:
        raise HTTPException(status_code=503, detail="Qdrant is not configured.")


@router.post("/validate")
async def validate_uploaded_document(
    upload: UploadFile = File(...),
    cookie: str | None = Depends(session_cookie),
) -> dict[str, object]:
    session_store.require(cookie)
    return {"status": "accepted", **await validate_document(upload)}


@router.post("/ingest")
async def ingest_uploaded_document(
    upload: UploadFile = File(...),
    cookie: str | None = Depends(session_cookie),
) -> dict[str, object]:
    session = session_store.require(cookie)
    require_services()
    metadata = await validate_document(upload)
    await upload.seek(0)
    content = await upload.read()
    extension = PurePath(upload.filename or "").suffix.lower()
    qdrant = AsyncQdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
    try:
        chunk_count = await ingest_document(
            content=content,
            filename=str(metadata["filename"]),
            extension=extension,
            session_id=session.session_id,
            qdrant=qdrant,
            embedder=GeminiEmbedder(settings.gemini_api_key, settings.embedding_model),
            collection_name=settings.qdrant_collection,
        )
    except Exception as error:
        raise HTTPException(status_code=502, detail="Document ingestion failed.") from error
    finally:
        await qdrant.close()
    return {"status": "indexed", "filename": str(metadata["filename"]), "chunk_count": chunk_count}
