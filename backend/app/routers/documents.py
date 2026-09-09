"""Uploading and indexing a PDF, TXT or Markdown document."""

from fastapi import APIRouter, Depends, File, UploadFile

from app.core.documents import MAX_DOCUMENT_BYTES
from app.deps import current_session, get_pipeline
from app.schemas import IngestResponse
from app.sessions import Session
from app.services.pipeline import Pipeline

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post("/ingest", response_model=IngestResponse)
async def ingest_document(
    upload: UploadFile = File(...),
    session: Session = Depends(current_session),
    pipeline: Pipeline = Depends(get_pipeline),
) -> IngestResponse:
    # One byte past the limit is enough to detect an oversized upload without
    # reading the whole thing into memory. Validation itself lives in app.core.
    content = await upload.read(MAX_DOCUMENT_BYTES + 1)
    return await pipeline.ingest_document(
        session.id,
        session.expires_at_unix,
        upload.filename or "document",
        content,
    )
