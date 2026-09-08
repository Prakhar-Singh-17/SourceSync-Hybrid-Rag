from fastapi import APIRouter, Depends, HTTPException
from qdrant_client import AsyncQdrantClient

from app.answering import GeminiAnswerer
from app.embeddings import GeminiEmbedder
from app.retrieval import retrieve_context
from app.schemas import QueryRequest
from app.sessions import session_cookie
from app.state import session_store, settings


router = APIRouter(prefix="/api/query", tags=["query"])


@router.post("")
async def query_sources(
    request: QueryRequest,
    cookie: str | None = Depends(session_cookie),
) -> dict[str, object]:
    session = session_store.require(cookie)
    if not settings.gemini_api_key:
        raise HTTPException(status_code=503, detail="Gemini is not configured.")
    if not settings.qdrant_url or not settings.qdrant_api_key:
        raise HTTPException(status_code=503, detail="Qdrant is not configured.")

    qdrant = AsyncQdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
    try:
        if not await qdrant.collection_exists(settings.qdrant_collection):
            return {"answer": "No sources have been indexed for this session yet.", "sources": []}
        context = await retrieve_context(
            question=request.question,
            session_id=session.session_id,
            qdrant=qdrant,
            embedder=GeminiEmbedder(settings.gemini_api_key, settings.embedding_model),
            collection_name=settings.qdrant_collection,
        )
        if not context:
            return {"answer": "No matching sources were found for this session.", "sources": []}
        answer = await GeminiAnswerer(settings.gemini_api_key, settings.gemini_model).answer_async(request.question, context)
        sources = list(dict.fromkeys(
            f"{item['source_name']} - {item['file_path']}" if item.get("file_path") else str(item["source_name"])
            for item in context
        ))
        return {"answer": answer, "sources": sources}
    except Exception as error:
        raise HTTPException(status_code=502, detail="The question could not be answered.") from error
    finally:
        await qdrant.close()
