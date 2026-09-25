"""Central configuration. Everything is overridable through .env or the environment."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    ollama_base_url: str = "http://localhost:11434"

    chat_model: str = "qwen3:14b"
    chat_model_fast: str = "qwen3:8b"
    fast_mode: bool = False

    embedding_model: str = "qwen3-embedding:0.6b"

    max_investigation_loops: int = 2

    # --- Retrieval pipeline ---
    # "vector" is the V1 behaviour, kept so the evaluation harness can measure what hybrid buys.
    retrieval_mode: Literal["vector", "hybrid"] = "hybrid"
    dense_k: int = 20
    sparse_k: int = 20
    final_k: int = 4

    rerank_enabled: bool = True
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    # Cross-encoder logits are unbounded; negative values still carry signal, so the floor is
    # deliberately permissive and only discards clearly unrelated chunks.
    min_rerank_score: float = -6.0

    chunk_size: int = 900
    chunk_overlap: int = 120

    knowledge_dir: Path = DATA_DIR / "knowledge"
    log_dir: Path = DATA_DIR / "logs"
    chroma_dir: Path = DATA_DIR / "chroma"
    sqlite_path: Path = DATA_DIR / "shipping.db"
    checkpoint_path: Path = DATA_DIR / "checkpoints.sqlite"

    chroma_collection: str = "shipping_knowledge"


settings = Settings()
