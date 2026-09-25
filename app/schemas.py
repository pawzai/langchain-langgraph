"""Structured shapes the model is asked to produce, plus the API contract."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Citation(BaseModel):
    """One retrieved chunk, addressable by the marker the model is asked to write inline."""

    marker: int = Field(description="1-based; the model writes this as [1] in its prose.")
    source: str = Field(description="Path of the document, relative to the knowledge directory.")
    section: str = ""
    chunk_id: str = ""
    score: float = Field(default=0.0, description="Rerank score, or the fusion score without it.")
    excerpt: str = ""


class GroundingCheck(BaseModel):
    """Whether the model's citations point at chunks that were actually retrieved."""

    grounded: bool = True
    cited_markers: list[int] = Field(default_factory=list)
    unknown_markers: list[int] = Field(
        default_factory=list, description="Markers with no matching source. Signals invention."
    )
    uncited: bool = Field(
        default=False, description="True when sources were supplied but none were cited."
    )
    note: str = ""


class IssueKind(str, Enum):
    KNOWLEDGE = "knowledge"
    INVESTIGATION = "investigation"
    REMEDIATION = "remediation"


class IssueUnderstanding(BaseModel):
    """Result of the Understand Issue node."""

    kind: IssueKind = Field(
        description=(
            "knowledge = answerable from documentation alone; "
            "investigation = needs logs or database evidence to find a cause; "
            "remediation = the user is asking for a fix to be applied"
        )
    )
    summary: str = Field(description="One sentence restating the issue.")
    entity_ids: list[str] = Field(
        default_factory=list,
        description="Identifiers mentioned, e.g. ['SHP-1007']. Empty if none.",
    )


class InvestigationPlan(BaseModel):
    """Result of the Create Investigation Plan node."""

    search_knowledge: bool = Field(description="Search the documentation.")
    inspect_logs: bool = Field(description="Search application log files.")
    query_database: bool = Field(description="Query the shipping database.")
    knowledge_query: str = Field(default="", description="Search phrase for the docs.")
    log_query: str = Field(default="", description="Search term for the logs.")
    reasoning: str = Field(default="", description="Why these sources were chosen.")


class EvidenceVerdict(BaseModel):
    """Result of the Validate Evidence node."""

    sufficient: bool = Field(description="True if a root cause can be stated with confidence.")
    missing: str = Field(default="", description="What evidence is still needed.")
    refined_knowledge_query: str = Field(default="")
    refined_log_query: str = Field(default="")


class RootCauseReport(BaseModel):
    """Result of the Generate Root-Cause Report node."""

    root_cause: str = Field(description="The single most likely cause, one or two sentences.")
    evidence: list[str] = Field(description="Concrete findings that support the cause.")
    confidence: int = Field(ge=0, le=100, description="Confidence percentage, 0-100.")
    recommended_action: str = Field(description="The operational step that resolves the issue.")
    requires_approval: bool = Field(
        default=False,
        description="True if the recommended action changes production state.",
    )


# --- API contract ---


class InvestigateRequest(BaseModel):
    question: str
    thread_id: str | None = Field(
        default=None, description="Reuse to ask follow-up questions with memory."
    )
    fast: bool | None = Field(default=None, description="Override FAST_MODE for this call.")


class EvidenceItem(BaseModel):
    source: str
    content: str
    citations: list[Citation] = Field(default_factory=list)


class InvestigateResponse(BaseModel):
    thread_id: str
    kind: IssueKind | None = None
    summary: str = ""
    plan: InvestigationPlan | None = None
    evidence: list[EvidenceItem] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    grounding: GroundingCheck | None = None
    report: RootCauseReport | None = None
    answer: str = ""
    loops: int = 0
    awaiting_approval: bool = False
    trace: list[str] = Field(default_factory=list)


class ApprovalRequest(BaseModel):
    thread_id: str
    decision: str = Field(description="approve, reject, or the text of a modification.")
