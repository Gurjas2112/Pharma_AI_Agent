<p align="center"><img src="App_Logo.svg" width="320" alt="Repurpora"/></p>

# repurpora-lazarus-graph

> **Lazarus Graph: a LangGraph multi-agent copilot that revives approved molecules for new indications, dosage forms and patient populations.**
> A master agent fans out to market, trade, patent, clinical-trial, internal-RAG and web agents, scores each opportunity with an ML model, and archives evidence-cited PDF/Excel reports.

**Live demo:** https://repurpora.vercel.app  ·  **Agent API:** Railway (Aegra, Agent Protocol)  ·  **Walkthrough:** [`app_screenshots_screen_recording/`](app_screenshots_screen_recording/)

Built for EY Techathon 6.0, Challenge I (Pharmaceuticals): it cuts an early-stage repurposing literature review from **2–3 months to minutes**.

---

## What it does

```
"Assess montelukast for repurposing in India: unmet needs, trials, new indications, patents"
        │
        ▼  Master agent (LangGraph planner → typed ResearchPlan)
 ┌──────┬──────┬────────┬──────────────┬──────────────┬──────┐   parallel Send() fan-out
 IQVIA  EXIM   Patent   Clinical Trials Internal RAG   Web
 market  API    FTO      live CT.gov v2  pgvector+BM25  Firecrawl
 ▼ evidence register [E1..En] (source · trust tier · sha256)
 ▼ scorer: rule gate (GO / PARTIAL_GO / NO_GO) + ML p(success) with drivers
 ▼ synthesizer → judge (coverage ≥ 0.75, faithfulness) → ≤ 1 redraft
 ▼ report: PDF + Excel → Supabase Storage (+ S3 mirror) → signed link in chat
```

| PS requirement | Where |
|---|---|
| Master agent decomposes and delegates | [`nodes/core.py`](backend/src/repurpora/nodes/core.py) `planner` → `Send` |
| IQVIA / EXIM / Patent / Trials / Internal / Web / Report agents | [`agents/workers.py`](backend/src/repurpora/agents/workers.py), [`report/`](backend/src/repurpora/report) |
| Mock IQVIA, EXIM, USPTO clone, trials stub, web proxy | [`mock_apis/`](backend/src/repurpora/mock_apis) (separate Railway service) |
| Internal docs repository + optional PDF upload | [`rag/`](backend/src/repurpora/rag), synthetic strategy deck, field report and MINS |
| Summary report archived | Supabase Storage `reports` bucket + `reports` table + S3 (LocalStack) |
| 10+ strategic questions | [`evals/golden_queries.jsonl`](backend/evals/golden_queries.jsonl) |
| UI for prompts | Next.js landing + auth + LangGraph **Agent Chat UI** ([`frontend/`](frontend)) |

## Stack

| Layer | Tech |
|---|---|
| Orchestration | **LangGraph** 1.2 (`StateGraph`, `Send`, `Command`, `interrupt`, checkpointer + store), **LangChain** 1.5 |
| Agent server | **Aegra** (open-source Agent Protocol server) on **Railway**, with Postgres persistence |
| LLMs | **Ollama**: qwen2.5 7B (planner, writer), qwen2.5 3B (notes, judge), nomic-embed-text. Behind a Caddy bearer-token proxy. **AWS EC2** GPU scripts ready; prototype uses **LocalStack** + a local RTX GPU via tunnel |
| Data | **Supabase** Postgres + pgvector (HNSW) + Auth (ES256 JWT) + Storage, Railway **Redis** cache |
| ML | **scikit-learn** opportunity scorer (LogReg / RF / GBM, CV-selected), pandas, NumPy |
| Frontend | **Next.js 15** on **Vercel**, Agent Chat UI (`create-agent-chat-app`), Tailwind v4, framer-motion |
| Observability | **LangSmith** tracing, token telemetry → `llm_usage`, append-only `audit_log`, CloudWatch (LocalStack) |
| Infra | Docker Compose (10 services), Dockerfiles for Railway, LocalStack (S3, Secrets Manager, Logs, EC2) |

## Engineering practices built in

| Area | Implementation |
|---|---|
| **Reasoning and orchestration** | Code-enforced state machine. The planner returns a JSON schema; `Send` runs workers in parallel; there is a draft → judge → redraft loop; `RetryPolicy` and a recursion limit. |
| **Memory and session** | Postgres checkpointer threads (time travel and history in the UI). Long-term per-user store with a hard cap and provenance (thread, report). Context compaction past the token budget. |
| **RAG and context engineering** | Recursive section-aware chunking. Hybrid dense + FTS search fused with RRF (k=60), then MMR. A corrective relevance gate. A token-budgeted evidence digest. A chunking benchmark. |
| **Evidence layer** | Every claim cites `[E#]`. Evidence carries a source, trust tier, URL, retrieval time and SHA-256. Coverage and citation accuracy are gated. The PDF has an evidence register appendix. |
| **Guardrails and security** | Prompt-injection and harmful-use firewall, domain scope check, untrusted-content sanitiser, PII/secret DLP on output. A per-agent tool allow-list and call budget (policy gateway). A secrets vault (AWS Secrets Manager), never in prompts. Per-user thread isolation, RLS, and a bearer-gated LLM proxy. |
| **Caching and token optimisation** | Redis LLM response cache, TTL tool cache with hit-rate stats, model routing (7B/3B), Ollama `keep_alive`, a compact evidence digest. |
| **Evaluation** | 37 pytest tests, a 12-query golden set (routing, groundedness, faithfulness, safety, latency, tokens), a RAG benchmark, and ML hold-out metrics. |
| **Observability** | LangSmith traces with tags. `UsageCallback` telemetry. Audit events: guard, plan, tool_call, judge, archive, dlp. |
| **Governance** | [`governance/`](governance): manifest with risk tier, model card, change log, policies, control YAMLs, retention, owners. |

## Skills demonstrated

| Skill area | Evidence in this repo |
|---|---|
| Build, train and evaluate ML models | `ml/opportunity_scorer.py`: pandas data generation and cleaning, stratified split, 5-fold CV over three model families, ROC-AUC / PR-AUC / F1 / Brier, calibration, over-fit gap, permutation importance |
| LLMs: prompt engineering, RAG, agentic workflows | LangGraph master/worker graph, JSON-schema planning, cited synthesis, LLM-as-judge, hybrid RAG with RRF and a corrective gate |
| Clean, preprocess, analyse datasets | pandas analytics in every worker (HHI, CAGR, FTO scoring, saturation); PDF cleaning and chunking pipeline |
| Clean Python, internal tools and APIs | Typed settings, Pydantic schemas, FastAPI mock-data service, Agent Protocol server, 37 pytest tests, ruff config |
| Benchmark performance and run experiments | Golden-set eval (v1 baseline → v2 after fixes), chunking benchmark (Hit@k / MRR / nDCG), latency, token and cache telemetry |
| Read research and apply it | `essential_docs/` papers (DrugRAG, production RAG, AHP product selection) → hybrid RAG, evidence gating, selection criteria in the scorer and strategy docs |
| Cloud and containers | AWS (EC2 GPU IaC, S3, Secrets Manager, CloudWatch via LocalStack), Docker Compose (10 services), Railway, Vercel |
| Vector DBs, embeddings, LangChain | Supabase pgvector HNSW, nomic embeddings, LangChain and LangGraph 1.x |

## Results (from this repo's own runs)

**ML opportunity scorer:** 4,000 synthetic projects, 80/20 stratified split, 5-fold CV.

| Model | CV ROC-AUC |
|---|---|
| Logistic regression (selected) | **0.796** ± 0.019 |
| Gradient boosting | 0.783 ± 0.021 |
| Random forest | 0.781 ± 0.019 |

Hold-out: ROC-AUC **0.803**, PR-AUC 0.824, F1 0.771, Brier 0.180, train-test gap −0.005 (no over-fitting).

**RAG chunking benchmark** ([`evals/results/rag_bench.md`](backend/evals/results/rag_bench.md)):

| Strategy | Hit@1 | Hit@5 | MRR@10 | nDCG@10 |
|---|---|---|---|---|
| fixed 1000 | 0.80 | 0.93 | 0.86 | 0.89 |
| recursive 1200/180 (default) | 0.80 | **1.00** | 0.89 | 0.92 |
| parent-child 400→1600 | **0.93** | 0.97 | **0.95** | **0.96** |

Parent-child wins on ranking, but each hit returns roughly 3× more tokens. Recursive stays the default because of
the context budget on a 6 GB GPU.

**Golden-set agent eval:** see [`evals/results/latest.md`](backend/evals/results/latest.md).

## Run it locally

```bash
# 0) prerequisites: Docker Desktop, Ollama (models below), uv, Node 22+
ollama pull qwen2.5:7b-instruct && ollama pull qwen2.5:3b-instruct && ollama pull nomic-embed-text

# 1) infra: LocalStack (AWS emulator), Redis, bearer-token Ollama proxy
cp backend/.env.example backend/.env        # fill in Supabase / Firecrawl / LangSmith
docker compose up -d localstack aws-bootstrap redis ollama-proxy

# 2) backend
cd backend && uv sync
uv run python scripts/apply_schema.py                 # Supabase schema + RRF function
uv run python scripts/make_synthetic_internal_docs.py
uv run python scripts/ingest.py --dir data/synthetic_internal
uv run python -m repurpora.ml.opportunity_scorer --train
uv run uvicorn repurpora.mock_apis.app:app --port 8081 &
uv run aegra serve --host 127.0.0.1 --port 2026

# 3) frontend
cd ../frontend && cp .env.example .env.local && npm install && npm run dev   # http://localhost:3000
```

The whole stack can also run in containers: `docker compose up -d --wait`.
Add `--profile ollama-container` to run Ollama in a container, or `--profile demo` to start the Cloudflare tunnel.

## Test and evaluate

```bash
cd backend
uv run pytest                                  # 37 tests (AWS tests auto-skip without LocalStack)
uv run python evals/run_evals.py --langsmith   # golden set → evals/results/latest.md
uv run python evals/rag_bench.py               # chunking benchmark
uv run python scripts/api_e2e.py               # Supabase JWT → Aegra streamed run
```

## Deploy

| Target | How |
|---|---|
| Railway | `railway up backend --path-as-root -s agent-server`, plus `-s mock-apis` (`RAILWAY_DOCKERFILE_PATH=Dockerfile.mockapi`). Redis is a plugin. |
| Vercel | `cd frontend && vercel deploy --prod`. Env: `NEXT_PUBLIC_SUPABASE_*`, `SUPABASE_SECRET_KEY` (server-only), `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_ASSISTANT_ID=repurpora`, `NEXT_PUBLIC_MOCK_API_URL` |
| AWS (production) | `infra/aws/ec2_ollama.sh`: g4dn.xlarge, IMDSv2, encrypted gp3, port 443 only, Caddy TLS + bearer token. `teardown.sh` stops it. |

See [`docs/SPEC.md`](docs/SPEC.md), [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) and [`docs/RUNBOOK.md`](docs/RUNBOOK.md).

## Repository layout

```
backend/            LangGraph graph, workers, RAG, ML, report, guardrails, Aegra config, tests, evals
frontend/           Next.js landing, auth, Agent Chat UI
infra/              Caddy proxy, AWS (LocalStack bootstrap, EC2 provisioning, teardown)
governance/         AI governance registry
docs/               spec, architecture, runbook, 5-slide deck
app_screenshots_screen_recording/   step-by-step screenshots + full walkthrough video
```

*Market, trade and patent data are synthetic mocks, as the problem statement requires. Not medical, legal or regulatory advice.*

## License
MIT. See [LICENSE](LICENSE).
