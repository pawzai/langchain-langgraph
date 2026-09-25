"""Cross-encoder reranking.

The bi-encoder that fills the vector store embeds the query and the document independently, so
it can only ever compare two summaries of meaning. A cross-encoder reads the query and the
chunk together in one forward pass and scores the pair directly, which is markedly more
accurate — and far too slow to run over a whole corpus. Hence the standard arrangement used
here: retrieve widely and cheaply, then rerank a few dozen candidates precisely.

The model is loaded lazily so that importing this module, or running the graph with reranking
disabled, never pays the cost of loading torch.
"""

from __future__ import annotations

from collections.abc import Sequence
from functools import lru_cache

from app.config import settings


@lru_cache(maxsize=1)
def _encoder():
    from langchain_community.cross_encoders import HuggingFaceCrossEncoder

    return HuggingFaceCrossEncoder(model_name=settings.reranker_model)


def available() -> bool:
    """Whether reranking can actually run, so callers can degrade instead of crashing."""
    if not settings.rerank_enabled:
        return False
    try:
        _encoder()
        return True
    except Exception:  # noqa: BLE001 - a missing model or absent torch is a soft failure
        return False


def score(query: str, texts: Sequence[str]) -> list[float]:
    """Relevance of each text to the query. Higher is better; the scale is unbounded logits."""
    if not texts:
        return []
    return [float(s) for s in _encoder().score([(query, text) for text in texts])]


def warm_up() -> bool:
    """Load the model ahead of the first query. Returns False if it is unavailable."""
    if not available():
        return False
    score("warm up", ["warm up"])
    return True
