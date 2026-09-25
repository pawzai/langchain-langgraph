"""The retrieval pipeline.

    query -> dense (Chroma) + sparse (BM25) -> RRF fusion -> cross-encoder rerank -> top k

Each stage exists to cover a specific failure of the one before it. Dense search understands
that "stuck before dispatch" and "blocked CREATED transition" mean the same thing, but it will
happily miss an exact token like `SHP-1007` or `outbound_enabled` that appears nowhere in its
training distribution. BM25 catches those literal tokens and misses the paraphrase. Fusing the
two ranked lists covers both, at the cost of admitting more marginal chunks — which is what the
reranker is then there to filter out.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

from langchain_chroma import Chroma
from langchain_core.documents import Document

from app import rerank as reranker
from app.config import settings
from app.ingest import load_documents
from app.llm import get_embeddings

# The RRF smoothing constant. 60 is the value from the original paper and the de facto default;
# it damps the influence of the top one or two positions so a single confident-but-wrong
# retriever cannot dominate the fused ranking.
RRF_K = 60


@dataclass
class IndexStats:
    added: int = 0
    removed: int = 0
    unchanged: int = 0
    total: int = 0

    def as_dict(self) -> dict:
        return {
            "added": self.added,
            "removed": self.removed,
            "unchanged": self.unchanged,
            "total": self.total,
        }


@dataclass
class ScoredChunk:
    """A retrieved chunk with the score from every stage that touched it.

    Keeping all of them, rather than collapsing to one number, is what makes the debug endpoint
    and the evaluation harness able to explain *why* a chunk ended up where it did.
    """

    document: Document
    dense_rank: int | None = None
    dense_distance: float | None = None
    sparse_rank: int | None = None
    fused_score: float = 0.0
    rerank_score: float | None = None

    @property
    def chunk_id(self) -> str:
        return str(self.document.metadata.get("chunk_id", ""))

    @property
    def source(self) -> str:
        return str(self.document.metadata.get("source", "unknown"))

    @property
    def section(self) -> str:
        return str(self.document.metadata.get("section", ""))

    @property
    def text(self) -> str:
        return self.document.page_content.strip()

    @property
    def score(self) -> float:
        """The score that decided the final ordering."""
        return self.rerank_score if self.rerank_score is not None else self.fused_score

    def label(self) -> str:
        return f"{self.source} — {self.section}" if self.section else self.source


# --- Index ---


@lru_cache(maxsize=1)
def get_vector_store() -> Chroma:
    return Chroma(
        collection_name=settings.chroma_collection,
        embedding_function=get_embeddings(),
        persist_directory=str(settings.chroma_dir),
    )


def build_index(reset: bool = False) -> IndexStats:
    """Sync the vector store with the knowledge directory.

    Incremental by default: because `chunk_id` is a hash of the chunk's own content, an
    unchanged chunk keeps its id across runs, so re-indexing after editing one paragraph
    re-embeds one chunk instead of the whole corpus.
    """
    settings.chroma_dir.mkdir(parents=True, exist_ok=True)
    store = get_vector_store()

    if reset:
        existing_ids = store.get()["ids"]
        if existing_ids:
            store.delete(ids=existing_ids)
        existing: set[str] = set()
    else:
        existing = set(store.get()["ids"])

    docs = load_documents()
    wanted = {doc.metadata["chunk_id"]: doc for doc in docs}

    to_add = [chunk_id for chunk_id in wanted if chunk_id not in existing]
    to_remove = [chunk_id for chunk_id in existing if chunk_id not in wanted]

    if to_add:
        store.add_documents([wanted[chunk_id] for chunk_id in to_add], ids=to_add)
    if to_remove:
        store.delete(ids=to_remove)

    _bm25_corpus.cache_clear()
    return IndexStats(
        added=len(to_add),
        removed=len(to_remove),
        unchanged=len(wanted) - len(to_add),
        total=len(wanted),
    )


def index_is_empty() -> bool:
    try:
        return not get_vector_store().get(limit=1)["ids"]
    except Exception:  # noqa: BLE001 - an unreadable store is an empty store for our purposes
        return True


def index_size() -> int:
    try:
        return len(get_vector_store().get(include=[])["ids"])
    except Exception:  # noqa: BLE001
        return 0


# --- Sparse retrieval ---


@lru_cache(maxsize=1)
def _bm25_corpus() -> list[Document]:
    """Read the indexed chunks back out of Chroma to build the keyword index from.

    Rebuilding BM25 from the persisted store rather than re-chunking the source files means the
    two indexes are the same set of chunks by construction and cannot silently drift apart.
    """
    try:
        raw = get_vector_store().get(include=["documents", "metadatas"])
    except Exception:  # noqa: BLE001
        return []

    return [
        Document(page_content=text, metadata=dict(meta or {}))
        for text, meta in zip(raw.get("documents") or [], raw.get("metadatas") or [])
    ]


def _sparse_search(query: str, k: int) -> list[Document]:
    corpus = _bm25_corpus()
    if not corpus:
        return []
    try:
        from langchain_community.retrievers import BM25Retriever
    except ImportError:
        return []

    retriever = BM25Retriever.from_documents(corpus)
    retriever.k = min(k, len(corpus))
    return retriever.invoke(query)


def _dense_search(query: str, k: int) -> list[tuple[Document, float]]:
    # The raw distance is kept for display only. Fusion deliberately uses rank rather than
    # score, because a cosine distance and a BM25 score are not on any common scale.
    return get_vector_store().similarity_search_with_score(query, k=k)


# --- Fusion ---


def _fuse(
    dense: list[tuple[Document, float]], sparse: list[Document]
) -> list[ScoredChunk]:
    """Reciprocal Rank Fusion: score = sum over lists of 1 / (RRF_K + rank)."""
    merged: dict[str, ScoredChunk] = {}

    def slot(doc: Document) -> ScoredChunk:
        key = str(doc.metadata.get("chunk_id")) or doc.page_content[:64]
        if key not in merged:
            merged[key] = ScoredChunk(document=doc)
        return merged[key]

    for rank, (doc, distance) in enumerate(dense, start=1):
        chunk = slot(doc)
        chunk.dense_rank = rank
        chunk.dense_distance = float(distance)
        chunk.fused_score += 1.0 / (RRF_K + rank)

    for rank, doc in enumerate(sparse, start=1):
        chunk = slot(doc)
        chunk.sparse_rank = rank
        chunk.fused_score += 1.0 / (RRF_K + rank)

    return sorted(merged.values(), key=lambda c: c.fused_score, reverse=True)


# --- Public API ---


@dataclass
class RetrievalTrace:
    """Every stage of one retrieval, for the debug endpoint and the evaluation harness."""

    query: str
    mode: str
    reranked: bool
    dense: list[ScoredChunk] = field(default_factory=list)
    sparse: list[ScoredChunk] = field(default_factory=list)
    fused: list[ScoredChunk] = field(default_factory=list)
    final: list[ScoredChunk] = field(default_factory=list)


def retrieve_traced(
    query: str,
    k: int | None = None,
    mode: str | None = None,
    use_reranker: bool | None = None,
) -> RetrievalTrace:
    k = k or settings.final_k
    mode = mode or settings.retrieval_mode
    use_reranker = settings.rerank_enabled if use_reranker is None else use_reranker

    trace = RetrievalTrace(query=query, mode=mode, reranked=False)
    if not query or not query.strip():
        return trace

    dense_hits = _dense_search(query, settings.dense_k)
    trace.dense = [
        ScoredChunk(document=doc, dense_rank=rank, dense_distance=float(distance))
        for rank, (doc, distance) in enumerate(dense_hits, start=1)
    ]

    sparse_hits: list[Document] = []
    if mode == "hybrid":
        sparse_hits = _sparse_search(query, settings.sparse_k)
        trace.sparse = [
            ScoredChunk(document=doc, sparse_rank=rank)
            for rank, doc in enumerate(sparse_hits, start=1)
        ]

    trace.fused = _fuse(dense_hits, sparse_hits)

    candidates = trace.fused
    if use_reranker and candidates and reranker.available():
        try:
            scores = reranker.score(query, [c.text for c in candidates])
            for chunk, value in zip(candidates, scores):
                chunk.rerank_score = value
            candidates = sorted(
                (c for c in candidates if c.rerank_score >= settings.min_rerank_score),
                key=lambda c: c.rerank_score,
                reverse=True,
            )
            trace.reranked = True
        except Exception:  # noqa: BLE001 - a reranker failure must not lose the results
            candidates = trace.fused

    trace.final = candidates[:k]
    return trace


def retrieve(
    query: str,
    k: int | None = None,
    mode: str | None = None,
    use_reranker: bool | None = None,
) -> list[ScoredChunk]:
    return retrieve_traced(query, k=k, mode=mode, use_reranker=use_reranker).final
