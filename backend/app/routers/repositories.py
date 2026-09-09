"""Indexing a public GitHub repository."""

from fastapi import APIRouter, Depends

from app.deps import current_session, get_pipeline
from app.schemas import IngestResponse, RepositoryRequest
from app.sessions import Session
from app.services.pipeline import Pipeline

router = APIRouter(prefix="/api/repositories", tags=["repositories"])


@router.post("/ingest", response_model=IngestResponse)
async def ingest_repository(
    request: RepositoryRequest,
    session: Session = Depends(current_session),
    pipeline: Pipeline = Depends(get_pipeline),
) -> IngestResponse:
    return await pipeline.ingest_repository(session.id, session.expires_at_unix, request.url)
