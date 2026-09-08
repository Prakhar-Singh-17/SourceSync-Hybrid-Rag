import asyncio
import re

from rank_bm25 import BM25Okapi
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchValue

from app.embeddings import GeminiEmbedder


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z0-9_]+", text.lower())


async def scroll_session_chunks(
    qdrant: AsyncQdrantClient,
    collection_name: str,
    session_filter: Filter,
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    offset = None
    while True:
        page, offset = await qdrant.scroll(
            collection_name=collection_name,
            scroll_filter=session_filter,
            limit=256,
            offset=offset,
            with_payload=True,
        )
        records.extend(
            {
                "id": str(record.id),
                "text": record.payload.get("text", ""),
                "source_name": record.payload.get("source_name", "Unknown source"),
                "file_path": record.payload.get("file_path"),
            }
            for record in page
            if record.payload and record.payload.get("text")
        )
        if offset is None:
            return records


async def retrieve_context(
    *,
    question: str,
    session_id: str,
    qdrant: AsyncQdrantClient,
    embedder: GeminiEmbedder,
    collection_name: str,
    limit: int = 6,
) -> list[dict[str, object]]:
    query_vector = await asyncio.to_thread(embedder.embed_query, question)
    session_filter = Filter(must=[FieldCondition(key="session_id", match=MatchValue(value=session_id))])
    response = await qdrant.query_points(
        collection_name=collection_name,
        query=query_vector,
        query_filter=session_filter,
        limit=max(limit * 2, 12),
        with_payload=True,
    )
    dense_results = [
        {
            "id": str(point.id),
            "text": point.payload.get("text", ""),
            "source_name": point.payload.get("source_name", "Unknown source"),
            "file_path": point.payload.get("file_path"),
        }
        for point in response.points
        if point.payload and point.payload.get("text")
    ]
    all_chunks = await scroll_session_chunks(qdrant, collection_name, session_filter)
    if not all_chunks:
        return dense_results[:limit]

    bm25 = BM25Okapi([tokenize(str(chunk["text"])) for chunk in all_chunks])
    query_tokens = tokenize(question)
    query_token_set = set(query_tokens)
    lexical_scores = [
        max(float(score), 0.0) + len(query_token_set.intersection(tokenize(str(chunk["text"]))))
        for score, chunk in zip(bm25.get_scores(query_tokens), all_chunks, strict=True)
    ]
    lexical_results = [
        chunk
        for score, chunk in sorted(zip(lexical_scores, all_chunks), key=lambda pair: pair[0], reverse=True)
        if score > 0
    ][: max(limit * 2, 12)]

    fused: dict[str, tuple[float, dict[str, object]]] = {}
    for rank, chunk in enumerate(dense_results, start=1):
        fused[str(chunk["id"])] = (1 / (60 + rank), chunk)
    for rank, chunk in enumerate(lexical_results, start=1):
        key = str(chunk["id"])
        score = 1 / (60 + rank)
        if key in fused:
            fused[key] = (fused[key][0] + score, chunk)
        else:
            fused[key] = (score, chunk)
    return [chunk for _, chunk in sorted(fused.values(), key=lambda item: item[0], reverse=True)[:limit]]
