"""The nodes of the investigation workflow.

Each node is a small, testable function that takes state and returns only the keys it changes.
Model calls use structured output so routing decisions are typed data rather than parsed prose.
"""

from __future__ import annotations

import re

from langgraph.types import interrupt

from app.config import settings
from app.llm import get_chat_model
from app.schemas import (
    Citation,
    EvidenceItem,
    EvidenceVerdict,
    GroundingCheck,
    InvestigationPlan,
    IssueKind,
    IssueUnderstanding,
    RootCauseReport,
)
from app.tools.knowledge import search_documents
from app.tools.logs import search_log_files
from app.tools.sql import DATABASE_SCHEMA, run_query
from app.graph.state import InvestigationState


def _model(state: InvestigationState):
    """Model for this request. `fast` is per-request state, not a global setting."""
    return get_chat_model(state.get("fast"))


def _structured(schema, state: InvestigationState):
    return _model(state).with_structured_output(schema)


# --- 1. Understand ---

UNDERSTAND_PROMPT = """You triage production issues for a shipping platform.

Classify the user's request and extract any identifiers.

Classify as:
- "knowledge" when the answer is a documented rule or policy and no specific incident is named.
- "investigation" when a specific entity is misbehaving and evidence is needed to find the cause.
- "remediation" when the user wants a fix applied or asks how to fix a specific incident.

Shipment identifiers look like SHP-1007. Trailer identifiers look like TRL-311.

Request: {question}"""


def understand_issue(state: InvestigationState) -> dict:
    result = _structured(IssueUnderstanding, state).invoke(
        UNDERSTAND_PROMPT.format(question=state["question"])
    )
    return {
        "understanding": result,
        "trace": [
            f"Reasoning with {_model(state).model}.",
            f"Understood the request as a {result.kind.value} question.",
        ],
    }


# --- 2. Plan ---

PLAN_PROMPT = """You are planning an investigation for a shipping platform.

Three read-only sources are available:
- knowledge: workflow rules, troubleshooting guide, business conditions and approval policy.
- logs: application log lines from the shipping services.
- database: shipment, trailer and facility tables.

Database schema:
{schema}

Choose only the sources that will actually help, and write a precise search phrase for each one
you choose.

Guidance:
- A rules or policy question needs knowledge only.
- Diagnosing a specific entity needs all three: the rule, the log error and the row itself.
- The log query works best as a bare identifier such as "SHP-1007".
- The knowledge query works best as the symptom or the rule name, not the identifier.

Issue type: {kind}
Issue: {summary}
Identifiers: {entities}
Original request: {question}{refinement}"""


def create_plan(state: InvestigationState) -> dict:
    understanding: IssueUnderstanding = state["understanding"]
    verdict: EvidenceVerdict | None = state.get("verdict")

    refinement = ""
    if verdict and not verdict.sufficient:
        suggested = [
            f"{label}: {query}"
            for label, query in (
                ("knowledge", state.get("refined_knowledge_query", "")),
                ("logs", state.get("refined_log_query", "")),
            )
            if query.strip()
        ]
        refinement = (
            f"\n\nA previous attempt was insufficient. Missing: {verdict.missing}. "
            "Choose different or broader search phrases this time."
        )
        if suggested:
            refinement += "\nSuggested replacement queries — " + "; ".join(suggested)

    plan = _structured(InvestigationPlan, state).invoke(
        PLAN_PROMPT.format(
            schema=DATABASE_SCHEMA,
            kind=understanding.kind.value,
            summary=understanding.summary,
            entities=", ".join(understanding.entity_ids) or "none",
            question=state["question"],
            refinement=refinement,
        )
    )

    # Guardrails: the plan drives real branching, so repair obviously bad plans rather than
    # letting the graph fan out to nothing.
    if not (plan.search_knowledge or plan.inspect_logs or plan.query_database):
        plan.search_knowledge = True
    # A proposed fix must be checked against the documented rules and approval policy, so the
    # model is not allowed to skip the documentation here.
    if understanding.kind == IssueKind.REMEDIATION:
        plan.search_knowledge = True
    if plan.search_knowledge and not plan.knowledge_query.strip():
        plan.knowledge_query = understanding.summary or state["question"]
    if plan.inspect_logs and not plan.log_query.strip():
        plan.log_query = (
            understanding.entity_ids[0] if understanding.entity_ids else state["question"]
        )

    # Re-running an identical query would return identical evidence and burn a loop, so when the
    # validator supplied a replacement and the planner ignored it, take the validator's.
    previous: InvestigationPlan | None = state.get("plan")
    if previous:
        refined_knowledge = state.get("refined_knowledge_query", "").strip()
        refined_log = state.get("refined_log_query", "").strip()
        if refined_knowledge and plan.knowledge_query == previous.knowledge_query:
            plan.knowledge_query = refined_knowledge
        if refined_log and plan.log_query == previous.log_query:
            plan.log_query = refined_log

    chosen = [
        name
        for name, on in (
            ("knowledge", plan.search_knowledge),
            ("logs", plan.inspect_logs),
            ("database", plan.query_database),
        )
        if on
    ]
    return {
        "plan": plan,
        "loops": state.get("loops", 0) + 1,
        "trace": [f"Planned to use: {', '.join(chosen)}."],
    }


# --- 3. Parallel evidence gathering ---


def search_knowledge_node(state: InvestigationState) -> dict:
    plan: InvestigationPlan = state["plan"]
    content, citations = search_documents(plan.knowledge_query)

    # On a re-planned loop this node runs again and its passages are appended to the ones
    # already in state, so markers continue from where the last pass stopped. Restarting at 1
    # would give two different chunks the same [1] and make every citation ambiguous.
    offset = len(state.get("citations", []))
    if offset:
        citations = [c.model_copy(update={"marker": c.marker + offset}) for c in citations]
        content = _shift_markers(content, offset)

    sources = sorted({c.source for c in citations})
    detail = f"{len(citations)} passage(s) from {', '.join(sources)}" if citations else "no match"
    return {
        "evidence": [
            EvidenceItem(source="knowledge", content=content, citations=citations)
        ],
        "citations": citations,
        "trace": [f"Searched documentation for '{plan.knowledge_query}' — {detail}."],
    }


def _shift_markers(content: str, offset: int) -> str:
    return re.sub(
        r"^\[(\d+)\]",
        lambda m: f"[{int(m.group(1)) + offset}]",
        content,
        flags=re.MULTILINE,
    )


def inspect_logs_node(state: InvestigationState) -> dict:
    plan: InvestigationPlan = state["plan"]
    lines = search_log_files(plan.log_query)
    content = "\n".join(lines) if lines else f"No log lines matched '{plan.log_query}'."
    return {
        "evidence": [EvidenceItem(source="logs", content=content)],
        "trace": [f"Searched logs for '{plan.log_query}' — {len(lines)} line(s) matched."],
    }


SQL_PROMPT = """Write one read-only SQLite SELECT that gathers the rows needed to diagnose this
issue. Return only the SQL.

Schema:
{schema}

Prefer a LEFT JOIN from shipments to trailers and facilities so a missing trailer still returns
the shipment row.

Issue: {summary}
Identifiers: {entities}"""


def query_database_node(state: InvestigationState) -> dict:
    understanding: IssueUnderstanding = state["understanding"]
    entities = understanding.entity_ids

    # A deterministic query for the common single-shipment case: it is faster and cannot be
    # malformed. Fall back to the model only for open-ended requests.
    if entities and entities[0].upper().startswith("SHP-"):
        sql = f"""SELECT s.shipment_id, s.status, s.trailer_id, s.location, s.priority,
       s.created_at, t.status AS trailer_status, t.last_inspection,
       f.name AS facility_name, f.outbound_enabled
FROM shipments s
LEFT JOIN trailers t ON t.trailer_id = s.trailer_id
LEFT JOIN facilities f ON f.code = s.location
WHERE s.shipment_id = '{entities[0].upper()}'"""
    else:
        raw = _model(state).invoke(
            SQL_PROMPT.format(
                schema=DATABASE_SCHEMA,
                summary=understanding.summary,
                entities=", ".join(entities) or "none",
            )
        ).content
        sql = _strip_sql_fence(str(raw))

    try:
        rows = run_query(sql)
        content = _format_rows(rows)
        note = f"{len(rows)} row(s)"
    except Exception as exc:  # noqa: BLE001 - surface the failure as evidence, do not crash
        content = f"Query failed: {exc}\nSQL: {sql}"
        note = "query failed"

    return {
        "evidence": [EvidenceItem(source="database", content=content)],
        "trace": [f"Queried the database — {note}."],
    }


def _strip_sql_fence(text: str) -> str:
    text = text.strip()
    if "```" in text:
        parts = text.split("```")
        if len(parts) >= 2:
            text = parts[1]
            if text.lower().startswith("sql"):
                text = text[3:]
    return text.strip()


def _format_rows(rows: list[dict]) -> str:
    if not rows:
        return "Query returned no rows."
    lines = []
    for row in rows:
        lines.append("\n".join(f"{k}: {'NULL' if v is None else v}" for k, v in row.items()))
    return "\n---\n".join(lines)


# --- 4. Combine ---


def combine_evidence(state: InvestigationState) -> dict:
    sources = sorted({item.source for item in state.get("evidence", [])})
    return {"trace": [f"Combined evidence from: {', '.join(sources) or 'no sources'}."]}


# --- 5. Validate ---

VALIDATE_PROMPT = """You are checking whether the collected evidence is enough to state a root
cause with confidence.

Answer sufficient=true when the evidence identifies a concrete cause — for example a rule that
was violated together with data or a log line proving the violation.

Answer sufficient=false only when a genuinely necessary piece is missing, and say what it is.
Do not ask for evidence that does not exist in a read-only shipping system.

When you answer sufficient=false, also propose better search phrases: set
refined_knowledge_query to the wording most likely to surface the missing rule, and
refined_log_query to the term most likely to surface the missing log line. Leave a field empty
if that source is not the one lacking. Do not repeat a phrase that has already been tried.

Issue: {summary}

Evidence:
{evidence}"""


def validate_evidence(state: InvestigationState) -> dict:
    understanding: IssueUnderstanding = state["understanding"]
    verdict = _structured(EvidenceVerdict, state).invoke(
        VALIDATE_PROMPT.format(
            summary=understanding.summary,
            evidence=_render_evidence(state),
        )
    )

    loops = state.get("loops", 0)
    if not verdict.sufficient and loops >= settings.max_investigation_loops:
        verdict.sufficient = True
        note = (
            f"Evidence judged incomplete but the loop limit ({settings.max_investigation_loops}) "
            "was reached — reporting with the available evidence."
        )
    elif verdict.sufficient:
        note = "Evidence judged sufficient."
    else:
        note = f"Evidence insufficient: {verdict.missing}. Re-planning."

    return {
        "verdict": verdict,
        "refined_knowledge_query": verdict.refined_knowledge_query,
        "refined_log_query": verdict.refined_log_query,
        "trace": [note],
    }


def refine_plan(state: InvestigationState) -> dict:
    suggested = [
        f"{label} '{query}'"
        for label, query in (
            ("documentation", state.get("refined_knowledge_query", "")),
            ("logs", state.get("refined_log_query", "")),
        )
        if query.strip()
    ]
    note = "Refining the investigation plan."
    if suggested:
        note += " Retrying with " + " and ".join(suggested) + "."
    return {"trace": [note]}


# --- 6. Report ---

RCA_PROMPT = """You are a senior platform engineer writing a root-cause analysis.

Use only the evidence provided. Cite concrete values such as a NULL column or an exact log
message. Do not speculate beyond the evidence.

Citations. Documentation passages are numbered like [1] and [2]. Every claim you take from the
documentation must carry the matching marker, for example: "a trailer must be assigned [1]".
Never invent a marker that is not in the evidence. Quote log lines and database values
directly instead of citing them.

Set requires_approval=true when your recommended action would write to production — assigning a
trailer, changing a status or clearing a hold. Read-only follow-up leaves it false.

Confidence guidance: 90 or above when a rule, a log error and a data value all agree; 60 to 85
when one source is missing; below 60 when the cause is a guess.

Issue: {summary}

Evidence:
{evidence}"""


def generate_report(state: InvestigationState) -> dict:
    understanding: IssueUnderstanding = state["understanding"]
    report = _structured(RootCauseReport, state).invoke(
        RCA_PROMPT.format(summary=understanding.summary, evidence=_render_evidence(state))
    )

    # The remediation scenario always needs a human, whatever the model decided.
    if understanding.kind == IssueKind.REMEDIATION:
        report.requires_approval = True

    grounding = check_grounding(
        " ".join([report.root_cause, *report.evidence]), state.get("citations", [])
    )
    trace = [f"Generated the root-cause report ({report.confidence}% confidence)."]
    if grounding.note:
        trace.append(grounding.note)

    return {"report": report, "grounding": grounding, "trace": trace}


# --- 7. Knowledge-only answer ---

ANSWER_PROMPT = """Answer the question using only the documentation below.

Each passage is numbered, for example [1]. End every sentence that uses a passage with its
marker, like this: "The trailer must be ACTIVE [2]." Use only markers that appear below — never
invent one. If the documentation does not cover the question, say so plainly rather than
filling the gap from your own knowledge.

Question: {question}

Documentation:
{evidence}"""


def answer_from_knowledge(state: InvestigationState) -> dict:
    answer = str(
        _model(state)
        .invoke(ANSWER_PROMPT.format(question=state["question"], evidence=_render_evidence(state)))
        .content
    ).strip()

    grounding = check_grounding(answer, state.get("citations", []))
    trace = ["Answered directly from the documentation."]
    if grounding.note:
        trace.append(grounding.note)

    return {"answer": answer, "grounding": grounding, "trace": trace}


# --- Grounding guardrail ---

MARKER_PATTERN = re.compile(r"\[(\d{1,3})\]")


def check_grounding(text: str, citations: list[Citation]) -> GroundingCheck:
    """Verify the model's citation markers resolve to passages it was actually given.

    This is a cheap, deterministic hallucination check. It cannot tell you the claim is true,
    but it does catch the common failure where a model manufactures authority by attributing a
    statement to a source that was never retrieved.
    """
    valid = {c.marker for c in citations}
    cited = sorted({int(m) for m in MARKER_PATTERN.findall(text)})
    unknown = [m for m in cited if m not in valid]
    uncited = bool(valid) and not cited

    if unknown:
        note = (
            "Grounding warning: cited "
            + ", ".join(f"[{m}]" for m in unknown)
            + " which was never retrieved."
        )
    elif uncited:
        note = "Grounding warning: documentation was retrieved but the answer cites none of it."
    else:
        note = ""

    return GroundingCheck(
        grounded=not unknown and not uncited,
        cited_markers=cited,
        unknown_markers=unknown,
        uncited=uncited,
        note=note,
    )


# --- 8. Human approval ---


def human_review(state: InvestigationState) -> dict:
    report: RootCauseReport = state["report"]

    decision = interrupt(
        {
            "reason": "The recommended action would change production state.",
            "root_cause": report.root_cause,
            "recommended_action": report.recommended_action,
            "confidence": report.confidence,
        }
    )

    text = str(decision).strip()
    lowered = text.lower()
    if lowered in {"approve", "approved", "yes", "ok"}:
        note = "Human approved the recommended action. Execution is out of scope for this demo."
    elif lowered in {"reject", "rejected", "no"}:
        note = "Human rejected the recommended action. No change will be made."
    else:
        note = f"Human modified the recommended action: {text}"
        report.recommended_action = text

    return {"approval_decision": text, "report": report, "trace": [note]}


def _render_evidence(state: InvestigationState) -> str:
    items = state.get("evidence", [])
    if not items:
        return "(no evidence collected)"
    return "\n\n".join(f"### {item.source}\n{item.content}" for item in items)
