"""Retrieval over the workflow and troubleshooting documentation."""

from __future__ import annotations

from langchain_core.tools import tool

from app.rag import ScoredChunk, retrieve
from app.schemas import Citation

EXCERPT_CHARS = 240


def to_citation(marker: int, chunk: ScoredChunk) -> Citation:
    excerpt = chunk.text[:EXCERPT_CHARS]
    if len(chunk.text) > EXCERPT_CHARS:
        excerpt += "..."
    return Citation(
        marker=marker,
        source=chunk.source,
        section=chunk.section,
        chunk_id=chunk.chunk_id,
        score=round(chunk.score, 4),
        excerpt=excerpt,
    )


def render_context(chunks: list[ScoredChunk]) -> str:
    """Number every passage so the model has a stable handle to cite.

    The marker has to be visible in the context for the model to be able to reference it, and
    the label has to sit next to the text so a citation carries provenance rather than just a
    number.
    """
    blocks = []
    for marker, chunk in enumerate(chunks, start=1):
        blocks.append(f"[{marker}] {chunk.label()}\n{chunk.text}")
    return "\n\n".join(blocks)


def search_documents(query: str, k: int | None = None) -> tuple[str, list[Citation]]:
    """Retrieve passages as numbered context plus the citations those numbers resolve to."""
    chunks = retrieve(query, k=k)
    if not chunks:
        return f"No documentation matched '{query}'.", []
    citations = [to_citation(i, chunk) for i, chunk in enumerate(chunks, start=1)]
    return render_context(chunks), citations


def format_documents(query: str, k: int | None = None) -> str:
    """Context only, for callers that do not track citations."""
    return search_documents(query, k=k)[0]


@tool
def search_knowledge(query: str) -> str:
    """Search the shipping workflow rules, troubleshooting guide, business conditions,
    SLA and escalation policy, and the workflow service source code.

    Use this to find the rules that govern a status transition, the documented cause of a
    symptom, an escalation tier, or the code that emits a given error. Returns numbered
    passages labelled with their source document and section.
    """
    return format_documents(query)
