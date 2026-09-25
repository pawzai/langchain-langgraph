"""Graph assembly: nodes, edges, conditional routes and the checkpointer."""

from __future__ import annotations

import sqlite3
from functools import lru_cache

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from app.config import settings
from app.graph import nodes
from app.graph.state import InvestigationState
from app.schemas import IssueKind


def route_sources(state: InvestigationState) -> list[str]:
    """Fan out to the evidence nodes the plan selected. Runs them in one parallel superstep."""
    plan = state["plan"]
    targets = []
    if plan.search_knowledge:
        targets.append("search_knowledge")
    if plan.inspect_logs:
        targets.append("inspect_logs")
    if plan.query_database:
        targets.append("query_database")
    return targets or ["search_knowledge"]


def route_after_combine(state: InvestigationState) -> str:
    """A documentation question needs no evidence validation loop."""
    if state["understanding"].kind == IssueKind.KNOWLEDGE:
        return "answer_from_knowledge"
    return "validate_evidence"


def route_after_validation(state: InvestigationState) -> str:
    verdict = state.get("verdict")
    if verdict and not verdict.sufficient:
        return "refine_plan"
    return "generate_report"


def route_after_report(state: InvestigationState) -> str:
    report = state.get("report")
    if report and report.requires_approval:
        return "human_review"
    return END


def build_graph(checkpointer=None):
    graph = StateGraph(InvestigationState)

    graph.add_node("understand_issue", nodes.understand_issue)
    graph.add_node("create_plan", nodes.create_plan)
    graph.add_node("search_knowledge", nodes.search_knowledge_node)
    graph.add_node("inspect_logs", nodes.inspect_logs_node)
    graph.add_node("query_database", nodes.query_database_node)
    graph.add_node("combine_evidence", nodes.combine_evidence)
    graph.add_node("validate_evidence", nodes.validate_evidence)
    graph.add_node("refine_plan", nodes.refine_plan)
    graph.add_node("generate_report", nodes.generate_report)
    graph.add_node("answer_from_knowledge", nodes.answer_from_knowledge)
    graph.add_node("human_review", nodes.human_review)

    graph.add_edge(START, "understand_issue")
    graph.add_edge("understand_issue", "create_plan")

    graph.add_conditional_edges(
        "create_plan",
        route_sources,
        ["search_knowledge", "inspect_logs", "query_database"],
    )

    for source in ("search_knowledge", "inspect_logs", "query_database"):
        graph.add_edge(source, "combine_evidence")

    graph.add_conditional_edges(
        "combine_evidence",
        route_after_combine,
        ["validate_evidence", "answer_from_knowledge"],
    )
    graph.add_conditional_edges(
        "validate_evidence",
        route_after_validation,
        ["refine_plan", "generate_report"],
    )
    graph.add_edge("refine_plan", "create_plan")
    graph.add_conditional_edges(
        "generate_report", route_after_report, ["human_review", END]
    )
    graph.add_edge("answer_from_knowledge", END)
    graph.add_edge("human_review", END)

    return graph.compile(checkpointer=checkpointer)


@lru_cache(maxsize=1)
def get_graph():
    """Compiled graph with durable SQLite checkpointing.

    Checkpointing is what makes follow-up questions and the approval pause work: the graph can be
    resumed on a later HTTP request because its state lives on disk, keyed by thread_id.
    """
    settings.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.checkpoint_path, check_same_thread=False)
    return build_graph(checkpointer=SqliteSaver(conn))
