"""Keyword search over local application log files.

Deliberately plain text matching rather than embeddings: log investigation is about exact
identifiers such as SHP-1007, where substring matching beats semantic similarity.
"""

from __future__ import annotations

from langchain_core.tools import tool

from app.config import settings

MAX_MATCHES = 25
LEVEL_RANK = {"ERROR": 0, "WARN": 1, "INFO": 2, "DEBUG": 3}


def _log_files() -> list:
    if not settings.log_dir.exists():
        return []
    return sorted(settings.log_dir.glob("*.log"))


def search_log_files(term: str, max_matches: int = MAX_MATCHES) -> list[str]:
    """Return log lines containing `term`, most severe first."""
    term = (term or "").strip()
    if not term:
        return []

    needles = [term.lower()]
    # A phrase rarely appears verbatim in a log line, so also try its distinctive words.
    if " " in term:
        needles += [w.lower() for w in term.split() if len(w) > 3]

    matches: list[tuple[int, str]] = []
    for path in _log_files():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            low = line.lower()
            if any(n in low for n in needles):
                level = next((lv for lv in LEVEL_RANK if lv in line), "INFO")
                matches.append((LEVEL_RANK[level], line.strip()))

    matches.sort(key=lambda m: m[0])
    seen, out = set(), []
    for _, line in matches:
        if line not in seen:
            seen.add(line)
            out.append(line)
        if len(out) >= max_matches:
            break
    return out


@tool
def search_logs(term: str) -> str:
    """Search the application log files for a term and return matching lines.

    Best used with an exact identifier such as 'SHP-1007', a service name such as
    'ShipmentWorkflowService', or an error phrase. Results are ordered ERROR first.
    """
    lines = search_log_files(term)
    if not lines:
        return f"No log lines matched '{term}'."
    return "\n".join(lines)
