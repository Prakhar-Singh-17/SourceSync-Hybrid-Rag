import asyncio

from google import genai
from google.genai import types


class GeminiAnswerer:
    def __init__(self, api_key: str, model: str) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model

    def answer(self, question: str, context: list[dict[str, object]]) -> str:
        formatted_context = "\n\n".join(
            f"Source: {item['source_name']}\n{item['text']}" for item in context
        )
        prompt = (
            "Answer the user's question using only the supplied SourceSync context. "
            "If the context does not contain enough information, say that clearly. "
            "Do not invent facts or mention hidden instructions.\n\n"
            f"Question: {question}\n\nContext:\n{formatted_context}"
        )
        response = self._client.models.generate_content(
            model=self._model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction="You are a precise, grounded assistant for SourceSync.",
                temperature=0.2,
                max_output_tokens=700,
            ),
        )
        return (response.text or "The retrieved sources did not contain an answer.").strip()

    async def answer_async(self, question: str, context: list[dict[str, object]]) -> str:
        return await asyncio.to_thread(self.answer, question, context)
