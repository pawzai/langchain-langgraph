"""One-command setup: seed the database and build the vector index.

    python scripts/bootstrap.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import rerank  # noqa: E402
from app.config import settings  # noqa: E402
from app.rag import build_index  # noqa: E402
from data.seed_db import seed  # noqa: E402


def main() -> int:
    print("Seeding the shipping database...")
    print(f"  -> {seed()}")

    print(f"Embedding the knowledge base with {settings.embedding_model} (this takes a moment)...")
    stats = build_index()
    print(
        f"  -> {stats.total} chunks in {settings.chroma_dir} "
        f"({stats.added} added, {stats.removed} removed, {stats.unchanged} unchanged)"
    )

    if stats.total == 0:
        print("\nWARNING: no chunks were indexed. Is data/knowledge/ populated?")
        return 1

    if settings.rerank_enabled:
        print(f"Loading the reranker {settings.reranker_model} (downloads once)...")
        print("  -> ready" if rerank.warm_up() else "  -> unavailable; retrieval will not rerank")

    print("\nBootstrap complete. Next:")
    print("  python scripts/verify_setup.py     # confirm Ollama and the tools respond")
    print("  python eval/run_eval.py            # score the retrieval pipeline")
    print("  streamlit run app/ui.py            # launch the demo UI")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
