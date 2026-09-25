FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# sentence-transformers pulls torch, whose default wheel bundles CUDA and adds roughly two
# gigabytes to the image. The reranker runs on CPU, so install the CPU-only build first and let
# the main install see the dependency as already satisfied.
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch \
    && pip install -r requirements.txt

COPY app ./app
COPY data ./data
COPY scripts ./scripts

# Bake the cross-encoder into the image so the container does not reach Hugging Face at
# start-up, and so a run with no internet access still reranks.
ENV HF_HOME=/opt/hf
RUN python -c "from sentence_transformers import CrossEncoder; \
    CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')"

# Ollama runs on the host, not in this image: the models are large and are already pulled.
ENV OLLAMA_BASE_URL=http://host.docker.internal:11434

EXPOSE 8501 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD curl -fs http://localhost:8501/_stcore/health || exit 1

CMD ["sh", "-c", "python scripts/ensure_ready.py && streamlit run app/ui.py --server.port=8501 --server.address=0.0.0.0"]
