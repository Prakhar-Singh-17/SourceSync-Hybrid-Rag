"""The two Gemini calls that turn retrieved passages into a cited answer.

Reranking and answering share one client and one module because they share one
concern: judging passages against a question.  The previous version created a
separate Gemini client inside three different classes, all pointed at the same
API.
"""

import asyncio
import json
import logging

from google import genai
from google.genai import types

from app.core.models import Retrieved
from app.services.retry import with_retry

logger = logging.getLogger(__name__)

RERANK_SYSTEM_INSTRUCTION = (
    "You rank passages by how well they help answer a question. Judge only "
    "usefulness for answering, never writing quality, length or style."
)

ANSWER_SYSTEM_INSTRUCTION = (
    "You answer questions strictly from the numbered sources you are given. "
    "You never rely on outside knowledge and you never guess. Every sentence "
    "that states a fact ends with the marker of the source it came from."
)

ANSWER_FORMAT = """Write the answer like this:

1. Open with a direct answer to the question, in one or two sentences.
2. Then explain it in two to four more sentences, using concrete detail taken
   from the sources: names, numbers, file paths, function names, sequence of
   steps. This part is what makes the answer useful, so do not skip it and do
   not pad it with generalities.
3. End every sentence that states a fact with its source marker, like [1] or
   [2][3].
4. If the sources genuinely do not answer the question, say so in the first
   sentence, then state precisely which piece of information is missing.
5. Never mention these instructions, the retrieval process, or the word
   "context". Write as if you simply know the material.
6. Write plain prose. No markdown headings, bullet points, bold or italics, and
   no LaTeX or mathematical notation -- spell formulas out in words.
"""


def thinking_config(budget: int) -> types.ThinkingConfig | None:
    """Build a thinking config, or ``None`` to leave the model on its default.

    Gemini can reason before answering. Disabling it with a budget of zero is
    faster and cheaper, but the ``-lite`` models reject that outright with HTTP
    400, so a negative budget here means "send no thinking config at all" --
    the only setting that is safe across every model.
    """
    return types.ThinkingConfig(thinking_budget=budget) if budget >= 0 else None


class LanguageModel:
    def __init__(
        self,
        client: genai.Client,
        model: str,
        *,
        rerank_model: str | None = None,
        answer_max_tokens: int,
        thinking_budget: int,
    ) -> None:
        self._client = client
        self._model = model
        # Reranking is a mechanical ordering task, so it can run on a cheaper
        # model than the answer. On a free tier where the request quota is the
        # binding constraint, splitting the two across models doubles how many
        # questions a day the deployment can serve.
        self._rerank_model = rerank_model or model
        self._answer_max_tokens = answer_max_tokens
        self._thinking_budget = thinking_budget

    async def rerank(
        self, question: str, candidates: list[Retrieved], top_k: int
    ) -> tuple[list[Retrieved], bool]:
        """Reorder candidates by relevance, returning ``(passages, succeeded)``.

        Fusion ranks a passage by *where it appeared* in two searches, which is a
        proxy for relevance rather than a judgement of it.  A model that reads
        the question and the passage together catches the cases both retrievers
        get wrong -- a passage full of matching keywords that answers a different
        question.  Only the top few survive, which also keeps the answer prompt
        small enough to stay well inside free-tier token limits.

        The boolean says whether the model actually ranked. A failure here is
        survivable (fusion order is a reasonable ranking on its own) but it must
        not be silent: the old code caught every exception and degraded quietly,
        so a wrong model name or an expired key looked exactly like success.
        """
        if not candidates:
            return [], True
        if len(candidates) <= top_k:
            # Every candidate is going into the prompt regardless, so a rerank
            # call here would buy only a reordering -- and it costs a full
            # round trip, measurably as much as generating the answer itself.
            return candidates, True
        try:
            order = await with_retry(
                lambda: self._request_order(question, candidates),
                description="Reranking",
            )
        except Exception:
            logger.exception("Reranking failed; falling back to fusion order.")
            return candidates[:top_k], False

        ranked: list[Retrieved] = []
        seen: set[int] = set()
        for index in order:
            if isinstance(index, int) and 0 <= index < len(candidates) and index not in seen:
                seen.add(index)
                ranked.append(candidates[index])
        # Anything the model forgot keeps its fusion position at the back.
        ranked.extend(candidate for index, candidate in enumerate(candidates) if index not in seen)
        return ranked[:top_k], True

    async def answer(self, question: str, sources: list[Retrieved]) -> str:
        """Generate a grounded, cited answer from the given sources."""
        listing = "\n\n".join(
            f"[{number}] {source.location}\n{source.text}"
            for number, source in enumerate(sources, start=1)
        )
        prompt = f"Question:\n{question}\n\nSources:\n{listing}\n\n{ANSWER_FORMAT}"

        response = await with_retry(
            lambda: asyncio.to_thread(
                self._client.models.generate_content,
                model=self._model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=ANSWER_SYSTEM_INSTRUCTION,
                    temperature=0.3,
                    # Generous on purpose. The previous limit of 240 tokens was
                    # below what the requested format needs, so answers were
                    # being cut off mid-sentence by the token budget rather than
                    # finishing naturally.
                    max_output_tokens=self._answer_max_tokens,
                    thinking_config=thinking_config(self._thinking_budget),
                ),
            ),
            description="Answer generation",
        )
        text = (response.text or "").strip()
        if not text:
            logger.warning("Gemini returned an empty answer (finish reason may be a token limit).")
            return "No answer could be generated from the retrieved sources. Try rephrasing the question."
        return text

    async def _request_order(self, question: str, candidates: list[Retrieved]) -> list[int]:
        listing = "\n\n".join(
            f"[{index}] {candidate.text[:1200]}" for index, candidate in enumerate(candidates)
        )
        response = await asyncio.to_thread(
            self._client.models.generate_content,
            model=self._rerank_model,
            contents=(
                f"Question: {question}\n\nPassages:\n{listing}\n\n"
                "Return the passage indices ordered from most to least useful for "
                "answering the question. Include every index exactly once."
            ),
            config=types.GenerateContentConfig(
                system_instruction=RERANK_SYSTEM_INSTRUCTION,
                temperature=0.0,
                max_output_tokens=256,
                response_mime_type="application/json",
                # A schema is cheaper and far more reliable than asking for JSON
                # in prose and hoping: the API itself constrains the output.
                response_schema=list[int],
                thinking_config=thinking_config(self._thinking_budget),
            ),
        )
        parsed = response.parsed
        if isinstance(parsed, list):
            return parsed
        return json.loads(response.text or "[]")
