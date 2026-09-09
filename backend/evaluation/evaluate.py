"""Measure whether hybrid retrieval actually beats its parts.

The claim this project makes is that combining semantic and keyword search
retrieves better than either alone. This script tests that claim instead of
asserting it.

The corpus is the backend's own source tree, which makes the evaluation
self-contained: no downloads, no external fixtures, and ground truth that is
simply the file a question is about. Each question in ``questions.json`` names
the file that answers it; a retrieval configuration scores a hit when a passage
from that file appears in the top k.

Two metrics:

* **Hit@k** -- the share of questions where the right file appears at all in the
  top k. This is what matters for a RAG system, because the answer model only
  ever sees the top k.
* **MRR** -- mean reciprocal rank, ``1 / position`` of the first correct
  passage. It rewards putting the right passage *first*, not merely somewhere.

Run it from the backend directory:

    python -m evaluation.evaluate

It needs credentials in .env, and it costs roughly one embedding call per source
file plus one per question, and one generate call per question for the reranked
configuration.
"""

import asyncio
import json
import time
from pathlib import Path

from google import genai
from qdrant_client import AsyncQdrantClient

from app.config import get_settings
from app.core.chunking import split_code
from app.core.fusion import reciprocal_rank_fusion
from app.core.models import Passage
from app.core.sparse import sparse_vector
from app.services.embeddings import Embedder
from app.services.llm import LanguageModel
from app.services.vectorstore import VectorStore

BACKEND_ROOT = Path(__file__).resolve().parents[1]
QUESTIONS_FILE = Path(__file__).resolve().parent / "questions.json"
SESSION_ID = "evaluation-corpus"
TOP_K = 5
CANDIDATES = 20


def build_corpus() -> list[Passage]:
    """Chunk every backend source file into passages tagged with their path."""
    passages: list[Passage] = []
    for path in sorted((BACKEND_ROOT / "app").rglob("*.py")):
        relative = path.relative_to(BACKEND_ROOT).as_posix()
        text = path.read_text(encoding="utf-8")
        for index, chunk in enumerate(split_code(text)):
            passages.append(
                Passage(text=chunk, index=index, source_name="sourcesync", file_path=relative)
            )
    return passages


def score(rankings: list[list[str]], expected: list[str]) -> tuple[float, float]:
    """Return (Hit@k, MRR) for a list of ranked file paths per question."""
    hits = 0
    reciprocal_total = 0.0
    for ranked, target in zip(rankings, expected, strict=True):
        top = ranked[:TOP_K]
        if target in top:
            hits += 1
            reciprocal_total += 1.0 / (top.index(target) + 1)
    return hits / len(expected), reciprocal_total / len(expected)


async def main() -> None:
    settings = get_settings()
    questions = json.loads(QUESTIONS_FILE.read_text(encoding="utf-8"))
    qdrant = AsyncQdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
    gemini = genai.Client(api_key=settings.gemini_api_key)
    store = VectorStore(qdrant, settings.qdrant_collection, settings.embedding_dimensions)
    embedder = Embedder(gemini, settings.embedding_model, settings.embedding_dimensions, settings.embedding_concurrency)
    llm = LanguageModel(
        gemini,
        settings.gemini_model,
        answer_max_tokens=settings.answer_max_tokens,
        thinking_budget=settings.answer_thinking_budget,
    )

    try:
        await store.ensure_ready()
        await store.delete_session(SESSION_ID)

        corpus = build_corpus()
        print(f"Indexing {len(corpus)} passages from {len({p.file_path for p in corpus})} files...")
        started = time.perf_counter()
        vectors = await embedder.embed_passages([passage.embedding_text for passage in corpus])
        expires_at = int(time.time()) + 3600
        await store.upsert(SESSION_ID, expires_at, corpus, vectors)
        print(f"Indexed in {time.perf_counter() - started:.1f}s\n")

        dense_only: list[list[str]] = []
        sparse_only: list[list[str]] = []
        hybrid: list[list[str]] = []
        reranked: list[list[str]] = []
        expected = [item["expected"] for item in questions]

        for item in questions:
            question = item["question"]
            query_vector = await embedder.embed_query(question)
            indices, values = sparse_vector(question)

            dense, sparse = await asyncio.gather(
                store.search_dense(SESSION_ID, query_vector, CANDIDATES),
                store.search_sparse(SESSION_ID, indices, values, CANDIDATES),
            )
            fused = reciprocal_rank_fusion(dense, sparse, limit=CANDIDATES)
            ordered, _ = await llm.rerank(question, list(fused), TOP_K)

            dense_only.append([found.file_path or "" for found in dense])
            sparse_only.append([found.file_path or "" for found in sparse])
            hybrid.append([found.file_path or "" for found in fused])
            reranked.append([found.file_path or "" for found in ordered])
            print(f"  scored: {question[:60]}")

        print(f"\n{len(questions)} questions, top {TOP_K}\n")
        print("| Retrieval | Hit@5 | MRR |")
        print("| --- | --- | --- |")
        for label, rankings in [
            ("Semantic (dense) only", dense_only),
            ("Keyword (BM25) only", sparse_only),
            ("Hybrid with RRF", hybrid),
            ("Hybrid with RRF + rerank", reranked),
        ]:
            hit, mrr = score(rankings, expected)
            print(f"| {label} | {hit:.0%} | {mrr:.3f} |")
    finally:
        await store.delete_session(SESSION_ID)
        await qdrant.close()


if __name__ == "__main__":
    asyncio.run(main())
