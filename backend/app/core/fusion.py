"""Reciprocal Rank Fusion: merging two rankings that use different scales.

The dense search returns cosine similarities (roughly 0 to 1).  The sparse
search returns BM25 scores (unbounded, routinely above 10).  Adding them
directly would let BM25 drown out the dense signal entirely, and normalising
them is fragile because the ranges shift with every query.

RRF sidesteps the problem by discarding the scores and keeping only the
*positions*.  A passage sitting at rank ``r`` in a list contributes

    1 / (k + r)

and its final score is the sum of those contributions across every list it
appears in.  Two consequences make this work well in practice:

* A passage found by **both** retrievers is pushed above one found by only a
  single retriever -- which is exactly the agreement signal hybrid search is
  built to exploit.
* The constant ``k`` (60, from the original 2009 paper) flattens the top of each
  list.  Rank 1 scores 1/61 and rank 2 scores 1/62 -- nearly identical -- so one
  retriever that is confidently wrong cannot dominate the merged ranking.
"""

from app.core.models import Retrieved

RRF_K = 60


def reciprocal_rank_fusion(
    dense: list[Retrieved],
    sparse: list[Retrieved],
    *,
    k: int = RRF_K,
    limit: int | None = None,
) -> list[Retrieved]:
    """Merge a dense and a sparse ranking into one ordered list.

    Each returned passage records the rank it held in each input list, so the
    caller can explain *why* it surfaced.
    """
    merged: dict[str, Retrieved] = {}

    for rank, passage in enumerate(dense, start=1):
        entry = merged.setdefault(passage.id, passage)
        entry.dense_rank = rank
        entry.fused_score += 1.0 / (k + rank)

    for rank, passage in enumerate(sparse, start=1):
        entry = merged.setdefault(passage.id, passage)
        entry.sparse_rank = rank
        entry.fused_score += 1.0 / (k + rank)

    ranked = sorted(merged.values(), key=lambda passage: passage.fused_score, reverse=True)
    return ranked[:limit] if limit is not None else ranked
