"""Splitting a source into overlapping passages.

Embedding models have a fixed input budget, and a passage that covers three
unrelated topics produces a vector that sits between all three and matches none
of them well.  So sources are cut into passages of roughly uniform size.

Two strategies, because prose and code break differently:

* :func:`split_prose` walks a character window and backs up to the nearest
  paragraph or word boundary.
* :func:`split_code` never cuts inside a line -- half a line of source code is
  useless as context.

Both overlap consecutive passages, so a sentence (or a short function) sitting
on a boundary still appears intact in at least one of them.
"""

import re

DEFAULT_CHUNK_SIZE = 1200
DEFAULT_OVERLAP = 180
CODE_OVERLAP_LINES = 5

_BLANK_LINES = re.compile(r"\n{3,}")


def split_prose(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_OVERLAP,
) -> list[str]:
    """Split prose into overlapping passages of at most ``chunk_size`` characters."""
    if chunk_size <= 0 or not 0 <= overlap < chunk_size:
        raise ValueError("overlap must be non-negative and smaller than chunk_size")

    normalized = _BLANK_LINES.sub("\n\n", text).strip()
    if not normalized:
        return []

    passages: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(start + chunk_size, len(normalized))
        if end < len(normalized):
            # Prefer a paragraph break, then a word break, but only if it does
            # not shrink the passage to less than half the target size.
            boundary = max(
                normalized.rfind("\n\n", start, end),
                normalized.rfind(" ", start, end),
            )
            if boundary > start + chunk_size // 2:
                end = boundary
        passage = normalized[start:end].strip()
        if passage:
            passages.append(passage)
        if end >= len(normalized):
            break
        start = max(end - overlap, start + 1)
    return passages


def split_code(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap_lines: int = CODE_OVERLAP_LINES,
) -> list[str]:
    """Split source code on line boundaries, repeating a few lines of context."""
    if chunk_size <= 0 or overlap_lines < 0:
        raise ValueError("chunk_size must be positive and overlap_lines non-negative")

    lines = [part for line in text.splitlines() for part in _hard_wrap(line, chunk_size)]
    if not any(line.strip() for line in lines):
        return []

    passages: list[str] = []
    current: list[str] = []
    size = 0
    for line in lines:
        if current and size + len(line) + 1 > chunk_size:
            passages.append("\n".join(current))
            current = _overlap_tail(current, overlap_lines, chunk_size // 3)
            size = sum(len(item) + 1 for item in current)
        current.append(line)
        size += len(line) + 1
    if any(line.strip() for line in current):
        passages.append("\n".join(current))
    return passages


def _overlap_tail(lines: list[str], overlap_lines: int, budget: int) -> list[str]:
    """Take up to ``overlap_lines`` trailing lines, without blowing the budget.

    Carrying context forward must never make the next passage bigger than the
    chunk size, which it otherwise would for files of very long lines.
    """
    if overlap_lines <= 0:
        return []
    tail: list[str] = []
    total = 0
    for line in reversed(lines[-overlap_lines:]):
        if total + len(line) + 1 > budget:
            break
        total += len(line) + 1
        tail.insert(0, line)
    return tail


def _hard_wrap(line: str, width: int) -> list[str]:
    """Break a pathologically long line (minified JS, embedded data) into pieces."""
    if len(line) <= width:
        return [line]
    return [line[index : index + width] for index in range(0, len(line), width)]
