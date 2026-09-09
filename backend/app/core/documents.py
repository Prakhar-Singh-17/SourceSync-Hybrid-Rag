"""Turning uploaded PDF and TXT bytes into passages.

Extraction is per *page* rather than one flat blob.  That is what allows an
answer to cite "report.pdf, page 12" instead of just "report.pdf", and a
citation a reader can verify in seconds is the difference between an answer
they trust and one they have to re-check by hand.
"""

from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePath

from pypdf import PdfReader

from app.core.chunking import split_prose
from app.core.errors import SourceError, SourceTooLarge
from app.core.models import Passage

# Limits chosen for the free Render instance (512 MB RAM): a document is held
# in memory whole, and pypdf's page objects cost several times the file size.
MAX_DOCUMENT_BYTES = 15 * 1024 * 1024
MAX_PDF_PAGES = 120
ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md"}


@dataclass(frozen=True)
class Page:
    """One page of a document. ``number`` is ``None`` for formats without pages."""

    number: int | None
    text: str


def extension_of(filename: str) -> str:
    return PurePath(filename or "").suffix.lower()


def extract_pages(content: bytes, extension: str) -> list[Page]:
    """Read raw bytes into pages of text."""
    if extension not in ALLOWED_EXTENSIONS:
        raise SourceError("Only PDF, TXT and Markdown documents are supported.")
    if len(content) > MAX_DOCUMENT_BYTES:
        raise SourceTooLarge("Documents must be 15 MB or smaller.")

    if extension in {".txt", ".md"}:
        try:
            return [Page(number=None, text=content.decode("utf-8"))]
        except UnicodeDecodeError as error:
            raise SourceError("Text documents must use UTF-8 encoding.") from error

    try:
        reader = PdfReader(BytesIO(content))
        pages = reader.pages
    except Exception as error:
        raise SourceError("The PDF could not be read. It may be corrupt or encrypted.") from error

    if len(pages) > MAX_PDF_PAGES:
        raise SourceTooLarge(f"PDF documents must contain {MAX_PDF_PAGES} pages or fewer.")

    extracted = [Page(number=index, text=page.extract_text() or "") for index, page in enumerate(pages, start=1)]
    if not any(page.text.strip() for page in extracted):
        raise SourceError(
            "No text could be extracted. This PDF is likely a scan; OCR is not supported."
        )
    return extracted


def passages_from_document(pages: list[Page], source_name: str) -> list[Passage]:
    """Chunk every page and tag each passage with its page number."""
    passages: list[Passage] = []
    for page in pages:
        for text in split_prose(page.text):
            passages.append(
                Passage(
                    text=text,
                    index=len(passages),
                    source_name=source_name,
                    page_number=page.number,
                )
            )
    return passages
