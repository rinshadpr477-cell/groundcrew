# Groundcrew

Groundcrew is an autonomous triage system for GitHub issue trackers, built and evaluated against 5,300+ real issues from [colinhacks/zod](https://github.com/colinhacks/zod), a popular open-source TypeScript library.

[![Eval Gate](https://github.com/rinshadpr477-cell/groundcrew/actions/workflows/eval.yml/badge.svg)](https://github.com/rinshadpr477-cell/groundcrew/actions/workflows/eval.yml)

Given a new issue, it classifies it, retrieves the most relevant past issues using semantic search, drafts a helpful first reply grounded only in those retrieved issues, and runs that draft through a second "critic" agent that checks for fabricated or unsupported claims before anything reaches a human. Anything the critic can't verify — even after revision attempts — is routed to a human review queue instead of being shipped automatically.

It's built to demonstrate production RAG and multi-agent patterns end to end: real data, a verification step that actually catches hallucinations, an honest evaluation harness, and basic LLMOps (latency tracing, pluggable model backends, load testing) — not a toy demo.

## How it works

New issue
│
▼
Router (LLM) ──── classifies: bug / question / feature_request / other
│
▼
Retrieval (embeddings + Qdrant) ── finds top-5 semantically similar past issues
│
▼
Draft agent (LLM) ── writes a reply, citing only the retrieved issues
│
▼
Critic agent (LLM) ── checks the draft for unsupported/fabricated claims
│
├── approved ──────────────► saved, shown in review queue as "approved"
│
└── rejected ── revise (up to 2x) ──┬── approved eventually → "approved"
└── still rejected → "needs_review" (human decides)


Every run — including the full timing breakdown per stage — is persisted to Postgres and viewable through a Next.js review dashboard, where a human can approve or reject the suggested reply.

## Real results

These numbers all come from actually running the system against real GitHub data — none are estimated or fabricated.

| Metric | Result | Sample size |
|---|---|---|
| Issues ingested | 5,318 | full historical backfill |
| Issues embedded & indexed | 3,181 | |
| Router category accuracy vs. real GitHub labels | 72.5% | 40 issues |
| Retrieval relevance@5 (label-overlap proxy) | 0.29 | 100 issues |
| Pipeline approval rate | 96.7% (29/30 auto-approved) | 30 issues |
| Avg. attempts per issue | 1.1 | 30 issues |
| Avg. pipeline latency | ~65s/issue | local 3B model, CPU only |
| API load test (`/triage/queue`) | 15.4 req/s, p95 ≈ 1.98s, 0 errors | 20 concurrent users, 200 requests |

One issue (#6455) needed all 3 attempts and was still correctly escalated to human review rather than being auto-approved — a concrete example of the system refusing to ship something it couldn't verify.

## Continuous evaluation

Every push to `main` runs a GitHub Actions workflow that spins up Postgres and Qdrant, loads a 500-issue golden set (a real, checked-in sample of historically closed issues, biased toward labeled ones for evaluability), re-indexes it, and re-runs the retrieval-relevance metric — failing the build if it drops below a baseline (currently 0.82 on this set). This golden-set score isn't directly comparable to the 0.29 measured above, since it's a smaller, more label-dense subset — it's a regression check against a fixed reference point, not a restatement of the headline metric. The LLM-dependent metrics (router accuracy, pipeline approval rate) are deliberately excluded from CI, since gating every single commit on a paid API call or a locally-installed model isn't a sensible cost/time trade-off; those stay manual, run periodically via `python run_eval.py`.

## Known limitations

Being upfront about these because they're genuinely interesting engineering trade-offs, not oversights:

- **Retrieval relevance is a proxy metric.** True duplicate-issue recall would need issue-comment data (which comments reference which past issue) that wasn't collected. The 0.29 figure measures GitHub-label overlap between a query issue and its top-5 retrieved neighbors instead — a reasonable but imperfect stand-in.
- **The critic only checks against retrieved context, not the original issue text.** In one run, the draft correctly cited an issue number that appeared in the *original issue's own title* but wasn't part of the retrieved similar-issues list — the critic approved it since it had no way to distinguish "grounded in the issue" from "fabricated." A stricter version would also pass the critic the source issue text.
- **Backtested on historical issues, not live traffic.** Groundcrew runs against issues already in the database rather than a live GitHub webhook. This was a deliberate scope decision — it proves the pipeline's reasoning and evaluation without needing a public-facing deployment or ongoing hosting cost.
- **Local model trades quality for cost.** Switching from a hosted 8B model to a free local 3B model (via Ollama) was a deliberate cost decision after exhausting free hosted-API credits — the client is a pluggable interface (`llm_client.py`) supporting either backend via one environment variable, but smaller models are measurably weaker at strict instruction-following like the critic's fact-checking task.
- **Single repository.** Only tested against `colinhacks/zod`. The pipeline is repo-agnostic by design (repo/owner are environment variables), but generalization to other repos hasn't been verified.

## Architecture

- **Frontend**: Next.js (App Router, TypeScript, Tailwind) — human review dashboard
- **Backend**: FastAPI (Python)
- **Database**: PostgreSQL — source of truth for issues, triage results, eval runs
- **Vector store**: Qdrant — semantic search over issue embeddings
- **Embeddings**: `sentence-transformers/all-MiniLM-L6-v2` (384-dim)
- **LLM**: pluggable — local via [Ollama](https://ollama.com) (default, free) or hosted via Hugging Face Inference API, switched with one environment variable
- **Infra**: Docker Compose (Postgres + Qdrant), no cloud hosting required to run or evaluate

## Project structure

apps/
web/ Next.js frontend (review dashboard)
api/ FastAPI backend
ingest_backfill.py Pulls issues from the GitHub API into Postgres
index_to_qdrant.py Embeds issues and indexes them in Qdrant
agent_pipeline.py Core router → retrieval → draft → critic loop
run_eval.py Evaluation harness (retrieval, router, pipeline metrics)
load_test.py Concurrent load test against the API
main.py FastAPI app / REST endpoints
infra/
docker-compose.yml Postgres + Qdrant for local development


## Running it locally

**Prerequisites**: Docker Desktop, Python 3.11+, Node.js, and optionally [Ollama](https://ollama.com) for free local inference (or a Hugging Face API token for hosted inference).

```bash
# 1. Start infrastructure
cd infra
docker compose up -d

# 2. Backend setup
cd ../apps/api
python -m venv .venv
.venv\Scripts\activate.bat        # Windows; use .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
copy .env.example .env            # then fill in your GitHub token, repo, etc.
python init_db.py

# 3. Ingest and index real data
python ingest_backfill.py
python index_to_qdrant.py

# 4. (Optional) pull a local model if using Ollama
ollama pull llama3.2:3b

# 5. Run a single triage end to end
python agent_pipeline.py <issue_number>

# 6. Start the API
python -m uvicorn main:app --port 8000

# 7. In a separate terminal, start the frontend
cd ../web
npm install
npm run dev
```

Then open `http://localhost:3000` to see the review queue.

To reproduce the evaluation numbers above:
```bash
python run_eval.py 30
```

To reproduce the load test:
```bash
python load_test.py 20 200
```

