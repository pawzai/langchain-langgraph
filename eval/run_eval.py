"""Measure the retrieval pipeline against the golden set.

    python eval/run_eval.py

Runs every case through three configurations and prints a comparison, so a change to chunking,
`k`, the embedding model or the reranker can be judged on numbers rather than on the impression
left by one or two hand-typed queries.

Metrics
    hit@k   Fraction of questions where a correct document appears anywhere in the top k.
            The headline number: if this is low, nothing downstream can recover.
    hit@1   Fraction where the very first chunk is correct. Sensitive to ordering, which is
            precisely what reranking is supposed to fix.
    MRR     Mean reciprocal rank of the first correct document. Rewards putting the right
            chunk near the top rather than merely somewhere in the window.
    phrase  Fraction where the retrieved text actually contains the expected wording. Catches
            retrieving the right file but the wrong section of it.
"""

from __future__ import annotations

import json
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml  # noqa: E402

from app import rerank  # noqa: E402
from app.config import settings  # noqa: E402
from app.rag import index_is_empty, retrieve  # noqa: E402

GOLDEN_SET = Path(__file__).resolve().parent / "golden_set.yaml"
RESULTS = Path(__file__).resolve().parent / "results.json"

CONFIGS = [
    ("vector", {"mode": "vector", "use_reranker": False}),
    ("hybrid", {"mode": "hybrid", "use_reranker": False}),
    ("hybrid+rerank", {"mode": "hybrid", "use_reranker": True}),
]


@dataclass
class CaseResult:
    id: str
    question: str
    hit: bool
    first_rank: int | None
    phrase_hit: bool
    retrieved: list[str]
    latency_ms: float


@dataclass
class ConfigResult:
    name: str
    cases: list[CaseResult] = field(default_factory=list)

    @property
    def hit_at_k(self) -> float:
        return _mean(1.0 if c.hit else 0.0 for c in self.cases)

    @property
    def hit_at_1(self) -> float:
        return _mean(1.0 if c.first_rank == 1 else 0.0 for c in self.cases)

    @property
    def mrr(self) -> float:
        return _mean(1.0 / c.first_rank if c.first_rank else 0.0 for c in self.cases)

    @property
    def phrase_recall(self) -> float:
        return _mean(1.0 if c.phrase_hit else 0.0 for c in self.cases)

    @property
    def median_latency_ms(self) -> float:
        return statistics.median([c.latency_ms for c in self.cases]) if self.cases else 0.0

    def as_dict(self) -> dict:
        return {
            "config": self.name,
            "hit_at_k": round(self.hit_at_k, 4),
            "hit_at_1": round(self.hit_at_1, 4),
            "mrr": round(self.mrr, 4),
            "phrase_recall": round(self.phrase_recall, 4),
            "median_latency_ms": round(self.median_latency_ms, 1),
            "cases": [
                {
                    "id": c.id,
                    "hit": c.hit,
                    "first_rank": c.first_rank,
                    "phrase_hit": c.phrase_hit,
                    "retrieved": c.retrieved,
                    "latency_ms": round(c.latency_ms, 1),
                }
                for c in self.cases
            ],
        }


def _mean(values) -> float:
    values = list(values)
    return sum(values) / len(values) if values else 0.0


def load_cases() -> list[dict]:
    return yaml.safe_load(GOLDEN_SET.read_text(encoding="utf-8")) or []


def run_config(name: str, options: dict, cases: list[dict], k: int) -> ConfigResult:
    result = ConfigResult(name=name)

    for case in cases:
        expected = set(case.get("expected_sources", []))
        phrases = [p.lower() for p in case.get("expected_phrases", [])]

        started = time.perf_counter()
        chunks = retrieve(case["question"], k=k, **options)
        latency_ms = (time.perf_counter() - started) * 1000

        retrieved = [c.source for c in chunks]
        first_rank = next(
            (i for i, source in enumerate(retrieved, start=1) if source in expected), None
        )
        haystack = "\n".join(c.text for c in chunks).lower()

        result.cases.append(
            CaseResult(
                id=case["id"],
                question=case["question"],
                hit=first_rank is not None,
                first_rank=first_rank,
                phrase_hit=all(p in haystack for p in phrases) if phrases else True,
                retrieved=retrieved,
                latency_ms=latency_ms,
            )
        )

    return result


def print_summary(results: list[ConfigResult], k: int) -> None:
    header = f"{'config':<16}{'hit@' + str(k):>8}{'hit@1':>8}{'MRR':>8}{'phrase':>9}{'median ms':>12}"
    print("\n" + header)
    print("-" * len(header))
    for r in results:
        print(
            f"{r.name:<16}"
            f"{r.hit_at_k:>8.2f}"
            f"{r.hit_at_1:>8.2f}"
            f"{r.mrr:>8.3f}"
            f"{r.phrase_recall:>9.2f}"
            f"{r.median_latency_ms:>12.1f}"
        )


def print_regressions(results: list[ConfigResult]) -> None:
    """Cases still failing in the best configuration, and any the reranker made worse."""
    best = results[-1]
    failures = [c for c in best.cases if not c.hit]
    if failures:
        print(f"\nStill missed by {best.name}:")
        for case in failures:
            print(f"  {case.id:<28} retrieved {case.retrieved}")

    if len(results) >= 2:
        previous = {c.id: c for c in results[-2].cases}
        worse = [
            c
            for c in best.cases
            if previous.get(c.id)
            and previous[c.id].first_rank
            and (not c.first_rank or c.first_rank > previous[c.id].first_rank)
        ]
        if worse:
            print(f"\nRanked lower by {best.name} than by {results[-2].name}:")
            for case in worse:
                print(
                    f"  {case.id:<28} {previous[case.id].first_rank} -> {case.first_rank}"
                )


def main() -> int:
    if index_is_empty():
        print("The knowledge index is empty. Run: python scripts/bootstrap.py")
        return 1

    cases = load_cases()
    k = settings.final_k
    print(f"{len(cases)} case(s), k={k}, embeddings={settings.embedding_model}")

    configs = list(CONFIGS)
    if not rerank.available():
        print(
            "Reranker unavailable (RERANK_ENABLED=false or the model could not load); "
            "skipping that configuration."
        )
        configs = [c for c in configs if not c[1]["use_reranker"]]
    else:
        print(f"Reranker: {settings.reranker_model} (loading)")
        rerank.warm_up()

    results = []
    for name, options in configs:
        print(f"  running {name}...")
        results.append(run_config(name, options, cases, k))

    print_summary(results, k)
    print_regressions(results)

    RESULTS.write_text(
        json.dumps(
            {
                "k": k,
                "embedding_model": settings.embedding_model,
                "reranker_model": settings.reranker_model,
                "results": [r.as_dict() for r in results],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nWrote {RESULTS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
