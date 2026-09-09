"""Asking a question against the sources indexed in this session."""

import logging

from fastapi import APIRouter, Depends, HTTPException

from app.deps import current_session, get_pipeline
from app.schemas import AnswerResponse, QueryRequest
from app.sessions import Session
from app.services.pipeline import Pipeline
from app.services.retry import is_rate_limited, is_retryable

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/query", tags=["query"])


@router.post("", response_model=AnswerResponse)
async def ask_question(
    request: QueryRequest,
    session: Session = Depends(current_session),
    pipeline: Pipeline = Depends(get_pipeline),
) -> AnswerResponse:
    """Retrieve, rerank and answer.

    The whole strategy lives in ``Pipeline.ask``; this handler only translates
    failures into status codes. Retries have already happened one layer down, so
    reaching here means the operation genuinely failed.
    """
    try:
        return await pipeline.ask(session.id, request.question)
    except Exception as error:
        logger.exception("Query failed")
        if is_rate_limited(error):
            raise HTTPException(
                status_code=429,
                detail=(
                    "The daily Gemini request quota for this model has been used up. "
                    "Try again later, or set GEMINI_MODEL to a model with more headroom."
                ),
            ) from error
        if is_retryable(error):
            raise HTTPException(
                status_code=503,
                detail="Gemini is temporarily unavailable. Try again shortly.",
            ) from error
        raise HTTPException(status_code=502, detail="The question could not be answered.") from error
