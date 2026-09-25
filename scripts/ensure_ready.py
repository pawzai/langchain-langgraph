"""Idempotent startup step: seed and index only what is missing.

Used as the container entrypoint so a fresh volume becomes usable without a manual bootstrap,
while a warm volume starts instantly.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests  # noqa: E402

from app.config import settings  # noqa: E402
from app.rag import build_index, index_is_empty  # noqa: E402
from data.seed_db import seed  # noqa: E402


def wait_for_ollama(timeout: int = 90) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            requests.get(f"{settings.ollama_base_url}/api/tags", timeout=5).raise_for_status()
            return True
        except requests.RequestException:
            print(f"Waiting for Ollama at {settings.ollama_base_url}...")
            time.sleep(5)
    return False


def main() -> int:
    if not settings.sqlite_path.exists():
        print(f"Seeding database -> {seed()}")
    else:
        print("Database already present.")

    if not wait_for_ollama():
        print(
            f"ERROR: Ollama unreachable at {settings.ollama_base_url}. "
            "Start it on the host with 'ollama serve'."
        )
        return 1

    # Always sync: incremental indexing makes a no-op run cheap, and it means a container
    # restart after editing a document picks the change up without a manual reindex.
    stats = build_index()
    print(
        f"Knowledge index: {stats.total} chunks "
        f"({stats.added} added, {stats.removed} removed, {stats.unchanged} unchanged)."
    )
    if index_is_empty():
        print("WARNING: the index is empty. Is data/knowledge/ populated?")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
