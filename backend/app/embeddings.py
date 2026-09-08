import asyncio

from google import genai
from google.genai import types


EMBEDDING_BATCH_SIZE = 1
EMBEDDING_CONCURRENCY = 3


class GeminiEmbedder:
    def __init__(self, api_key: str, model: str) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors: list[list[float]] = []
        for start in range(0, len(texts), EMBEDDING_BATCH_SIZE):
            batch = texts[start : start + EMBEDDING_BATCH_SIZE]
            response = self._client.models.embed_content(
                model=self._model,
                contents=batch,
                config=types.EmbedContentConfig(taskType="RETRIEVAL_DOCUMENT"),
            )
            batch_vectors = [embedding.values for embedding in response.embeddings]
            if len(batch_vectors) != len(batch):
                raise RuntimeError(
                    f"Gemini returned {len(batch_vectors)} embeddings for {len(batch)} texts."
                )
            vectors.extend(batch_vectors)
        return vectors

    def _embed_document(self, text: str) -> list[float]:
        response = self._client.models.embed_content(
            model=self._model,
            contents=text,
            config=types.EmbedContentConfig(taskType="RETRIEVAL_DOCUMENT"),
        )
        if len(response.embeddings) != 1:
            raise RuntimeError(f"Gemini returned {len(response.embeddings)} embeddings for one text.")
        return response.embeddings[0].values

    async def embed_documents_async(self, texts: list[str]) -> list[list[float]]:
        semaphore = asyncio.Semaphore(EMBEDDING_CONCURRENCY)

        async def embed_one(text: str) -> list[float]:
            async with semaphore:
                return await asyncio.to_thread(self._embed_document, text)

        return await asyncio.gather(*(embed_one(text) for text in texts))

    def embed_query(self, text: str) -> list[float]:
        response = self._client.models.embed_content(
            model=self._model,
            contents=text,
            config=types.EmbedContentConfig(taskType="RETRIEVAL_QUERY"),
        )
        return response.embeddings[0].values
