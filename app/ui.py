"""Streamlit demo UI.

    streamlit run app/ui.py

Calls the service layer directly rather than going over HTTP, so the demo needs one process.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Streamlit executes this file as a script, so the project root is not on sys.path yet.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st  # noqa: E402

from app.config import settings  # noqa: E402
from app.rag import index_is_empty, index_size, retrieve_traced  # noqa: E402
from app.schemas import ApprovalRequest, InvestigateRequest, IssueKind  # noqa: E402
from app.service import KnowledgeBaseEmpty, investigate, resume  # noqa: E402

SCENARIOS = {
    "Scenario 1 — knowledge question": "What conditions are required for READY_FOR_DISPATCH?",
    "Scenario 2 — root-cause investigation": "Why is shipment SHP-1007 stuck in CREATED?",
    "Scenario 3 — human approval": "Suggest how to fix shipment SHP-1007.",
    "Trailer in maintenance": "Why is shipment SHP-1010 not dispatching?",
    "Inbound-only facility": "Why is shipment SHP-1013 stuck?",
    "Escalation policy (PDF source)": "Which escalation tier owns a shipment blocked by a disabled facility?",
    "Source code question": "Which BlockReason does the workflow service return when trailer_id is null?",
}

SOURCE_ICONS = {"knowledge": "Documentation", "logs": "Application logs", "database": "Database"}

st.set_page_config(page_title="AI Production Issue Investigator", page_icon="🔍", layout="wide")


def init_state() -> None:
    st.session_state.setdefault("response", None)
    st.session_state.setdefault("question", SCENARIOS["Scenario 2 — root-cause investigation"])
    st.session_state.setdefault("error", None)


def sidebar() -> bool:
    with st.sidebar:
        st.header("Runtime")
        st.caption("Every inference call stays on this machine.")

        active = settings.chat_model_fast if settings.fast_mode else settings.chat_model
        st.metric("Reasoning model", active)
        st.text(f"Embeddings: {settings.embedding_model}")
        st.text(f"Ollama: {settings.ollama_base_url}")

        fast = st.toggle(
            "Fast mode",
            value=settings.fast_mode,
            help=f"Use {settings.chat_model_fast} instead of {settings.chat_model}.",
        )

        st.divider()
        st.header("Retrieval")

        # These write straight back to the settings object, so the change applies to the next
        # query. It makes the difference between the configurations demonstrable live rather
        # than only in the evaluation table.
        hybrid = st.toggle(
            "Hybrid search",
            value=settings.retrieval_mode == "hybrid",
            help="Fuse dense vector search with BM25 keyword search. Off is dense only.",
        )
        settings.retrieval_mode = "hybrid" if hybrid else "vector"

        settings.rerank_enabled = st.toggle(
            "Cross-encoder rerank",
            value=settings.rerank_enabled,
            help=f"Rescore fused candidates with {settings.reranker_model}.",
        )
        st.caption(
            f"{settings.dense_k} dense + {settings.sparse_k} sparse candidates, "
            f"top {settings.final_k} to the model."
        )

        st.divider()
        st.header("Demo scenarios")
        for label, question in SCENARIOS.items():
            if st.button(label, use_container_width=True):
                st.session_state.question = question
                st.session_state.response = None

        st.divider()
        if index_is_empty():
            st.error("Knowledge index is empty.\n\nRun `python scripts/bootstrap.py`.")
        else:
            st.success(f"Knowledge index ready — {index_size()} chunks")

        return fast


def render_plan(response) -> None:
    if not response.plan:
        return
    chosen = [
        (name, on)
        for name, on in (
            ("Documentation", response.plan.search_knowledge),
            ("Application logs", response.plan.inspect_logs),
            ("Database", response.plan.query_database),
        )
    ]
    cols = st.columns(len(chosen))
    for col, (name, on) in zip(cols, chosen):
        col.metric(name, "Used" if on else "Skipped")
    if response.plan.reasoning:
        st.caption(response.plan.reasoning)


def render_report(response) -> None:
    report = response.report
    if not report:
        return

    st.subheader("Root-cause analysis")

    left, right = st.columns([3, 1])
    with left:
        st.markdown(f"**Root cause**\n\n{report.root_cause}")
    with right:
        st.metric("Confidence", f"{report.confidence}%")
        st.progress(report.confidence / 100)

    st.markdown("**Evidence**")
    for item in report.evidence:
        st.markdown(f"- {item}")

    st.markdown("**Recommended action**")
    if report.requires_approval:
        st.warning(report.recommended_action)
    else:
        st.info(report.recommended_action)


def render_approval(response) -> None:
    if not response.awaiting_approval:
        return

    st.subheader("Human review required")
    st.caption(
        "The graph is paused on a checkpoint. Nothing will be executed until a human decides."
    )

    decision_col, modify_col = st.columns([1, 2])
    with decision_col:
        if st.button("Approve", type="primary", use_container_width=True):
            _resume(response.thread_id, "approve")
        if st.button("Reject", use_container_width=True):
            _resume(response.thread_id, "reject")
    with modify_col:
        modified = st.text_input("Or replace the action with your own wording")
        if st.button("Submit modification", use_container_width=True) and modified.strip():
            _resume(response.thread_id, modified.strip())


def _resume(thread_id: str, decision: str) -> None:
    with st.spinner("Resuming the workflow..."):
        st.session_state.response = resume(
            ApprovalRequest(thread_id=thread_id, decision=decision)
        )
    st.rerun()


def render_evidence(response) -> None:
    if not response.evidence:
        return
    st.subheader("Evidence collected")
    tabs = st.tabs([SOURCE_ICONS.get(i.source, i.source) for i in response.evidence])
    for tab, item in zip(tabs, response.evidence):
        with tab:
            st.code(item.content, language="text")


def render_sources(response) -> None:
    """The passages the model was allowed to use, and whether it stayed inside them."""
    if not response.citations:
        return

    grounding = response.grounding
    cited = set(grounding.cited_markers) if grounding else set()

    st.subheader("Sources")
    if grounding and not grounding.grounded:
        st.warning(grounding.note)
    elif cited:
        st.caption(
            f"Every claim is traceable: {len(cited)} of {len(response.citations)} retrieved "
            "passages were cited, and all markers resolve to a real chunk."
        )

    for citation in response.citations:
        used = "cited" if citation.marker in cited else "retrieved, not cited"
        label = f"[{citation.marker}] {citation.source}"
        if citation.section:
            label += f" — {citation.section}"
        with st.expander(f"{label}  ·  score {citation.score:.3f}  ·  {used}"):
            st.text(citation.excerpt)


def render_retrieval_debug(question: str) -> None:
    """Re-run retrieval for the question and show what each stage did.

    Worth surfacing in the demo because it turns "the model found the right document" into
    something an audience can verify.
    """
    with st.expander("Retrieval pipeline"):
        if not question.strip():
            st.caption("Ask something first.")
            return

        trace = retrieve_traced(question)
        stages = st.columns(3 if trace.sparse else 2)

        with stages[0]:
            st.markdown(f"**Dense** ({len(trace.dense)})")
            for chunk in trace.dense[:8]:
                st.caption(f"{chunk.dense_rank}. {chunk.source} — {chunk.section or '-'}")

        column = 1
        if trace.sparse:
            with stages[column]:
                st.markdown(f"**BM25** ({len(trace.sparse)})")
                for chunk in trace.sparse[:8]:
                    st.caption(f"{chunk.sparse_rank}. {chunk.source} — {chunk.section or '-'}")
            column += 1

        with stages[column]:
            st.markdown("**Reranked**" if trace.reranked else "**Fused**")
            for rank, chunk in enumerate(trace.final, start=1):
                st.caption(f"{rank}. {chunk.source} — {chunk.section or '-'} ({chunk.score:.3f})")

        st.caption(
            f"Mode: {trace.mode}. "
            + ("Cross-encoder applied." if trace.reranked else "No reranking.")
        )


def main() -> None:
    init_state()
    fast = sidebar()

    st.title("AI Production Issue Investigator")
    st.caption(
        "LangChain supplies the building blocks, LangGraph governs the workflow, and a local "
        "Ollama model provides the reasoning. Answers are grounded in retrieved passages and "
        "every claim carries a source. No data leaves this machine."
    )

    question = st.text_area("Describe the production issue", value=st.session_state.question, height=90)

    run, _ = st.columns([1, 5])
    if run.button("Investigate", type="primary", use_container_width=True):
        st.session_state.question = question
        st.session_state.error = None
        try:
            with st.spinner("Planning, gathering evidence and correlating..."):
                st.session_state.response = investigate(
                    InvestigateRequest(question=question, fast=fast)
                )
        except KnowledgeBaseEmpty as exc:
            st.session_state.error = str(exc)
            st.session_state.response = None

    if st.session_state.error:
        st.error(st.session_state.error)

    response = st.session_state.response
    if not response:
        return

    st.divider()
    st.markdown(f"**Classified as** `{response.kind.value if response.kind else '-'}` — {response.summary}")
    render_plan(response)

    with st.expander("Workflow trace", expanded=True):
        for step in response.trace:
            st.markdown(f"- {step}")
        if response.loops > 1:
            st.caption(f"The graph re-planned {response.loops - 1} time(s) to close evidence gaps.")

    if response.kind == IssueKind.KNOWLEDGE and response.answer:
        st.subheader("Answer")
        st.markdown(response.answer)

    render_report(response)
    render_approval(response)
    render_sources(response)
    render_retrieval_debug(st.session_state.question)
    render_evidence(response)

    st.caption(f"Thread: `{response.thread_id}` — reuse it to ask a follow-up with memory.")


main()
