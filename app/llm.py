"""The single place a model provider is chosen.

Swapping to Anthropic or OpenAI later means editing these two functions only — the graph,
tools and RAG layers depend on the returned interfaces, not on Ollama.
"""

from __future__ import annotations

from functools import lru_cache

from langchain_ollama import ChatOllama, OllamaEmbeddings

from app.config import settings


@lru_cache(maxsize=4)
def get_chat_model(fast: bool | None = None) -> ChatOllama:
    """Return the reasoning model.

    `reasoning=False` disables qwen3's thinking tokens. Leaving them on roughly triples
    latency and leaks chain-of-thought into structured-output parsing.
    """
    use_fast = settings.fast_mode if fast is None else fast
    return ChatOllama(
        model=settings.chat_model_fast if use_fast else settings.chat_model,
        base_url=settings.ollama_base_url,
        temperature=0,
        reasoning=False,
    )


@lru_cache(maxsize=1)
def get_embeddings() -> OllamaEmbeddings:
    return OllamaEmbeddings(
        model=settings.embedding_model,
        base_url=settings.ollama_base_url,
    )
