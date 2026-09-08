import asyncio
from uuid import uuid4

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, PayloadSchemaType, PointStruct, VectorParams

from app.chunking import split_text
from app.documents import extract_text
from app.embeddings import GeminiEmbedder
from app.repositories import eligible_members


async def ensure_collection(qdrant: AsyncQdrantClient, collection_name: str, vector_size: int) -> None:
    if not await qdrant.collection_exists(collection_name):
        await qdrant.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )
    await qdrant.create_payload_index(
        collection_name=collection_name,
        field_name="session_id",
        field_schema=PayloadSchemaType.KEYWORD,
        wait=True,
    )


async def ingest_document(
    *,
    content: bytes,
    filename: str,
    extension: str,
    session_id: str,
    qdrant: AsyncQdrantClient,
    embedder: GeminiEmbedder,
    collection_name: str,
) -> int:
    text, page_count = extract_text(content, extension)
    chunks = split_text(text)
    if not chunks:
        return 0

    vectors = await asyncio.to_thread(embedder.embed_documents, [chunk.text for chunk in chunks])
    if not vectors:
        return 0

    await ensure_collection(qdrant, collection_name, len(vectors[0]))

    points = [
        PointStruct(
            id=str(uuid4()),
            vector=vector,
            payload={
                "session_id": session_id,
                "source_type": "document",
                "source_name": filename,
                "chunk_index": chunk.index,
                "text": chunk.text,
                "start": chunk.start,
                "end": chunk.end,
                "file_type": extension.removeprefix("."),
                "page_count": page_count,
            },
        )
        for chunk, vector in zip(chunks, vectors, strict=True)
    ]
    await qdrant.upsert(collection_name=collection_name, points=points, wait=True)
    return len(points)


async def ingest_repository(
    *,
    archive: bytes,
    repository_name: str,
    session_id: str,
    qdrant: AsyncQdrantClient,
    embedder: GeminiEmbedder,
    collection_name: str,
) -> tuple[int, int]:
    from io import BytesIO
    from zipfile import ZipFile

    with ZipFile(BytesIO(archive)) as zip_file:
        members = eligible_members(zip_file)
        documents = []
        for member in members:
            content = zip_file.read(member)
            text = content.decode("utf-8", errors="ignore")
            chunks = split_text(text)
            documents.extend((member, chunk) for chunk in chunks)

    if not documents:
        return len(members), 0

    points: list[PointStruct] = []
    for start in range(0, len(documents), 100):
        batch = documents[start : start + 100]
        vectors = await asyncio.to_thread(embedder.embed_documents, [chunk.text for _, chunk in batch])
        points.extend(
            PointStruct(
                id=str(uuid4()),
                vector=vector,
                payload={
                    "session_id": session_id,
                    "source_type": "repository",
                    "source_name": repository_name,
                    "file_path": member,
                    "chunk_index": chunk.index,
                    "text": chunk.text,
                    "start": chunk.start,
                    "end": chunk.end,
                },
            )
            for (member, chunk), vector in zip(batch, vectors, strict=True)
        )

    await ensure_collection(qdrant, collection_name, len(points[0].vector))
    for start in range(0, len(points), 100):
        await qdrant.upsert(collection_name=collection_name, points=points[start : start + 100], wait=True)
    return len(members), len(points)
