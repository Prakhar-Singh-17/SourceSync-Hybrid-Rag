from google import genai
from google.genai import types


class GeminiEmbedder:
    def __init__(self, api_key: str, model: str) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        response = self._client.models.embed_content(
            model=self._model,
            contents=texts,
            config=types.EmbedContentConfig(taskType="RETRIEVAL_DOCUMENT"),
        )
        return [embedding.values for embedding in response.embeddings]

    def embed_query(self, text: str) -> list[float]:
        response = self._client.models.embed_content(
            model=self._model,
            contents=text,
            config=types.EmbedContentConfig(taskType="RETRIEVAL_QUERY"),
        )
        return response.embeddings[0].values
