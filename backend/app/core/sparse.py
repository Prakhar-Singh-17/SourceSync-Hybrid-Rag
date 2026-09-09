"""Lexical (keyword) matching, expressed as a sparse vector.

Dense embeddings capture meaning but reliably miss *exact tokens*: an error
code, a function name, a version number, a rare acronym.  Ask "what does
ensure_collection do" and a dense-only search happily returns passages about
"setting up the database" while missing the function itself.

A sparse vector fixes that.  Each dimension is one term, so a passage scores
against a query only when they literally share words.  Qdrant stores it next to
the dense vector and -- because the collection is created with
``Modifier.IDF`` -- applies the inverse-document-frequency half of BM25 itself,
using corpus statistics we do not have on the client.

So the value written here is only the term-frequency half of BM25:

    tf * (k1 + 1) / (tf + k1)

which saturates: the tenth occurrence of a word adds far less than the second.
The usual document-length normalisation (BM25's ``b`` term) is left out because
the chunker already caps every passage at roughly the same size, which makes
that correction close to a no-op.
"""

import re
from collections import Counter
from zlib import crc32

BM25_K1 = 1.2
MIN_TOKEN_LENGTH = 2

# Very common English words carry no signal but appear in every passage, so they
# would waste a dimension in every single vector.
STOP_WORDS = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "can", "do", "does",
    "for", "from", "has", "have", "how", "in", "is", "it", "its", "of", "on",
    "or", "that", "the", "then", "there", "these", "this", "to", "used", "was",
    "what", "when", "where", "which", "who", "why", "will", "with", "you",
})

_WORD = re.compile(r"[A-Za-z0-9_]+")
# Splits getUserName -> get, User, Name and HTTPServer -> HTTP, Server
_SUBWORD = re.compile(r"[A-Z]?[a-z]+|[A-Z]{2,}(?![a-z])|\d+")


def tokenize(text: str) -> list[str]:
    """Break text into search terms.

    Identifiers are additionally split on camelCase and underscores, so a
    question asking about "session cookie" still matches a passage that only
    ever writes ``set_session_cookie``.  The whole identifier is kept as well,
    so an exact-name search stays the strongest possible match.
    """
    tokens: list[str] = []
    for word in _WORD.findall(text):
        lowered = word.lower()
        if _is_useful(lowered):
            tokens.append(lowered)
        if "_" in word or not word.islower():
            for part in _SUBWORD.findall(word):
                part = part.lower()
                if part != lowered and _is_useful(part):
                    tokens.append(part)
    return tokens


def term_id(token: str) -> int:
    """Map a term to the unsigned 32-bit dimension index Qdrant expects.

    CRC32 rather than the built-in ``hash``: Python randomises string hashing
    per process (PYTHONHASHSEED), so ``hash`` would assign a term one dimension
    at ingest time and a different one at query time in a restarted worker.
    CRC32 is stable forever, which is what a persisted index requires.
    """
    return crc32(token.encode("utf-8"))


def sparse_vector(text: str) -> tuple[list[int], list[float]]:
    """Return ``(indices, values)`` for the BM25 term-frequency vector of ``text``."""
    counts = Counter(tokenize(text))
    if not counts:
        return [], []
    indices: list[int] = []
    values: list[float] = []
    for token, count in counts.items():
        indices.append(term_id(token))
        values.append(count * (BM25_K1 + 1.0) / (count + BM25_K1))
    return indices, values


def _is_useful(token: str) -> bool:
    return len(token) >= MIN_TOKEN_LENGTH and token not in STOP_WORDS
