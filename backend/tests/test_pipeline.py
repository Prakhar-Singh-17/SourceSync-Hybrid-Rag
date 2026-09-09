"""Tests for the query pipeline, using stand-in services.

No Qdrant, no Gemini, no API key: the pipeline is handed fakes for the three
things it talks to. That is only possible because those three arrive as
constructor arguments rather than being created inside, which is the practical
payoff of the services layer — the retrieval flow can be tested end to end in
milliseconds.

The ordering assertions matter as much as the content ones. The interface shows
citations while the answer is still being written, and that only works if the
context event genuinely precedes the first token.
"""

import unittest

from app.core.models import Retrieved
from app.schemas import AnswerResponse
from app.services.pipeline import Pipeline

ANSWER_PIECES = ["Forking makes a copy", " of a repository", " [1]."]


class FakeStore:
    """A vector store holding a fixed set of passages."""

    def __init__(self, dense: list[Retrieved], sparse: list[Retrieved]) -> None:
        self.dense = dense
        self.sparse = sparse
        self.count = len({item.id for item in dense + sparse})

    async def ensure_ready(self) -> None:
        return None

    async def count_for_session(self, session_id: str) -> int:
        return self.count

    async def search_dense(self, session_id: str, vector: list[float], limit: int):
        return self.dense[:limit]

    async def search_sparse(self, session_id: str, indices, values, limit: int):
        return self.sparse[:limit]


class FakeEmbedder:
    async def embed_query(self, question: str) -> list[float]:
        return [0.1, 0.2, 0.3]


class FakeLLM:
    """Reranks by truncation, and answers in fixed pieces."""

    def __init__(self, reranked: bool = True) -> None:
        self.reranked = reranked

    async def rerank(self, question, candidates, top_k):
        return candidates[:top_k], self.reranked

    async def answer_stream(self, question, sources):
        for piece in ANSWER_PIECES:
            yield piece


def passage(identifier: str, source: str = "readme.md") -> Retrieved:
    return Retrieved(id=identifier, text=f"text of {identifier}", source_name=source)


def build(dense=None, sparse=None, *, reranked=True, context_passages=2) -> Pipeline:
    return Pipeline(
        store=FakeStore(dense if dense is not None else [], sparse if sparse is not None else []),
        embedder=FakeEmbedder(),
        llm=FakeLLM(reranked=reranked),
        retrieval_candidates=10,
        context_passages=context_passages,
        max_session_passages=100,
    )


class AskStreamTests(unittest.IsolatedAsyncioTestCase):
    async def collect(self, pipeline: Pipeline, question: str = "What is forking?"):
        return [event async for event in pipeline.ask_stream("session", question)]

    async def test_stages_are_announced_in_pipeline_order(self) -> None:
        events = await self.collect(build([passage("a")], [passage("b")]))
        stages = [event["stage"] for event in events if event["type"] == "stage"]
        self.assertEqual(stages, ["embedding", "searching", "reranking", "writing"])

    async def test_citations_arrive_before_the_first_token(self) -> None:
        # The whole point of streaming here: the reader sees the sources while
        # the answer is still being written.
        kinds = [event["type"] for event in await self.collect(build([passage("a")], [passage("b")]))]
        self.assertLess(kinds.index("context"), kinds.index("token"))

    async def test_the_last_event_carries_the_timings(self) -> None:
        events = await self.collect(build([passage("a")], []))
        self.assertEqual(events[-1]["type"], "done")
        self.assertIn("total_ms", events[-1]["timings"])

    async def test_context_reports_what_each_retriever_returned(self) -> None:
        dense = [passage("a"), passage("b")]
        sparse = [passage("b")]
        events = await self.collect(build(dense, sparse))
        context = next(event for event in events if event["type"] == "context")
        self.assertEqual(context["dense_hits"], 2)
        self.assertEqual(context["sparse_hits"], 1)
        self.assertEqual(context["candidates_considered"], 2)
        self.assertTrue(context["reranked"])

    async def test_citations_are_numbered_and_record_how_they_were_found(self) -> None:
        events = await self.collect(build([passage("a"), passage("b")], [passage("b")]))
        citations = next(event for event in events if event["type"] == "context")["citations"]
        self.assertEqual([item["number"] for item in citations], [1, 2])
        found = {item["number"]: item for item in citations}
        # "b" was returned by both searches, so fusion ranks it first.
        self.assertEqual(found[1]["dense_rank"], 2)
        self.assertEqual(found[1]["sparse_rank"], 1)
        self.assertIsNone(found[2]["sparse_rank"])

    async def test_a_failed_rerank_is_reported_rather_than_hidden(self) -> None:
        events = await self.collect(build([passage("a")], [passage("b")], reranked=False))
        context = next(event for event in events if event["type"] == "context")
        self.assertFalse(context["reranked"])

    async def test_an_empty_session_says_so_without_running_the_pipeline(self) -> None:
        events = await self.collect(build([], []))
        self.assertNotIn("stage", [event["type"] for event in events])
        self.assertIn("No sources", "".join(
            str(event["text"]) for event in events if event["type"] == "token"
        ))

    async def test_no_matching_passages_is_reported(self) -> None:
        pipeline = build([], [])
        pipeline._store.count = 5  # indexed, but neither search matched
        events = await self.collect(pipeline)
        text = "".join(str(event["text"]) for event in events if event["type"] == "token")
        self.assertIn("Nothing in the indexed sources matched", text)


class AskTests(unittest.IsolatedAsyncioTestCase):
    async def test_the_json_form_assembles_the_streamed_pieces(self) -> None:
        result = await build([passage("a")], [passage("b")]).ask("session", "What is forking?")
        self.assertIsInstance(result, AnswerResponse)
        self.assertEqual(result.answer, "".join(ANSWER_PIECES).strip())
        self.assertEqual(len(result.citations), 2)
        self.assertTrue(result.reranked)
        self.assertGreaterEqual(result.timings.total_ms, 0)

    async def test_context_passages_caps_how_many_reach_the_model(self) -> None:
        dense = [passage(letter) for letter in "abcde"]
        result = await build(dense, [], context_passages=2).ask("session", "What is forking?")
        self.assertEqual(len(result.citations), 2)


if __name__ == "__main__":
    unittest.main()
