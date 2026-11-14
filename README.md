<p align="center"><img src="App_Logo.svg" width="300" alt="Repurpora"/></p>

<h1 align="center">repurpora-lazarus-graph</h1>

<p align="center">
<b>Lazarus Graph: a LangGraph multi-agent copilot that revives approved molecules for new indications, dosage forms and patient populations.</b><br/>
A master agent fans out to market, trade, patent, clinical-trial, internal-RAG and web agents, scores each opportunity with an ML model, and archives evidence-cited PDF/Excel reports.
</p>

<p align="center">
<a href="https://repurpora.vercel.app"><b>▶ Live demo</b></a> ·
<a href="app_screenshots_screen_recording/full_walkthrough.mp4">🎬 72-second walkthrough</a> ·
<a href="docs/Repurpora_Journey.pptx">📑 5-slide deck</a> ·
<a href="docs/SPEC.md">📘 Spec</a> ·
<a href="docs/ARCHITECTURE.md">🏗 Architecture</a>
</p>

<p align="center">
<img alt="python" src="https://img.shields.io/badge/python-3.12-3776AB"/>
<img alt="langgraph" src="https://img.shields.io/badge/LangGraph-1.2-1C3C3C"/>
<img alt="tests" src="https://img.shields.io/badge/tests-41%20passing-2EA44F"/>
<img alt="deploy" src="https://img.shields.io/badge/deployed-Vercel%20%2B%20Railway-black"/>
<img alt="license" src="https://img.shields.io/badge/license-MIT-blue"/>
</p>

---

## The 30-second version

**The problem.** A generic-drug company wants new, higher-value products made from medicines that are *already
approved*: a new disease ("indication"), a new form (a film instead of a tablet), or a new patient group (children).
Finding each opportunity means reading markets, trials, patents and papers for **2–3 months**.

**What Repurpora does.** You type one question, for example *"Assess montelukast for repurposing in India"*. A
**master AI agent** splits it into tasks and sends them to **six specialist agents running in parallel**:

| Agent | What it checks |
|---|---|
| Market | How big is it, how fast is it growing, and who are the competitors? |
| Trade | Where does the raw ingredient come from? |
| Patents | Is it legally free to make? |
| Clinical trials | What is being tested right now? |
| Company documents | What does the company already know? |
| Web | What do guidelines and papers say? |

It then writes a short brief **where every claim cites its evidence**, scores the opportunity with a
**machine-learning model**, checks its own work with a second AI acting as **judge**, and saves a **PDF + Excel report**.
All of this takes about 2 minutes.

**Why it's built carefully.** It has guardrails against prompt injection, per-user memory you can view and erase, an
audit trail, an evaluation suite with before/after numbers, and full deployment (Vercel + Railway + Supabase, with
AWS emulated through LocalStack).

<p align="center">
<img src="app_screenshots_screen_recording/01_landing_hero.png" width="49%" alt="Landing page"/>
<img src="app_screenshots_screen_recording/12_evidence_register_quality_gates_report_link.png" width="49%" alt="Evidence register, quality gates and report links"/>
<img src="app_screenshots_screen_recording/10_brief_sections_with_citations.png" width="49%" alt="Cited brief"/>
<img src="app_screenshots_screen_recording/15_guardrail_blocks_prompt_injection.png" width="49%" alt="Guardrail blocking prompt injection"/>
</p>

---

## What happens when you ask a question

```
 You: "Assess montelukast for repurposing in India"
   │
 1 ▼  Guardrail ── blocks prompt injection, harmful or off-topic requests, and strips secrets/PII from answers
 2 ▼  Memory ──── recalls what you researched before (and your usual region)
 3 ▼  Master agent (planner) ── writes a typed research plan: molecule, region, which agents to run
 4 ▼  Six agents in parallel ─┬─ Market (IQVIA*)     ─┬─ every fact becomes an evidence record
                              ├─ Trade (EXIM*)        │  [E1], [E2]… with source, trust level
                              ├─ Patents (USPTO*)     │  and a fingerprint (SHA-256)
                              ├─ Clinical trials (live ClinicalTrials.gov)
                              ├─ Company docs (RAG over PDFs)
                              └─ Web (live Firecrawl search)
 5 ▼  Scorer ──── business rules (GO / PARTIAL-GO / NO-GO) + ML probability of success, with reasons
 6 ▼  Writer ──── a cited brief: unmet need, market, trials, patents, supply, product story, risks
 7 ▼  Judge ───── checks every sentence has valid evidence; if coverage < 75 % it sends the brief back once
 8 ▼  Report ──── PDF + Excel → Supabase Storage (+ S3 mirror) → download links in chat
 9 ▼  Memory ──── saves the verdict with a link to the report (versioned, so old verdicts are kept)
```
<sub>* Market, trade and patent sources are realistic **mock APIs**, as the problem statement specifies. Clinical trials and web search are **live**.</sub>

---

## Results (measured by this repo's own evaluation scripts)

### Agent quality on a 12-question golden set: before and after fixes

| Metric | v1 baseline | **v2 (shipped)** | What it means |
|---|---|---|---|
| Evidence coverage | 0.29 | **__COV__** | Share of claims with a valid `[E#]` citation |
| Citation accuracy | 0.82 | **__CACC__** | Share of citations pointing at real evidence |
| Judge faithfulness (1–5) | 3.0 | **__FAITH__** | LLM-as-judge rating |
| Agent routing recall | 0.91 | **__REC__** | Did the planner call the agents the question needs? |
| Molecule extraction accuracy | 1.00 | **__MOL__** | |
| Guardrail block rate | 1.00 | **__BLOCK__** | Adversarial prompt refused |
| Latency p50 / p95 | 126 s / 173 s | **__P50__ s / __P95__ s** | Full assessment on one 6 GB laptop GPU |

The v1 evaluation exposed two problems: the model often stated facts without citing them, and one question was
mis-routed. The fixes were **post-hoc citation attribution** (a citation is added only when an evidence snippet
contains the claim's numbers and wording), a **routing floor** in code, and **section-aware prompts**.
Full tables: [`baseline_v1.md`](backend/evals/results/baseline_v1.md) → [`latest.md`](backend/evals/results/latest.md).

### ML opportunity scorer (scikit-learn, 4,000 synthetic projects, 5-fold CV)

| Model | CV ROC-AUC |
|---|---|
| **Logistic regression (selected)** | **0.796 ± 0.019** |
| Gradient boosting | 0.783 ± 0.021 |
| Random forest | 0.781 ± 0.019 |

Hold-out ROC-AUC **0.803**, PR-AUC 0.824, F1 0.771, Brier 0.180. The train-test gap is −0.005, so there is no
over-fitting. The simplest model won, and the README says so rather than forcing a fancier one.

### Retrieval (RAG) chunking benchmark

| Strategy | Hit@1 | Hit@5 | MRR@10 | nDCG@10 |
|---|---|---|---|---|
| Fixed 1000 chars | 0.80 | 0.93 | 0.86 | 0.89 |
| **Recursive 1200/180 (default)** | 0.80 | **1.00** | 0.89 | 0.92 |
| Parent-child 400→1600 | **0.93** | 0.97 | **0.95** | **0.96** |

Parent-child ranks best but sends about 3× more text to the model. Recursive stays the default to fit a small GPU's
context budget.

---

## Skills this project demonstrates

| Skill area | Where to look |
|---|---|
| **Build, train and evaluate ML models** | [`ml/opportunity_scorer.py`](backend/src/repurpora/ml/opportunity_scorer.py): pandas data generation and cleaning, stratified split, cross-validated model selection, ROC/PR-AUC, F1, Brier, calibration, over-fit check, permutation importance |
| **LLMs: prompting, RAG, agentic workflows** | [`nodes/core.py`](backend/src/repurpora/nodes/core.py) (LangGraph master agent, JSON-schema planning, judge loop), [`rag/`](backend/src/repurpora/rag) (hybrid retrieval) |
| **Clean, preprocess and analyse data** | pandas analytics in every agent ([`agents/workers.py`](backend/src/repurpora/agents/workers.py)): CAGR, HHI concentration, FTO scoring; PDF cleaning and chunking |
| **Clean Python, tools and APIs** | Typed settings and Pydantic schemas, FastAPI mock-data service, Agent Protocol server, ruff-clean |
| **Benchmark and experiment** | [`evals/`](backend/evals): golden-set v1→v2, chunking benchmark, latency, token and cache telemetry |
| **Read research and apply it** | [`essential_docs/`](essential_docs) papers (DrugRAG, production RAG, AHP product selection) → evidence-gated RAG and selection criteria |
| **Cloud and containers** | AWS (EC2 GPU IaC, S3, Secrets Manager, CloudWatch via LocalStack), Docker Compose (10 services), Railway, Vercel |
| **Vector DBs, embeddings, LangChain** | Supabase pgvector (HNSW index), nomic embeddings, LangChain + LangGraph 1.x |
| **Testing** | 41 pytest tests (unit, graph integration with a fake LLM, AWS emulator) + Playwright end-to-end recording |

---

## Features in detail

<details><summary><b>🤖 Multi-agent orchestration (LangGraph)</b></summary>

- The master planner returns a **typed `ResearchPlan`** (JSON schema). If the model's output can't be parsed, a heuristic planner takes over.
- **Code, not the LLM, enforces the order**: guard → plan → agents → judge → report. The model can't skip a safety step.
- Agents run in parallel with LangGraph `Send`. A failing agent never fails the whole run; you get partial results with a warning.
- Each agent may call **only its allow-listed tools**, within a call budget (policy gateway).
- A human-in-the-loop `interrupt()` before archiving a GO decision can be switched on (`REQUIRE_HUMAN_APPROVAL=true`).
</details>

<details><summary><b>📚 Retrieval-augmented generation</b></summary>

- Company PDFs are cleaned, split into section-aware chunks, and embedded with `nomic-embed-text` (768-d) into Supabase **pgvector (HNSW)**.
- **Hybrid search**: vector similarity + full-text (BM25-style), fused with **Reciprocal Rank Fusion (k=60)**, then **MMR** for diversity.
- A **corrective gate**: if nothing relevant is found, the agent returns nothing rather than grounding on noise.
- Users can **upload their own PDF**. It is indexed privately for that user only.
</details>

<details><summary><b>🧾 Evidence layer and self-checking</b></summary>

- Every fact is an `Evidence` record: id, agent, source, trust tier (registry, licensed DB, internal, web, synthetic), URL, timestamp and SHA-256.
- The brief must cite `[E#]`. The judge measures **evidence coverage** and **citation accuracy**, and asks a second model for **faithfulness**.
- Below 75 % coverage the brief is rewritten once, with the unsupported sentences listed.
</details>

<details><summary><b>🧠 Memory you can see and erase</b></summary>

| Layer | What it keeps |
|---|---|
| Session | Every thread is stored in Postgres, so you can reopen past research from the sidebar |
| Long-term | One fact per molecule × indication, with provenance (thread and report). **Versioned**: older verdicts are kept, not overwritten. Flagged **stale** after 30 days. Capped at 40. |
| Profile | Learns your usual region and uses it as the default next time |
| Your control | Ask *"What do you remember about me?"* or *"Forget my history"* |
| Isolation | Memory is per user (namespaced by Supabase user id) and never shared |
</details>

<details><summary><b>🌍 Works for any molecule, region, LLM host and language</b></summary>

| Dimension | How |
|---|---|
| Any molecule | 8 curated showcase molecules. Any other molecule gets candidate indications from **live ClinicalTrials.gov** data. |
| Any region | India, US, EU, UK, China, Japan, Brazil, Africa, Southeast Asia, Middle East, Global (detected from your wording) |
| Any LLM host | Self-hosted **Ollama** by default, or any **OpenAI-compatible** API (vLLM, LM Studio, Groq, Together, OpenAI) by setting `LLM_PROVIDER=openai`, so no GPU is required |
| Any language | Ask in Hindi, Spanish, and so on; the brief comes back in your language |
| Accessible UI | Labelled controls, a reduced-motion-aware animated background, a keyboard-friendly chat box |
</details>

<details><summary><b>🛡 Security, governance and observability</b></summary>

| Area | What's in place |
|---|---|
| Input | Prompt-injection and harmful-use detection, domain scope check, length cap |
| Untrusted content | Web pages and documents are sanitised, so instructions hidden in them are stripped |
| Output | DLP redacts API keys, JWTs, database URLs, emails, phone numbers and IDs |
| Secrets | Read from **AWS Secrets Manager** (LocalStack in the prototype), never placed in prompts |
| Auth | Supabase login; the agent server verifies ES256 JWTs via JWKS; threads are scoped per user |
| LLM proxy | Locked behind a bearer token (Caddy) |
| Tracing | **LangSmith** traces every step |
| Audit | Token usage goes to `llm_usage`; the append-only `audit_log` records guard, plan, tool, judge, archive, memory and DLP events, mirrored to CloudWatch |
| Governance | A [registry](governance/) with risk tier, model card, change log, numeric risk appetite, controls and retention |
</details>

---

## Architecture

```
Browser ──► Vercel (Next.js: landing, login, Agent Chat UI)
              │ Supabase JWT
              ▼
           Railway: agent-server (Aegra + LangGraph) ──► Railway: mock-apis (IQVIA/EXIM/USPTO/web mocks, PDF upload)
              │            │            │
              │            │            └─► live: ClinicalTrials.gov v2 · Firecrawl · LangSmith
              │            └─► Redis (LLM + tool cache)
              ▼
           Supabase: Postgres (threads, memory, pgvector, audit) · Auth · Storage (reports)
              │
           LLM: Ollama (qwen2.5 7B / 3B, nomic-embed) behind a bearer-token proxy
                prototype = local GPU via tunnel · production = AWS EC2 g4dn (scripts in infra/aws)
           AWS (LocalStack in prototype): S3 report mirror · Secrets Manager · CloudWatch audit
```
Diagrams and design decisions: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

| Layer | Tech |
|---|---|
| Agents | LangGraph 1.2, LangChain 1.5, Aegra (open-source Agent Protocol server) |
| Models | Ollama qwen2.5 7B / 3B, nomic-embed-text, or any OpenAI-compatible API; scikit-learn |
| Data | Supabase Postgres + pgvector + Auth + Storage, Redis, pandas |
| Frontend | Next.js 15, LangChain Agent Chat UI, Tailwind, framer-motion |
| Infra | Docker Compose, Railway, Vercel, LocalStack (S3, Secrets Manager, CloudWatch, EC2), Caddy, Cloudflare tunnel |
| Quality | pytest, Playwright, ruff, LangSmith |

---

## Try it

**Option 1: just use it.** Open **https://repurpora.vercel.app**, create an account, and click one of the sample questions.
<sub>The prototype's model runs on the author's GPU. If the server is offline, watch the [walkthrough video](app_screenshots_screen_recording/full_walkthrough.mp4).</sub>

**Option 2: run it locally without a GPU** (any OpenAI-compatible endpoint):
```bash
git clone https://github.com/Gurjas2112/repurpora-lazarus-graph && cd repurpora-lazarus-graph/backend
cp .env.example .env     # set SUPABASE_*, DATABASE_URL, and LLM_PROVIDER=openai + OPENAI_BASE_URL/OPENAI_API_KEY
uv sync && uv run python scripts/apply_schema.py
uv run uvicorn repurpora.mock_apis.app:app --port 8081 &
AUTH_DISABLED=true uv run aegra serve --port 2026
# new terminal
cd ../frontend && cp .env.example .env.local && npm install && npm run dev   # http://localhost:3000
```

**Option 3: the full self-hosted stack** (Ollama on your GPU, LocalStack as AWS, Redis, Caddy proxy):
```bash
ollama pull qwen2.5:7b-instruct && ollama pull qwen2.5:3b-instruct && ollama pull nomic-embed-text
docker compose up -d --wait            # add --profile ollama-container to run Ollama in Docker too
cd backend && uv run python scripts/make_synthetic_internal_docs.py && uv run python scripts/ingest.py --dir data/synthetic_internal
```

## Test and evaluate
```bash
cd backend
uv run pytest                                  # 41 tests (AWS tests auto-skip if LocalStack is off)
uv run python evals/run_evals.py --langsmith   # 12-question golden set → evals/results/latest.md
uv run python evals/rag_bench.py               # chunking benchmark
uv run python -m repurpora.ml.opportunity_scorer --train   # retrain + metrics
cd ../frontend && npx playwright test          # smoke + recorded walkthrough
```

## Deploy
| Target | Command |
|---|---|
| Railway | `railway up backend --path-as-root -s agent-server` and `-s mock-apis` (with `RAILWAY_DOCKERFILE_PATH=Dockerfile.mockapi`) |
| Vercel | `cd frontend && vercel deploy --prod` |
| AWS GPU (production) | `infra/aws/ec2_ollama.sh` (g4dn.xlarge, IMDSv2, encrypted disk, port 443 only); `infra/aws/teardown.sh` stops it |

Operations guide: [`docs/RUNBOOK.md`](docs/RUNBOOK.md).

## Repository map
```
backend/      LangGraph graph, agents, RAG, memory, ML, reports, guardrails, Aegra config, tests, evals
frontend/     Next.js landing + auth + Agent Chat UI, Playwright tests
infra/        Caddy LLM proxy, AWS scripts (LocalStack bootstrap, EC2 provisioning, teardown)
governance/   AI governance registry (manifest, model card, policies, controls, change log)
docs/         spec, architecture, runbook, 5-slide deck
app_screenshots_screen_recording/   16 step screenshots + walkthrough video + sample report
```

## Honest limitations and next steps
- Market, trade and patent data are **synthetic mocks** (as the problem statement requires). Licensed connectors would plug into the same tool interfaces.
- The ML scorer is trained on **synthetic** outcomes. Its probability is illustrative until it is retrained on real portfolio history.
- The prototype LLM is a 7B model on a laptop GPU, so a full assessment takes about 2 minutes. On an EC2 GPU or a hosted API it would be faster.
- Next: EC2 GPU host, licensed data connectors, SSO, CI with evaluation gates ([`risk_appetite.yaml`](governance/policies/risk_appetite.yaml)).

---
<sub>Built for EY Techathon 6.0, Challenge I (Pharmaceuticals). Decision support only, not medical, legal or regulatory advice. MIT licensed.</sub>
