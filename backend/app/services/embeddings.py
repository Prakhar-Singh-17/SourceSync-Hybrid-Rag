"""Dense embeddings from Gemini.

A dense embedding turns text into a list of numbers positioned so that texts
about the same thing land near each other, which is what lets a search match
"how do I stop the server" against a passage that only says "shutdown
procedure".  This is the half of hybrid search that understands *meaning*;
:mod:`app.core.sparse` is the half that understands *words*.

On batching: the Gemini embedding endpoint accepts a list of texts but returns
an embedding only for the first one, silently and without an error.  Passing
several texts therefore loses data rather than failing loudly, so passages are
embedded one request each.  Throughput comes from issuing several of those
requests concurrently instead, bounded by a semaphore so a large repository does
not open hundreds of sockets at once or trip the free-tier rate limit.

The length check in :meth:`_embed_one` exists to catch exactly that class of
silent mismatch if the API behaviour ever changes again.
"""

import asyncio
import logging

from google import genai
from google.genai import types

from app.services.retry import with_retry

logger = logging.getLogger(__name__)

# Concurrent embedding requests. Higher finishes a large ingest sooner but
# risks HTTP 429 on a free-tier key; the retry policy absorbs the occasional
# one, and this value keeps them rare.
DEFAULT_CONCURRENCY = 5


class Embedder:
    """Wraps the Gemini embedding model.

    ``dimensions`` truncates the vector -- the model supports this natively via
    Matryoshka representation learning, and the result comes back already
    normalised, so no rescaling is needed.  The default is 3072 numbers per
    passage; asking for 768 makes every stored vector four times smaller, which
    is what keeps the index inside a free Qdrant cluster, at very little cost in
    retrieval quality.
    """

    def __init__(
        self,
        client: genai.Client,
        model: str,
        dimensions: int,
        concurrency: int = DEFAULT_CONCURRENCY,
    ) -> None:
        self._client = client
        self._model = model
        self._dimensions = dimensions
        self._semaphore = asyncio.Semaphore(concurrency)

    async def embed_passages(self, texts: list[str]) -> list[list[float]]:
        """Embed stored passages, several requests at a time.

        ``asyncio.gather`` preserves input order, which matters: the caller zips
        these vectors back against the passages that produced them.
        """
        if not texts:
            return []
        return list(await asyncio.gather(*(self._embed_limited(text) for text in texts)))

    async def embed_query(self, question: str) -> list[float]:
        """Embed a question.

        The task type differs from the one used for passages on purpose: Gemini
        places questions and the passages that answer them into a shared space,
        rather than embedding both as if they were the same kind of text.  Using
        the wrong task type here is a classic and near-invisible RAG bug -- the
        system keeps working, it just retrieves noticeably worse.
        """
        return await self._embed_one(question, "RETRIEVAL_QUERY")

    async def _embed_limited(self, text: str) -> list[float]:
        async with self._semaphore:
            return await self._embed_one(text, "RETRIEVAL_DOCUMENT")

    async def _embed_one(self, text: str, task_type: str) -> list[float]:
        async def call() -> list[float]:
            response = await asyncio.to_thread(
                self._client.models.embed_content,
                model=self._model,
                contents=text,
                config=types.EmbedContentConfig(
                    task_type=task_type,
                    output_dimensionality=self._dimensions,
                ),
            )
            embeddings = response.embeddings or []
            if len(embeddings) != 1:
                raise RuntimeError(f"Gemini returned {len(embeddings)} embeddings for one text.")
            values = embeddings[0].values
            if not values:
                raise RuntimeError("Gemini returned an empty embedding.")
            return list(values)

        return await with_retry(call, description="Embedding")
