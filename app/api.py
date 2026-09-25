"""FastAPI backend.

    uvicorn app.api:app --reload
"""

from __future__ import annotations

import requests
from fastapi import FastAPI, HTTPException, Query

from app import rerank
from app.config import settings
from app.rag import ScoredChunk, build_index, index_is_empty, index_size, retrieve_traced
from app.schemas import ApprovalRequest, InvestigateRequest, InvestigateResponse
from app.service import KnowledgeBaseEmpty, investigate, pending_approval, resume

app = FastAPI(
    title="AI Production Issue Investigator",
    description=(
        "LangChain + LangGraph over locally hosted Ollama models, with hybrid retrieval, "
        "cross-encoder reranking and cited sources."
    ),
    version="2.0.0",
)


@app.get("/health")
def health() -> dict:
    """Report whether Ollama, the index and the database are ready."""
    ollama_ok, models = False, []
    try:
        resp = requests.get(f"{settings.ollama_base_url}/api/tags", timeout=5)
        resp.raise_for_status()
        models = [m["name"] for m in resp.json().get("models", [])]
        ollama_ok = True
    except requests.RequestException:
        pass

    return {
        "ollama_reachable": ollama_ok,
        "chat_model": settings.chat_model_fast if settings.fast_mode else settings.chat_model,
        "embedding_model": settings.embedding_model,
        "required_models_present": all(
            m in models
            for m in (settings.chat_model, settings.chat_model_fast, settings.embedding_model)
        ),
        "knowledge_index_ready": not index_is_empty(),
        "indexed_chunks": index_size(),
        "database_present": settings.sqlite_path.exists(),
        "retrieval": {
            "mode": settings.retrieval_mode,
            "dense_k": settings.dense_k,
            "sparse_k": settings.sparse_k,
            "final_k": settings.final_k,
            "rerank_enabled": settings.rerank_enabled,
            "reranker_model": settings.reranker_model,
            "reranker_ready": rerank.available(),
        },
    }


@app.post("/investigate", response_model=InvestigateResponse)
def post_investigate(request: InvestigateRequest) -> InvestigateResponse:
    """Run an investigation. Pass the returned thread_id back to ask a follow-up."""
    try:
        return investigate(request)
    except KnowledgeBaseEmpty as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/approval/{thread_id}")
def get_approval(thread_id: str) -> dict:
    """Inspect what the graph is waiting for, if it is paused."""
    payload = pending_approval(thread_id)
    return {"awaiting_approval": payload is not None, "request": payload}


@app.post("/approval", response_model=InvestigateResponse)
def post_approval(request: ApprovalRequest) -> InvestigateResponse:
    """Resume a paused investigation with approve, reject, or modified action text."""
    if pending_approval(request.thread_id) is None:
        raise HTTPException(
            status_code=409, detail="This thread is not waiting for approval."
        )
    return resume(request)


@app.post("/reindex")
def post_reindex(reset: bool = Query(False, description="Re-embed everything, not just changes.")) -> dict:
    """Sync the vector index with the knowledge documents.

    Incremental by default, so editing one paragraph re-embeds one chunk.
    """
    return build_index(reset=reset).as_dict()


def _chunk_json(chunk: ScoredChunk) -> dict:
    return {
        "chunk_id": chunk.chunk_id,
        "source": chunk.source,
        "section": chunk.section,
        "dense_rank": chunk.dense_rank,
        "dense_distance": chunk.dense_distance,
        "sparse_rank": chunk.sparse_rank,
        "fused_score": round(chunk.fused_score, 6),
        "rerank_score": (
            round(chunk.rerank_score, 4) if chunk.rerank_score is not None else None
        ),
        "excerpt": chunk.text[:240],
    }


@app.get("/retrieval/debug")
def get_retrieval_debug(
    q: str = Query(..., description="The query to trace."),
    k: int | None = Query(None, description="Chunks to return. Defaults to FINAL_K."),
    mode: str | None = Query(None, description="'vector' or 'hybrid'. Defaults to the setting."),
    rerank_: bool | None = Query(None, alias="rerank", description="Override reranking."),
) -> dict:
    """Every stage of one retrieval, side by side.

    Answers the question you actually have when a result looks wrong: was the chunk missed by
    both retrievers, found but ranked too low to survive fusion, or found and then discarded by
    the reranker?
    """
    if mode not in (None, "vector", "hybrid"):
        raise HTTPException(status_code=422, detail="mode must be 'vector' or 'hybrid'")

    trace = retrieve_traced(q, k=k, mode=mode, use_reranker=rerank_)
    return {
        "query": trace.query,
        "mode": trace.mode,
        "reranked": trace.reranked,
        "dense": [_chunk_json(c) for c in trace.dense],
        "sparse": [_chunk_json(c) for c in trace.sparse],
        "fused": [_chunk_json(c) for c in trace.fused],
        "final": [_chunk_json(c) for c in trace.final],
    }
