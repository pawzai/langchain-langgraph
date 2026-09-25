"""Investigation service shared by the API and the Streamlit UI."""

from __future__ import annotations

import uuid

from langgraph.types import Command

from app.graph.build import get_graph
from app.rag import index_is_empty
from app.schemas import ApprovalRequest, InvestigateRequest, InvestigateResponse


class KnowledgeBaseEmpty(RuntimeError):
    """Raised when the vector index has not been built yet."""


def _config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


def _to_response(thread_id: str, state: dict, interrupts) -> InvestigateResponse:
    return InvestigateResponse(
        thread_id=thread_id,
        kind=state.get("understanding").kind if state.get("understanding") else None,
        summary=state.get("understanding").summary if state.get("understanding") else "",
        plan=state.get("plan"),
        evidence=state.get("evidence", []),
        citations=state.get("citations", []),
        grounding=state.get("grounding"),
        report=state.get("report"),
        answer=state.get("answer", ""),
        loops=state.get("loops", 0),
        awaiting_approval=bool(interrupts),
        trace=state.get("trace", []),
    )


def investigate(request: InvestigateRequest) -> InvestigateResponse:
    if index_is_empty():
        raise KnowledgeBaseEmpty(
            "The knowledge index is empty. Run: python scripts/bootstrap.py"
        )

    thread_id = request.thread_id or str(uuid.uuid4())
    graph = get_graph()
    config = _config(thread_id)

    result = graph.invoke(
        {
            "question": request.question,
            "fast": request.fast,
            "evidence": [],
            "trace": [],
            "citations": [],
        },
        config,
    )
    snapshot = graph.get_state(config)
    return _to_response(thread_id, result, snapshot.interrupts)


def resume(request: ApprovalRequest) -> InvestigateResponse:
    graph = get_graph()
    config = _config(request.thread_id)

    result = graph.invoke(Command(resume=request.decision), config)
    snapshot = graph.get_state(config)
    return _to_response(request.thread_id, result, snapshot.interrupts)


def pending_approval(thread_id: str) -> dict | None:
    """Return the payload the graph paused on, or None if it is not waiting."""
    snapshot = get_graph().get_state(_config(thread_id))
    if not snapshot.interrupts:
        return None
    return snapshot.interrupts[0].value
