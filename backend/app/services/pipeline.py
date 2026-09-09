"""The RAG pipeline: ingestion on one side, question answering on the other.

This module is the one place where the whole flow is written down in order, so
it doubles as the explanation of how the system works:

    ingest:  bytes -> pages -> passages -> embeddings -> Qdrant
    ask:     question -> dense search + sparse search -> fuse -> rerank -> answer

Routers call into here and do nothing else.  Previously this orchestration lived
inside the query router, mixed together with HTTP concerns, retry loops and
tuning constants, which made the actual retrieval strategy hard to find.
"""

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from io import BytesIO
from zipfile import BadZipFile, ZipFile

from app.core import repository as repo
from app.core.documents import extension_of, extract_pages, passages_from_document
from app.core.errors import SourceError, SourceTooLarge
from app.core.fusion import reciprocal_rank_fusion
from app.core.models import Passage, Retrieved
from app.core.sparse import sparse_vector
from app.schemas import AnswerResponse, Citation, IngestResponse, SourceSummary, Timings
from app.services.embeddings import Embedder
from app.services.github import download_archive
from app.services.llm import LanguageModel
from app.services.vectorstore import VectorStore

logger = logging.getLogger(__name__)

SNIPPET_LENGTH = 320


class Pipeline:
    def __init__(
        self,
        *,
        store: VectorStore,
        embedder: Embedder,
        llm: LanguageModel,
        retrieval_candidates: int,
        context_passages: int,
        max_session_passages: int,
    ) -> None:
        self._store = store
        self._embedder = embedder
        self._llm = llm
        self._retrieval_candidates = retrieval_candidates
        self._context_passages = context_passages
        self._max_session_passages = max_session_passages

    # ------------------------------------------------------------------ ingest

    async def ingest_document(
        self, session_id: str, expires_at: int, filename: str, content: bytes
    ) -> IngestResponse:
        pages = extract_pages(content, extension_of(filename))
        passages = passages_from_document(pages, filename)
        stored = await self._store_passages(session_id, expires_at, passages)
        return IngestResponse(
            source_name=filename,
            passage_count=stored,
            total_passages=await self._store.count_for_session(session_id),
        )

    async def ingest_repository(self, session_id: str, expires_at: int, url: str) -> IngestResponse:
        details = repo.validate_github_url(url)
        archive_bytes = await download_archive(details["owner"], details["repository"])

        passages: list[Passage] = []
        try:
            with ZipFile(BytesIO(archive_bytes)) as archive:
                members = repo.eligible_members(archive)
                for member in members:
                    text = archive.read(member).decode("utf-8", errors="ignore")
                    passages.extend(repo.passages_from_file(member, text, details["name"]))
        except BadZipFile as error:
            raise SourceError("GitHub returned an archive that could not be read.") from error

        if not passages:
            raise SourceError("No indexable source or documentation files were found.")

        stored = await self._store_passages(session_id, expires_at, passages)
        return IngestResponse(
            source_name=details["name"],
            file_count=len(members),
            passage_count=stored,
            total_passages=await self._store.count_for_session(session_id),
        )

    async def _store_passages(self, session_id: str, expires_at: int, passages: list[Passage]) -> int:
        if not passages:
            raise SourceError("No readable text was found in that source.")

        # The collection is prepared *before* embedding. Doing it afterwards, as
        # the original did, means a misconfigured collection is only discovered
        # once every embedding has already been paid for.
        await self._store.ensure_ready()

        existing = await self._store.count_for_session(session_id)
        if existing + len(passages) > self._max_session_passages:
            raise SourceTooLarge(
                f"A session can hold {self._max_session_passages} passages. "
                f"This source would add {len(passages)} to the {existing} already indexed."
            )

        vectors = await self._embedder.embed_passages([passage.embedding_text for passage in passages])
        return await self._store.upsert(session_id, expires_at, passages, vectors)

    # --------------------------------------------------------------------- ask

    async def ask_stream(self, session_id: str, question: str) -> AsyncIterator[dict[str, object]]:
        """Run the pipeline, emitting an event as each stage completes.

        Event types:

        ``stage``    a named stage has begun: embedding, searching, reranking, writing
        ``context``  retrieval finished; carries the citations and retrieval counts
        ``token``    a fragment of the answer, as the model writes it
        ``done``     carries the per-stage timings
        ``error``    something failed, with a message

        Emitting ``context`` before the first token is the point of streaming
        here: the reader sees which passages the answer will be built from while
        it is still being written, rather than waiting for the whole thing.
        """
        started = time.perf_counter()

        if await self._store.count_for_session(session_id) == 0:
            yield _token("No sources have been indexed yet. Add a document or a repository first.")
            yield _done(Timings(total_ms=_elapsed_ms(started)))
            return

        # Both representations of the question. The dense one costs an API call;
        # the sparse one is pure local computation, which is why the keyword half
        # of hybrid search is effectively free.
        yield _stage("embedding")
        embed_started = time.perf_counter()
        query_vector = await self._embedder.embed_query(question)
        indices, values = sparse_vector(question)
        embed_ms = _elapsed_ms(embed_started)

        yield _stage("searching")
        search_started = time.perf_counter()
        dense, sparse = await asyncio.gather(
            self._store.search_dense(session_id, query_vector, self._retrieval_candidates),
            self._store.search_sparse(session_id, indices, values, self._retrieval_candidates),
        )
        search_ms = _elapsed_ms(search_started)

        candidates = reciprocal_rank_fusion(dense, sparse, limit=self._retrieval_candidates)
        if not candidates:
            yield _token("Nothing in the indexed sources matched that question.")
            yield _done(Timings(embed_ms=embed_ms, search_ms=search_ms, total_ms=_elapsed_ms(started)))
            return

        yield _stage("reranking")
        rerank_started = time.perf_counter()
        context, reranked = await self._llm.rerank(question, candidates, self._context_passages)
        rerank_ms = _elapsed_ms(rerank_started)

        yield {
            "type": "context",
            "citations": [
                _to_citation(number, item).model_dump()
                for number, item in enumerate(context, start=1)
            ],
            "reranked": reranked,
            "candidates_considered": len(candidates),
            "dense_hits": len(dense),
            "sparse_hits": len(sparse),
        }

        yield _stage("writing")
        generate_started = time.perf_counter()
        produced = False
        async for piece in self._llm.answer_stream(question, context):
            produced = True
            yield _token(piece)
        if not produced:
            logger.warning("Gemini produced no answer text; the token budget may have been hit.")
            yield _token(
                "No answer could be generated from the retrieved sources. Try rephrasing the question."
            )
        generate_ms = _elapsed_ms(generate_started)

        yield _done(
            Timings(
                embed_ms=embed_ms,
                search_ms=search_ms,
                rerank_ms=rerank_ms,
                generate_ms=generate_ms,
                total_ms=_elapsed_ms(started),
            )
        )

    async def ask(self, session_id: str, question: str) -> AnswerResponse:
        """The whole answer at once, assembled from the same generator.

        Kept so the JSON endpoint and the streaming endpoint cannot drift: there
        is one implementation of the pipeline, and this drains it.
        """
        response = AnswerResponse(answer="")
        parts: list[str] = []
        async for event in self.ask_stream(session_id, question):
            kind = event.get("type")
            if kind == "token":
                parts.append(str(event["text"]))
            elif kind == "context":
                response.citations = [Citation(**item) for item in event["citations"]]  # type: ignore[union-attr]
                response.reranked = bool(event["reranked"])
                response.candidates_considered = int(event["candidates_considered"])  # type: ignore[arg-type]
                response.dense_hits = int(event["dense_hits"])  # type: ignore[arg-type]
                response.sparse_hits = int(event["sparse_hits"])  # type: ignore[arg-type]
            elif kind == "done":
                response.timings = Timings(**event["timings"])  # type: ignore[arg-type]
        response.answer = "".join(parts).strip()
        return response

    async def clear(self, session_id: str) -> None:
        await self._store.ensure_ready()
        await self._store.delete_session(session_id)

    async def passage_count(self, session_id: str) -> int:
        await self._store.ensure_ready()
        return await self._store.count_for_session(session_id)

    async def sources(self, session_id: str) -> list[SourceSummary]:
        """Everything indexed in this session, newest ordering not guaranteed."""
        await self._store.ensure_ready()
        return [
            SourceSummary(name=name, passage_count=count)
            for name, count in await self._store.list_sources(session_id)
        ]


def _to_citation(number: int, item: Retrieved) -> Citation:
    snippet = " ".join(item.text.split())
    if len(snippet) > SNIPPET_LENGTH:
        snippet = snippet[:SNIPPET_LENGTH].rstrip() + "..."
    return Citation(
        number=number,
        source_name=item.source_name,
        file_path=item.file_path,
        page_number=item.page_number,
        location=item.location,
        snippet=snippet,
        dense_rank=item.dense_rank,
        sparse_rank=item.sparse_rank,
        fused_score=round(item.fused_score, 5),
    )


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def _stage(name: str) -> dict[str, object]:
    return {"type": "stage", "stage": name}


def _token(text: str) -> dict[str, object]:
    return {"type": "token", "text": text}


def _done(timings: Timings) -> dict[str, object]:
    return {"type": "done", "timings": timings.model_dump()}
