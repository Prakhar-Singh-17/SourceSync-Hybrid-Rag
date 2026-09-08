from dataclasses import dataclass
import re


@dataclass(frozen=True)
class TextChunk:
    index: int
    text: str
    start: int
    end: int


def split_text(text: str, chunk_size: int = 1200, overlap: int = 180) -> list[TextChunk]:
    if chunk_size <= 0 or overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be non-negative and smaller than chunk_size")

    normalized = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not normalized:
        return []

    chunks: list[TextChunk] = []
    start = 0
    while start < len(normalized):
        end = min(start + chunk_size, len(normalized))
        if end < len(normalized):
            boundary = max(normalized.rfind("\n\n", start, end), normalized.rfind(" ", start, end))
            if boundary > start + chunk_size // 2:
                end = boundary
        chunk_text = normalized[start:end].strip()
        if chunk_text:
            actual_start = normalized.find(chunk_text, start, end)
            actual_end = actual_start + len(chunk_text)
            chunks.append(TextChunk(len(chunks), chunk_text, actual_start, actual_end))
        if end >= len(normalized):
            break
        start = max(end - overlap, start + 1)
    return chunks
