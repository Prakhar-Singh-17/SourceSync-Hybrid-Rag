"""Application entry point.

Startup builds the shared clients once and assembles the pipeline; shutdown
closes them.  If credentials are missing the app still starts and still serves
its health endpoints -- it just reports 503 with the name of the missing setting
instead of failing to boot, which is far easier to diagnose on a hosted deploy.
"""

import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from google import genai
from qdrant_client import AsyncQdrantClient

from app.config import get_settings
from app.core.errors import SourceError, SourceTooLarge
from app.routers import documents, health, query, repositories, sessions
from app.services.embeddings import Embedder
from app.services.llm import LanguageModel
from app.services.pipeline import Pipeline
from app.services.vectorstore import VectorStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    settings.warn_about_gaps()
    app.state.qdrant = None
    app.state.pipeline = None

    if not settings.missing_credentials:
        qdrant = AsyncQdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
        gemini = genai.Client(api_key=settings.gemini_api_key)
        store = VectorStore(qdrant, settings.qdrant_collection, settings.embedding_dimensions)

        app.state.qdrant = qdrant
        app.state.store = store
        app.state.pipeline = Pipeline(
            store=store,
            embedder=Embedder(
                gemini,
                settings.embedding_model,
                settings.embedding_dimensions,
                settings.embedding_concurrency,
            ),
            llm=LanguageModel(
                gemini,
                settings.gemini_model,
                rerank_model=settings.rerank_model,
                answer_max_tokens=settings.answer_max_tokens,
                thinking_budget=settings.answer_thinking_budget,
            ),
            retrieval_candidates=settings.retrieval_candidates,
            context_passages=settings.context_passages,
            max_session_passages=settings.max_session_passages,
        )

        try:
            await store.ensure_ready()
            # One pass for anything that expired while the process was down.
            await store.purge_expired()
        except Exception:
            logger.exception("Could not prepare the Qdrant collection at startup.")

        app.state.purge_task = asyncio.create_task(
            _purge_expired_periodically(store, settings.purge_interval_minutes * 60)
        )

    yield

    purge_task: asyncio.Task | None = getattr(app.state, "purge_task", None)
    if purge_task is not None:
        purge_task.cancel()
        with suppress(asyncio.CancelledError):
            await purge_task
    if app.state.qdrant is not None:
        await app.state.qdrant.close()


async def _purge_expired_periodically(store: VectorStore, interval_seconds: int) -> None:
    """Delete passages belonging to expired sessions, on an interval, forever.

    Nothing tells the server when a visitor closes their tab, and deliberately
    so: a browser-close hook fires on an ordinary page reload too, which would
    throw away sources the visitor still wants. The session expiry is the
    boundary instead, and this sweep is what enforces it while the process runs.

    Each passage stores the expiry of the session that created it, so a sweep is
    a single filtered delete rather than any bookkeeping. Failures are logged and
    the loop continues -- a temporary Qdrant problem should not end cleanup for
    the lifetime of the process.
    """
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            await store.purge_expired()
        except Exception:
            logger.exception("Scheduled purge of expired passages failed; will retry.")


app = FastAPI(
    title="SourceSync API",
    version="1.0.0",
    description=(
        "Hybrid retrieval over uploaded documents and public GitHub repositories. "
        "Combines dense vector search with BM25 keyword search, merges the two "
        "rankings with Reciprocal Rank Fusion, reranks with Gemini, and answers "
        "with inline citations."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(SourceTooLarge)
async def handle_source_too_large(_: Request, error: SourceTooLarge) -> JSONResponse:
    return JSONResponse(status_code=413, content={"detail": str(error)})


@app.exception_handler(SourceError)
async def handle_source_error(_: Request, error: SourceError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": str(error)})


app.include_router(health.router)
app.include_router(sessions.router)
app.include_router(documents.router)
app.include_router(repositories.router)
app.include_router(query.router)
