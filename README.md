# AI Production Issue Investigator

An evidence-backed root-cause analysis agent for a fictional shipping platform. It searches
documentation, reads application logs, queries a sample database, and produces a root cause with
supporting evidence, a confidence score, a recommended action and a citation for every claim —
**running entirely on locally hosted models**. No API cost, no data leaving the machine.

| Pillar | Role in this project |
| --- | --- |
| **LangChain** | Models, prompts, retrieval, tools and structured output |
| **LangGraph** | State, parallel routing, re-planning loops, checkpoints and human approval |
| **Ollama** | `qwen3:14b` for reasoning, `qwen3-embedding:0.6b` for retrieval |
| **Hybrid RAG** | Chroma + BM25 fused with RRF, reranked by a local cross-encoder |

The design rationale and seven-day plan live in
[`langchain_langgraph_demo_plan.md`](langchain_langgraph_demo_plan.md).

> **New to Python?** Read [`HOW_TO_RUN.md`](HOW_TO_RUN.md) instead of this file. It walks through
> running the demo one step at a time, with a troubleshooting table and a plain-English glossary.
> The short version: double-click `start-demo.bat`.

---

## Quick start

Requires Python 3.12+ and [Ollama](https://ollama.com) running locally.

```bash
# 1. Pull the models (about 15 GB total)
ollama pull qwen3:14b
ollama pull qwen3:8b
ollama pull qwen3-embedding:0.6b

# 2. Install dependencies
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux
pip install -r requirements.txt

# 3. Seed the database and build the vector index
python scripts/bootstrap.py

# 4. Confirm everything responds
python scripts/verify_setup.py

# 5. Launch the demo
streamlit run app/ui.py
```

Bootstrap also downloads the reranker, a ~80 MB cross-encoder, on first run. Set
`RERANK_ENABLED=false` if the machine has no internet access.

`verify_setup.py` is the pre-demo checklist. It should print seven `PASS` lines:

```
  [PASS] Ollama runtime and models  7 models available, all required models present
  [PASS] SQLite sample database     SHP-1007 present with NULL trailer_id
  [PASS] SQL safety validation      5 writes rejected, comment injection neutralised
  [PASS] Log search tool            5 lines matched, ERROR line present
  [PASS] Chroma knowledge index     22 chunks indexed, retrieval returned numbered dispatch rules
  [PASS] Retrieval pipeline         dense 20 -> sparse 20 -> fused 22 -> reranked -> final 4
  [PASS] Multi-format ingestion     markdown, pdf and code chunks are all retrievable
```

### Other entry points

```bash
python scripts/run_scenarios.py            # run the three core demo scenarios in the terminal
python scripts/run_scenarios.py 2 --fast    # one scenario against the smaller model
python eval/run_eval.py                     # score retrieval against the golden set
uvicorn app.api:app --reload                # REST API, docs at http://localhost:8000/docs
docker compose up --build                   # UI on :8501, API on :8000
```

---

## The workflow

The graph is deliberately explicit, so a reviewer can see a governed process rather than one
uncontrolled prompt. Nodes are in `app/graph/nodes.py`, wiring in `app/graph/build.py`.

```
                  ┌──────────────────┐
                  │ Understand Issue │   classify: knowledge / investigation / remediation
                  └────────┬─────────┘
                           ▼
                  ┌──────────────────┐
             ┌───▶│   Create Plan    │   choose sources, write search phrases
             │    └────────┬─────────┘
             │             ▼  (parallel fan-out — only the chosen branches run)
             │   ┌─────────┼─────────┐
             │   ▼         ▼         ▼
             │ Knowledge  Logs   Database
             │   └─────────┼─────────┘
             │             ▼
             │    ┌──────────────────┐
             │    │ Combine Evidence │
             │    └────────┬─────────┘
             │             ▼
             │      knowledge? ──yes──▶ Answer from documentation ──▶ END
             │             │ no
             │             ▼
             │    ┌──────────────────┐
             └────│ Validate Evidence│  insufficient ──▶ Refine ──▶ re-plan (bounded)
                  └────────┬─────────┘
                           ▼ sufficient
                  ┌──────────────────┐
                  │  Generate RCA    │
                  └────────┬─────────┘
                           ▼
                  requires approval? ──yes──▶ Human Review (graph pauses) ──▶ END
                           │ no
                           ▼ END
```

Three properties worth pointing out in a demo:

- **Parallel evidence gathering.** `route_sources` returns a list of node names, so the
  documentation, log and database branches execute in a single superstep. `evidence` and `trace`
  use additive reducers in `app/graph/state.py` to merge those concurrent writes safely.
- **Bounded self-correction.** When `validate_evidence` judges the evidence insufficient, the
  graph loops back to re-plan with different search phrases. `MAX_INVESTIGATION_LOOPS` caps this,
  and on hitting the cap the graph reports with what it has instead of spinning.
- **A real pause, not a prompt.** `human_review` calls LangGraph's `interrupt()`. Execution stops
  and the state is persisted to SQLite; the run resumes on a later request via
  `Command(resume=...)`. This is why approval survives a page refresh or a process restart.

---

## The retrieval pipeline

The `Knowledge` branch above is not a single vector lookup. Each stage exists to cover a
specific failure of the one before it.

```
query
  ├─▶ Chroma dense search      top 20   understands paraphrase, misses literal tokens
  └─▶ BM25 keyword search      top 20   matches literal tokens, misses paraphrase
            │
            ▼
     Reciprocal Rank Fusion             merge on chunk_id, score = Σ 1/(60 + rank)
            │
            ▼
     Cross-encoder rerank               reads query and chunk together, drops the rest
            │
            ▼
     Top 4, numbered [1]..[4]           context the model may cite, and nothing else
            │
            ▼
     Grounding check                    every [n] the model wrote must resolve to a real chunk
```

**Why fuse on rank rather than score.** A cosine distance and a BM25 score share no scale, so
adding or averaging them is meaningless. RRF discards magnitudes and keeps only position, which
is why it can combine retrievers that disagree about what a "good" score even looks like. The
implementation is ten lines in [`app/rag.py`](app/rag.py) rather than `EnsembleRetriever`,
because it is worth being able to explain.

**Why a cross-encoder afterwards.** The embedding model encodes the query and the document
separately, so it compares two summaries. A cross-encoder reads the pair in one forward pass and
scores it directly — much more accurate, and far too slow to run over a whole corpus. Retrieve
widely and cheaply, then rescore a few dozen candidates precisely.

### Does it actually help?

`python eval/run_eval.py` runs 18 golden questions in
[`eval/golden_set.yaml`](eval/golden_set.yaml) through each configuration. Measured on the
development machine:

| Config | hit@4 | hit@1 | MRR | phrase | median latency |
| --- | --- | --- | --- | --- | --- |
| vector only | 0.89 | 0.56 | 0.690 | 0.83 | 42 ms |
| hybrid | 0.94 | 0.78 | 0.829 | 0.89 | 42 ms |
| hybrid + rerank | **1.00** | 0.72 | **0.838** | **0.94** | 339 ms |

Read this honestly rather than as a sales pitch:

- **Hybrid search is the big win, and it is free.** MRR improves from 0.690 to 0.829 at no
  measurable latency cost, because BM25 over a corpus this size is trivial. The gains come almost
  entirely from questions that hinge on a literal token — `MISSING_TRAILER`, `BOI`,
  `readyForDispatch` — which dense search alone ranked poorly or missed.
- **Reranking closes the last gap, and it is not free.** It is what takes hit@4 to 1.00 and
  phrase recall to 0.94, at roughly 300 ms per query on CPU. On this workload, where a full
  investigation is several seconds of LLM inference, that is noise. On a high-QPS service it
  would not be.
- **hit@1 goes down slightly.** The reranker demotes one case (`log-message-meaning`) from rank 1
  to rank 2. With `k=4` this changes nothing the model sees, but it is a real effect and the
  harness prints it rather than hiding it — a small cross-encoder is not uniformly better than
  fusion, it is better on average.

The harness also lists any case the best configuration still misses, which is how you decide
whether the next change should be to chunking, to the embedding model, or to the documents.

### Grounded citations

Passages reach the model numbered, and the prompts require an inline marker on every claim taken
from documentation. `check_grounding` in [`app/graph/nodes.py`](app/graph/nodes.py) then verifies
that each `[n]` the model wrote corresponds to a chunk actually retrieved.

This is deliberately a narrow guarantee. It cannot tell you a claim is true; it catches the
specific failure where a model manufactures authority by attributing a statement to a source it
was never given. The result is on `InvestigateResponse.grounding` and rendered in the UI, and
warnings appear in the workflow trace.

### Ingestion

[`app/ingest.py`](app/ingest.py) walks `data/knowledge/` and dispatches on file type: Markdown
splits on headings then size, PDFs split by page, and source files split on language boundaries
so a method body keeps its signature. The knowledge base therefore includes a Markdown ruleset, a
PDF escalation policy and a Java service class — and questions answerable only from the PDF or
only from the code are part of the demo.

Indexing is incremental. Each chunk's id is a hash of its text plus its locator, so re-indexing
after editing one paragraph re-embeds one chunk:

```
$ python scripts/bootstrap.py          # after editing one PDF page
  -> 22 chunks (1 added, 1 removed, 21 unchanged)
```

---

## Demo scenarios

| # | Ask | Path through the graph | What it demonstrates |
| --- | --- | --- | --- |
| 1 | `What conditions are required for READY_FOR_DISPATCH?` | Plan → Documentation → Answer | Hybrid RAG with cited sources |
| 2 | `Why is shipment SHP-1007 stuck in CREATED?` | Docs + Logs + DB → Validate → RCA | Multi-source correlation |
| 3 | `Suggest how to fix shipment SHP-1007.` | Investigation → Proposed action → Pause | Governed, human-gated AI |

Two extra cases are seeded to show the agent distinguishing causes rather than pattern-matching
one answer:

- `Why is shipment SHP-1010 not dispatching?` — a trailer **is** assigned, but the nightly
  inspection sweep moved it to `MAINTENANCE`.
- `Why is shipment SHP-1013 stuck?` — trailer valid and active, but `BOI` is inbound only.

Two more (`run_scenarios.py 6` and `7`) are answerable only from the non-Markdown sources, which
is how you show that ingestion reaches the model rather than merely reaching the index:

- `Which escalation tier owns a shipment blocked by a disabled facility?` — only in the PDF.
- `Which BlockReason does the workflow service return when trailer_id is null?` — only in the
  Java source.

Scenario 2 typically produces:

```
Root cause         : No active trailer is assigned to shipment SHP-1007.
Evidence           : - Log: 'No active trailer assignment found for SHP-1007...'
                     - Database: trailer_id is NULL for SHP-1007
                     - Workflow rule: CREATED -> READY_FOR_DISPATCH requires an active trailer
Confidence         : 90%
Recommended action : Assign an active trailer to SHP-1007 and retry the workflow transition.
```

---

## Layout

```
app/
  config.py          pydantic-settings configuration, .env overridable
  llm.py             THE provider seam — the only file that names Ollama
  schemas.py         structured model outputs, citations and the API contract
  ingest.py          per-format loaders and splitters, stable chunk ids
  rag.py             dense + BM25 + RRF fusion + rerank, incremental indexing
  rerank.py          lazily loaded cross-encoder
  service.py         shared by the API and the UI; owns thread_id and resume
  api.py             FastAPI: /investigate, /approval, /health, /reindex, /retrieval/debug
  ui.py              Streamlit demo
  tools/
    knowledge.py     numbered, citable passages from the retrieval pipeline
    logs.py          keyword search over .log files, ERROR ranked first
    sql.py           read-only SELECT with two layers of enforcement
  graph/
    state.py         shared state with additive reducers
    nodes.py         one function per node, plus the grounding check
    build.py         nodes, edges, conditional routes, SQLite checkpointer
data/
  knowledge/         Markdown rules, a PDF policy and a Java service class
  logs/              application.log covering all seeded scenarios
  seed_db.py         rebuilds shipments / trailers / facilities
eval/
  golden_set.yaml    18 questions with the document that should answer each
  run_eval.py        hit@k, MRR, phrase recall and latency per configuration
scripts/
  bootstrap.py       seed + index + warm the reranker
  verify_setup.py    pre-demo checklist
  run_scenarios.py   terminal demo runner
  ensure_ready.py    idempotent container startup step
  make_sample_pdf.py regenerates the PDF in the knowledge base
```

---

## Design notes

**Why the provider stays pluggable.** All model construction lives in `app/llm.py`. Moving to
Anthropic or OpenAI means editing those two functions — the graph, tools and retrieval layers
depend on the returned LangChain interfaces, not on Ollama.

**Why `reasoning=False`.** qwen3 is a thinking model. Leaving thinking enabled roughly tripled
latency and leaked chain-of-thought into structured-output parsing. Disabling it made every node
faster and the typed outputs reliable.

**Why structured output instead of a tool-calling agent.** Every routing decision
(`InvestigationPlan`, `EvidenceVerdict`) is a Pydantic model, so branching is typed data rather
than parsed prose. A local 8B–14B model is far more reliable choosing three booleans than driving
a free-form agent loop, and the graph stays inspectable.

**Why the database query is partly deterministic.** For a single-shipment lookup, `nodes.py` uses
a fixed `LEFT JOIN` rather than asking the model to write SQL. It is faster, cannot be malformed,
and the `LEFT JOIN` is what makes the `NULL` trailer visible — an inner join would return no rows
and hide the root cause. The model still writes SQL for open-ended requests.

**SQL safety has two layers.** `validate_sql` rejects anything that is not a single bare
`SELECT`, strips comments, and appends a `LIMIT`. Independently, the connection is opened with
SQLite's `mode=ro` URI flag, so a statement that somehow passed validation still cannot write.

### Configuration

Copy `.env.example` to `.env` to override any of:

| Variable | Default | Purpose |
| --- | --- | --- |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Where the runtime listens |
| `CHAT_MODEL` | `qwen3:14b` | Reasoning model |
| `CHAT_MODEL_FAST` | `qwen3:8b` | Used when `FAST_MODE=true` or the UI toggle is on |
| `EMBEDDING_MODEL` | `qwen3-embedding:0.6b` | 1024-dimension local embeddings |
| `MAX_INVESTIGATION_LOOPS` | `2` | Cap on re-planning loops |
| `RETRIEVAL_MODE` | `hybrid` | `hybrid` fuses BM25 with vectors; `vector` is dense only |
| `DENSE_K` / `SPARSE_K` | `20` | Candidates from each retriever before fusion |
| `FINAL_K` | `4` | Passages handed to the model |
| `RERANK_ENABLED` | `true` | Set false for a fully offline run |
| `RERANKER_MODEL` | `cross-encoder/ms-marco-MiniLM-L-6-v2` | ~80 MB, CPU |
| `MIN_RERANK_SCORE` | `-6.0` | Chunks below this are dropped rather than padding the context |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | `900` / `120` | Re-run bootstrap after changing |

### Performance

Timings on the development machine for scenario 2, the full three-source investigation. Model
residency dominates, so warm and cold are listed separately:

| State | `qwen3:8b` | `qwen3:14b` |
| --- | --- | --- |
| Warm — model already resident | ~8 s | ~15 s |
| Cold — model loaded on first call | ~16 s | ~35 s |

Two practical consequences:

- **Warm, the 14B model costs about twice the 8B one**, not the 3–4x the raw parameter counts
  suggest. An investigation is four to five sequential model calls, so both are dominated by
  round-trip and prompt-processing time.
- **Toggling fast mode mid-demo is the slow path.** Ollama evicts one model to load the other, so
  the first run after a switch pays the cold cost. Warm the model you intend to demo by running
  the scenario once beforehand.

Use fast mode while iterating on prompts, and demo on `qwen3:14b` — it produces tighter
root-cause wording and needed fewer re-planning loops in testing. The active model is printed as
the first line of the workflow trace, so you can always confirm which one served a run.

---

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `The knowledge index is empty` | `python scripts/bootstrap.py` |
| `models not pulled` from verify | `ollama pull qwen3:14b qwen3-embedding:0.6b` |
| Container cannot reach Ollama | Ollama must listen on `0.0.0.0`: `OLLAMA_HOST=0.0.0.0 ollama serve` |
| Answers cite stale documents | Edit `data/knowledge/`, then `POST /reindex` or re-run bootstrap |
| Approval button does nothing | Check `data/checkpoints.sqlite` is writable — resume needs the checkpointer |
| Reranker cannot download | `RERANK_ENABLED=false`, or pre-cache the model and set `HF_HOME` |
| A retrieved chunk looks wrong | `GET /retrieval/debug?q=...` shows dense, BM25, fused and final side by side |
| Retrieval quality changed | `python eval/run_eval.py` and compare against the table above |

## Scope

Intentionally excluded so far: multiple agents, live Jira or GitHub, production databases,
autonomous writes, distributed tracing and a React frontend. The graph, tool and retrieval seams
are where those attach — the next steps are exposing these tools over MCP, adding a Git
repository search tool, and splitting the evidence nodes into supervised sub-agents.
