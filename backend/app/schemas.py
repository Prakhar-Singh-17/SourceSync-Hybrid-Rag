"""Request and response models.

Every endpoint declares its response type, so the generated OpenAPI page at
``/docs`` documents the real shape of the API instead of an opaque object.  The
previous handlers all returned bare dictionaries, which meant the docs said
nothing at all.
"""

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2_000)


class RepositoryRequest(BaseModel):
    url: str = Field(max_length=500)


class Citation(BaseModel):
    """One passage that was placed in front of the model, and how it got there.

    ``dense_rank`` and ``sparse_rank`` are surfaced deliberately: they let the
    interface show whether a passage was found by meaning, by keyword, or by
    both, which is the clearest possible demonstration of what hybrid retrieval
    is actually doing.
    """

    number: int
    source_name: str
    file_path: str | None = None
    page_number: int | None = None
    location: str
    snippet: str
    dense_rank: int | None = None
    sparse_rank: int | None = None
    fused_score: float = 0.0


class Timings(BaseModel):
    """Per-stage latency in milliseconds, so slow questions can be diagnosed."""

    embed_ms: int = 0
    search_ms: int = 0
    rerank_ms: int = 0
    generate_ms: int = 0
    total_ms: int = 0


class AnswerResponse(BaseModel):
    answer: str
    citations: list[Citation] = []
    reranked: bool = True
    candidates_considered: int = 0
    dense_hits: int = 0
    sparse_hits: int = 0
    timings: Timings = Timings()


class IngestResponse(BaseModel):
    status: str = "indexed"
    source_name: str
    file_count: int | None = None
    passage_count: int
    total_passages: int


class SourceSummary(BaseModel):
    """One indexed source and how many passages it contributed."""

    name: str
    passage_count: int


class SessionResponse(BaseModel):
    status: str = "ok"
    expires_at: str
    passage_count: int = 0
    # Read back from the store rather than tracked in the browser, so the list
    # survives a page reload.
    sources: list[SourceSummary] = []


class HealthResponse(BaseModel):
    status: str
    service: str
    detail: str | None = None
