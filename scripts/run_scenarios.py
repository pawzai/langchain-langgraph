"""Run the three demo scenarios from the command line.

    python scripts/run_scenarios.py            # all three
    python scripts/run_scenarios.py 2          # just scenario 2
    python scripts/run_scenarios.py --fast     # use the smaller model
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.schemas import ApprovalRequest, InvestigateRequest  # noqa: E402
from app.service import investigate, resume  # noqa: E402

SCENARIOS = [
    ("Knowledge question", "What conditions are required for READY_FOR_DISPATCH?"),
    ("Root-cause investigation", "Why is shipment SHP-1007 stuck in CREATED?"),
    ("Human approval", "Suggest how to fix shipment SHP-1007."),
    # These two share the symptom of scenario 2 but have different causes, which shows the agent
    # reading the evidence rather than repeating one memorised answer.
    ("Trailer in maintenance", "Why is shipment SHP-1010 not dispatching?"),
    ("Inbound-only facility", "Why is shipment SHP-1013 stuck?"),
    # These two are answerable only from the PDF and the Java source, so they prove the
    # non-Markdown ingestion paths reach the model rather than merely reaching the index.
    (
        "Escalation policy from the PDF",
        "Which escalation tier owns a shipment blocked by a disabled facility?",
    ),
    (
        "Source code question",
        "Which BlockReason does the workflow service return when trailer_id is null?",
    ),
]


def rule(title: str) -> None:
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")


def show(response) -> None:
    print(f"\nClassified as : {response.kind.value if response.kind else '-'}")
    print(f"Summary       : {response.summary}")

    if response.plan:
        chosen = [
            n
            for n, on in (
                ("knowledge", response.plan.search_knowledge),
                ("logs", response.plan.inspect_logs),
                ("database", response.plan.query_database),
            )
            if on
        ]
        print(f"Sources used  : {', '.join(chosen)}")

    print("\nTrace:")
    for step in response.trace:
        print(f"  - {step}")

    for item in response.evidence:
        body = item.content if len(item.content) < 600 else item.content[:600] + " ..."
        print(f"\n--- evidence: {item.source} ---\n{body}")

    if response.answer:
        print(f"\n--- answer ---\n{response.answer}")

    if response.report:
        r = response.report
        print(f"\n--- root-cause report ---")
        print(f"Root cause         : {r.root_cause}")
        print("Evidence           :")
        for e in r.evidence:
            print(f"  - {e}")
        print(f"Confidence         : {r.confidence}%")
        print(f"Recommended action : {r.recommended_action}")
        print(f"Requires approval  : {r.requires_approval}")

    if response.citations:
        cited = set(response.grounding.cited_markers) if response.grounding else set()
        print("\n--- sources ---")
        for citation in response.citations:
            mark = "cited" if citation.marker in cited else "     "
            label = citation.source + (f" — {citation.section}" if citation.section else "")
            print(f"  [{citation.marker}] {mark}  {label}  (score {citation.score:.3f})")

    if response.grounding:
        status = "grounded" if response.grounding.grounded else "UNGROUNDED"
        print(f"\nGrounding          : {status}")
        if response.grounding.note:
            print(f"                     {response.grounding.note}")

    print(f"\nAwaiting approval  : {response.awaiting_approval}")


def main() -> int:
    args = [a for a in sys.argv[1:]]
    fast = "--fast" in args
    picks = [int(a) for a in args if a.isdigit()] or [1, 2, 3]

    for number in picks:
        title, question = SCENARIOS[number - 1]
        rule(f"Scenario {number} — {title}\n{question}")

        start = time.time()
        response = investigate(InvestigateRequest(question=question, fast=fast))
        show(response)

        if response.awaiting_approval:
            print("\n>>> Graph paused for human review. Sending 'approve'...")
            response = resume(
                ApprovalRequest(thread_id=response.thread_id, decision="approve")
            )
            print("Trace after approval:")
            for step in response.trace[-2:]:
                print(f"  - {step}")

        print(f"\nElapsed: {time.time() - start:.1f}s")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
