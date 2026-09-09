"""Plain data structures shared by the ingestion and query pipelines."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Passage:
    """One slice of a source, ready to be embedded and stored."""

    text: str
    index: int
    source_name: str
    file_path: str | None = None
    page_number: int | None = None

    @property
    def embedding_text(self) -> str:
        """The text actually sent to the embedding model.

        The location is prepended so the vector carries a hint of *where* the
        passage came from.  This matters most for code: a question like "how
        does the session cookie get set" should be pulled toward
        ``app/sessions.py`` by the path alone, even when the passage body never
        repeats the file name.
        """
        return f"# {self.location}\n\n{self.text}"

    @property
    def location(self) -> str:
        base = self.file_path or self.source_name
        return f"{base} (page {self.page_number})" if self.page_number else base


@dataclass
class Retrieved:
    """A passage returned by search, annotated with how it was found.

    ``dense_rank`` and ``sparse_rank`` are kept so the UI can show *why* a
    passage surfaced -- semantic similarity, keyword match, or both.  A passage
    found by only one retriever is exactly the case hybrid search exists for.
    """

    id: str
    text: str
    source_name: str
    file_path: str | None = None
    page_number: int | None = None
    dense_rank: int | None = None
    sparse_rank: int | None = None
    fused_score: float = 0.0

    @property
    def location(self) -> str:
        base = self.file_path or self.source_name
        return f"{base} (page {self.page_number})" if self.page_number else base
