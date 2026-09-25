"""Shared state for the investigation graph.

`evidence` and `trace` use additive reducers because the knowledge, log and database nodes run
as parallel branches and all write to them in the same superstep.
"""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from app.schemas import (
    Citation,
    EvidenceItem,
    EvidenceVerdict,
    GroundingCheck,
    InvestigationPlan,
    IssueUnderstanding,
    RootCauseReport,
)


class InvestigationState(TypedDict, total=False):
    question: str

    understanding: IssueUnderstanding | None
    plan: InvestigationPlan | None
    verdict: EvidenceVerdict | None
    report: RootCauseReport | None

    evidence: Annotated[list[EvidenceItem], operator.add]
    trace: Annotated[list[str], operator.add]

    # The retrieved passages the model was allowed to cite, and whether it stayed within them.
    citations: Annotated[list[Citation], operator.add]
    grounding: GroundingCheck | None

    answer: str
    loops: int

    approval_decision: str | None

    # Queries the validation step asked the next pass to try instead.
    refined_knowledge_query: str
    refined_log_query: str

    # Per-request model override. None means fall back to settings.fast_mode.
    fast: bool | None
