"""Pre-demo checklist. Confirms Ollama, the models, the tools and the index all respond.

    python scripts/verify_setup.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests  # noqa: E402

from app.config import settings  # noqa: E402
from app.rag import index_is_empty, index_size, retrieve_traced  # noqa: E402
from app.tools import query_database, search_knowledge, search_logs  # noqa: E402
from app.tools.sql import SqlSafetyError, validate_sql  # noqa: E402

PASS, FAIL = "PASS", "FAIL"
results: list[tuple[str, str, str]] = []


def check(name: str, fn) -> None:
    try:
        detail = fn()
        results.append((PASS, name, detail))
    except Exception as exc:  # noqa: BLE001 - a checklist should report, not crash
        results.append((FAIL, name, f"{type(exc).__name__}: {exc}"))


def check_ollama() -> str:
    resp = requests.get(f"{settings.ollama_base_url}/api/tags", timeout=10)
    resp.raise_for_status()
    names = {m["name"] for m in resp.json().get("models", [])}
    wanted = {settings.chat_model, settings.chat_model_fast, settings.embedding_model}
    missing = {w for w in wanted if w not in names}
    if missing:
        raise RuntimeError(f"models not pulled: {', '.join(sorted(missing))}")
    return f"{len(names)} models available, all required models present"


def check_database() -> str:
    out = query_database.invoke(
        {"query": "SELECT shipment_id, status, trailer_id FROM shipments WHERE shipment_id = 'SHP-1007'"}
    )
    if "SHP-1007" not in out:
        raise RuntimeError(f"unexpected result: {out}")
    if "NULL" not in out:
        raise RuntimeError("SHP-1007 should have a NULL trailer_id for the demo to work")
    return "SHP-1007 present with NULL trailer_id"


def check_sql_safety() -> str:
    must_reject = [
        "DELETE FROM shipments",
        "SELECT 1; DROP TABLE shipments",
        "UPDATE shipments SET status = 'DELIVERED'",
        "PRAGMA table_info(shipments)",
        "SELECT * FROM shipments UNION SELECT 1; DELETE FROM trailers",
    ]
    survived = [q for q in must_reject if _accepted(q)]
    if survived:
        raise RuntimeError(f"unsafe query was accepted: {survived[0]!r}")

    # Comment-smuggled writes are neutralised rather than rejected: the comment is stripped,
    # leaving a plain SELECT. Confirm the write really is gone.
    smuggled = validate_sql("SELECT * FROM shipments -- ; DROP TABLE trailers")
    if "drop" in smuggled.lower():
        raise RuntimeError("comment stripping left a DROP in the statement")

    return f"{len(must_reject)} writes rejected, comment injection neutralised"


def _accepted(query: str) -> bool:
    try:
        validate_sql(query)
        return True
    except SqlSafetyError:
        return False


def check_logs() -> str:
    out = search_logs.invoke({"term": "SHP-1007"})
    if "No active trailer assignment" not in out:
        raise RuntimeError("expected the trailer-assignment error in the log output")
    return f"{len(out.splitlines())} lines matched, ERROR line present"


def check_index() -> str:
    if index_is_empty():
        raise RuntimeError("vector index is empty — run python scripts/bootstrap.py")
    out = search_knowledge.invoke({"query": "conditions required for READY_FOR_DISPATCH"})
    if "trailer" not in out.lower():
        raise RuntimeError("retrieval did not surface the trailer rule")
    if "[1]" not in out:
        raise RuntimeError("passages are not numbered, so the model cannot cite them")
    return f"{index_size()} chunks indexed, retrieval returned numbered dispatch rules"


def check_multi_format() -> str:
    """Every format in the knowledge base should be reachable, not just Markdown."""
    probes = {
        "md": ("what blocks the CREATED to READY_FOR_DISPATCH transition", ".md"),
        "pdf": ("which escalation tier handles a disabled facility", ".pdf"),
        "java": ("BlockReason MISSING_TRAILER returned by the workflow service", ".java"),
    }
    missed = []
    for label, (query, suffix) in probes.items():
        sources = [c.source for c in retrieve_traced(query).final]
        if not any(s.endswith(suffix) for s in sources):
            missed.append(f"{label} (got {sources})")
    if missed:
        raise RuntimeError("format not retrievable: " + "; ".join(missed))
    return "markdown, pdf and code chunks are all retrievable"


def check_pipeline() -> str:
    trace = retrieve_traced("why is a shipment stuck before dispatch")
    if not trace.final:
        raise RuntimeError("the pipeline returned nothing")

    parts = [f"dense {len(trace.dense)}"]
    if settings.retrieval_mode == "hybrid":
        if not trace.sparse:
            raise RuntimeError("hybrid mode is on but BM25 returned no candidates")
        parts.append(f"sparse {len(trace.sparse)}")
    parts.append(f"fused {len(trace.fused)}")

    if settings.rerank_enabled:
        if not trace.reranked:
            raise RuntimeError(f"reranking is enabled but {settings.reranker_model} did not run")
        parts.append("reranked")
    parts.append(f"final {len(trace.final)}")
    return " -> ".join(parts)


def main() -> int:
    check("Ollama runtime and models", check_ollama)
    check("SQLite sample database", check_database)
    check("SQL safety validation", check_sql_safety)
    check("Log search tool", check_logs)
    check("Chroma knowledge index", check_index)
    check("Retrieval pipeline", check_pipeline)
    check("Multi-format ingestion", check_multi_format)

    width = max(len(n) for _, n, _ in results)
    print()
    for status, name, detail in results:
        print(f"  [{status}] {name.ljust(width)}  {detail}")

    failures = sum(1 for s, _, _ in results if s == FAIL)
    print()
    if failures:
        print(f"{failures} check(s) failed.")
        return 1
    print("All checks passed — ready to demo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
