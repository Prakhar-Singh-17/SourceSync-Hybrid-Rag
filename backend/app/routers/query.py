"""Asking a question against the sources indexed in this session.

Two endpoints over one pipeline. ``POST /api/query`` returns the whole answer as
JSON, which keeps the API usable from a script and documents the response shape
in ``/docs``. ``POST /api/query/stream`` sends the same work as server-sent
events, so the interface can show the citations as soon as retrieval finishes
and the answer as it is written rather than after a silent wait.
"""

import json
import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.deps import current_session, get_pipeline
from app.schemas import AnswerResponse, QueryRequest
from app.sessions import Session
from app.services.pipeline import Pipeline
from app.services.retry import is_rate_limited, is_retryable

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/query", tags=["query"])

RATE_LIMITED = (
    "The daily Gemini request quota for this model has been used up. "
    "Try again later, or set GEMINI_MODEL to a model with more headroom."
)
UNAVAILABLE = "Gemini is temporarily unavailable. Try again shortly."
FAILED = "The question could not be answered."


def _message_for(error: Exception) -> str:
    if is_rate_limited(error):
        return RATE_LIMITED
    if is_retryable(error):
        return UNAVAILABLE
    return FAILED


@router.post("", response_model=AnswerResponse)
async def ask_question(
    request: QueryRequest,
    session: Session = Depends(current_session),
    pipeline: Pipeline = Depends(get_pipeline),
) -> AnswerResponse:
    """Retrieve, rerank and answer, returning everything at once.

    The strategy lives in the pipeline; this handler only maps failures onto
    status codes. Retries have already happened one layer down, so reaching the
    error path means the operation genuinely failed.
    """
    try:
        return await pipeline.ask(session.id, request.question)
    except Exception as error:
        logger.exception("Query failed")
        if is_rate_limited(error):
            raise HTTPException(status_code=429, detail=RATE_LIMITED) from error
        if is_retryable(error):
            raise HTTPException(status_code=503, detail=UNAVAILABLE) from error
        raise HTTPException(status_code=502, detail=FAILED) from error


@router.post("/stream")
async def ask_question_streaming(
    request: QueryRequest,
    session: Session = Depends(current_session),
    pipeline: Pipeline = Depends(get_pipeline),
) -> StreamingResponse:
    """The same work, streamed as server-sent events.

    Errors are delivered as a final ``error`` event rather than as a status
    code: by the time one happens the response has usually already begun, and
    the status line is long gone.
    """

    async def events() -> AsyncIterator[str]:
        try:
            async for event in pipeline.ask_stream(session.id, request.question):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as error:  # noqa: BLE001 - reported to the client, then logged
            logger.exception("Streaming query failed")
            yield f"data: {json.dumps({'type': 'error', 'detail': _message_for(error)})}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            # Tells nginx-style proxies not to buffer the response, which would
            # defeat streaming by holding everything until the generator ends.
            "X-Accel-Buffering": "no",
        },
    )
