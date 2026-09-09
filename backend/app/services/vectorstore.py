"""Qdrant: storage and the two searches that feed rank fusion.

Every passage is stored once but indexed twice, under two named vectors:

* ``dense``  -- the Gemini embedding, searched by cosine similarity (meaning).
* ``sparse`` -- the BM25 term-frequency vector, searched by term overlap (words).

Doing the keyword search inside Qdrant is the important design decision here.
The obvious alternative -- pull every passage for the session out of the
database and run BM25 over them in Python -- is what this project used to do,
and it made every question cost a full scan of the corpus.  Pushing it into the
index makes the keyword search sublinear and removes the rank-bm25 dependency
entirely.

The collection is shared by every session; isolation comes from a mandatory
``session_id`` filter.  The payload index for that field is declared with
``is_tenant=True``, which tells Qdrant to store each session contiguously on
disk and makes the filtered search cheap rather than a full-index scan.
"""

import logging
import time
from uuid import uuid4

from qdrant_client import AsyncQdrantClient, models

from app.core.models import Passage, Retrieved

logger = logging.getLogger(__name__)

DENSE_VECTOR = "dense"
SPARSE_VECTOR = "sparse"

# A session that has indexed more distinct sources than this is not a case worth
# rendering a list for; the count still reflects everything.
MAX_SOURCES_LISTED = 100


class VectorStore:
    def __init__(self, client: AsyncQdrantClient, collection: str, dimensions: int) -> None:
        self._client = client
        self._collection = collection
        self._dimensions = dimensions
        self._ready = False

    async def ensure_ready(self) -> None:
        """Create the collection and its indexes if they do not exist yet."""
        if self._ready:
            return
        if not await self._client.collection_exists(self._collection):
            await self._create_collection()
        else:
            await self._verify_collection()
        await self._ensure_indexes()
        self._ready = True

    async def _ensure_indexes(self) -> None:
        """Declare the payload indexes. Safe to repeat; runs once per process.

        ``session_id`` is marked as a tenant field, which tells Qdrant to keep
        each session contiguous on disk so the mandatory filter on every search
        stays cheap instead of scanning. ``source_name`` is indexed so the list
        of a session's sources can be read with a faceted count rather than by
        paging through every stored passage.
        """
        await self._client.create_payload_index(
            collection_name=self._collection,
            field_name="session_id",
            field_schema=models.KeywordIndexParams(
                type=models.KeywordIndexType.KEYWORD,
                is_tenant=True,
            ),
        )
        await self._client.create_payload_index(
            collection_name=self._collection,
            field_name="source_name",
            field_schema=models.PayloadSchemaType.KEYWORD,
        )
        await self._client.create_payload_index(
            collection_name=self._collection,
            field_name="expires_at",
            field_schema=models.PayloadSchemaType.INTEGER,
        )

    async def _create_collection(self) -> None:
        logger.info("Creating Qdrant collection %s", self._collection)
        await self._client.create_collection(
            collection_name=self._collection,
            vectors_config={
                DENSE_VECTOR: models.VectorParams(
                    size=self._dimensions,
                    distance=models.Distance.COSINE,
                ),
            },
            sparse_vectors_config={
                # IDF is computed by Qdrant from the live corpus. The client only
                # supplies term frequencies, because it has no way to know how
                # rare a term is across every other passage.
                SPARSE_VECTOR: models.SparseVectorParams(modifier=models.Modifier.IDF),
            },
            # Passage text is the bulk of the stored bytes and is never used for
            # filtering, only returned with hits. Keeping it on disk rather than
            # in RAM is what makes this fit a free 1 GB cluster.
            on_disk_payload=True,
        )

    async def _verify_collection(self) -> None:
        """Fail loudly if an existing collection has an incompatible layout."""
        info = await self._client.get_collection(self._collection)
        vectors = info.config.params.vectors
        if not isinstance(vectors, dict) or DENSE_VECTOR not in vectors:
            raise RuntimeError(
                f"Collection {self._collection!r} predates hybrid search and has no "
                f"named {DENSE_VECTOR!r} vector. Delete it in the Qdrant console, or "
                "point QDRANT_COLLECTION at a new name."
            )

    async def upsert(self, session_id: str, expires_at: int, passages: list[Passage], vectors: list[list[float]]) -> int:
        """Store passages together with their dense and sparse representations."""
        from app.core.sparse import sparse_vector

        if len(passages) != len(vectors):
            raise RuntimeError(f"Got {len(vectors)} vectors for {len(passages)} passages.")

        points: list[models.PointStruct] = []
        for passage, dense in zip(passages, vectors, strict=True):
            indices, values = sparse_vector(passage.embedding_text)
            named: dict[str, object] = {DENSE_VECTOR: dense}
            if indices:
                named[SPARSE_VECTOR] = models.SparseVector(indices=indices, values=values)
            points.append(
                models.PointStruct(
                    id=str(uuid4()),
                    vector=named,
                    payload={
                        "session_id": session_id,
                        "expires_at": expires_at,
                        "source_name": passage.source_name,
                        "file_path": passage.file_path,
                        "page_number": passage.page_number,
                        "chunk_index": passage.index,
                        "text": passage.text,
                    },
                )
            )

        for start in range(0, len(points), 100):
            await self._client.upsert(
                collection_name=self._collection,
                points=points[start : start + 100],
                wait=True,
            )
        return len(points)

    async def search_dense(self, session_id: str, vector: list[float], limit: int) -> list[Retrieved]:
        response = await self._client.query_points(
            collection_name=self._collection,
            query=vector,
            using=DENSE_VECTOR,
            query_filter=self._session_filter(session_id),
            limit=limit,
            with_payload=True,
        )
        return [_to_retrieved(point) for point in response.points if point.payload]

    async def search_sparse(self, session_id: str, indices: list[int], values: list[float], limit: int) -> list[Retrieved]:
        if not indices:
            return []
        response = await self._client.query_points(
            collection_name=self._collection,
            query=models.SparseVector(indices=indices, values=values),
            using=SPARSE_VECTOR,
            query_filter=self._session_filter(session_id),
            limit=limit,
            with_payload=True,
        )
        return [_to_retrieved(point) for point in response.points if point.payload]

    async def list_sources(self, session_id: str) -> list[tuple[str, int]]:
        """Return ``(source name, passage count)`` for everything in this session.

        A faceted count asks Qdrant to group by ``source_name`` and return the
        distinct values, so this costs one request regardless of how many
        passages the session holds. The alternative -- paging through the whole
        session to collect names client-side -- is the pattern this project
        deliberately removed from the query path.
        """
        response = await self._client.facet(
            collection_name=self._collection,
            key="source_name",
            facet_filter=self._session_filter(session_id),
            limit=MAX_SOURCES_LISTED,
            exact=True,
        )
        return [(str(hit.value), hit.count) for hit in response.hits]

    async def count_for_session(self, session_id: str) -> int:
        result = await self._client.count(
            collection_name=self._collection,
            count_filter=self._session_filter(session_id),
            exact=True,
        )
        return result.count

    async def delete_session(self, session_id: str) -> None:
        """Drop everything a session indexed. Called when the user clears their sources."""
        await self._client.delete(
            collection_name=self._collection,
            points_selector=models.FilterSelector(filter=self._session_filter(session_id)),
            wait=True,
        )

    async def purge_expired(self) -> None:
        """Delete passages whose session has expired.

        Sessions are temporary, so without this the collection would grow
        forever -- the original version never deleted anything, and orphaned
        vectors from dead sessions accumulated indefinitely.  Each point carries
        the expiry of the session that created it, so cleanup is a single
        filtered delete rather than any kind of bookkeeping.
        """
        await self._client.delete(
            collection_name=self._collection,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[models.FieldCondition(key="expires_at", range=models.Range(lt=time.time()))]
                )
            ),
            wait=False,
        )

    @staticmethod
    def _session_filter(session_id: str) -> models.Filter:
        return models.Filter(
            must=[models.FieldCondition(key="session_id", match=models.MatchValue(value=session_id))]
        )


def _to_retrieved(point: models.ScoredPoint) -> Retrieved:
    payload = point.payload or {}
    return Retrieved(
        id=str(point.id),
        text=str(payload.get("text", "")),
        source_name=str(payload.get("source_name", "Unknown source")),
        file_path=payload.get("file_path"),
        page_number=payload.get("page_number"),
    )
