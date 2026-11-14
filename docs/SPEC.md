# Repurpora: Lazarus Graph · Prototype Specification v2.0

| Field | Value |
|---|---|
| Status | Prototype (deployed). The production phase is deferred on purpose; see §9. |
| Date | 2026-11-14 |
| Problem statement | EY Techathon 6.0, Challenge I: Pharmaceuticals (Agentic AI for drug repurposing) |
| Supersedes | v1 (CrewAI prototype) |

## 1. Problem
A generic-pharma company wants value-added products: approved molecules repurposed for **new indications,
dosage forms or patient populations**. Today the literature review behind each opportunity takes 2–3 months over
several iterations. The goal is an agentic assistant that compresses it to minutes and archives every result as a
cited report.

## 2. Scope (prototype)
| In scope | Out of scope (production phase) |
|---|---|
| Master agent plus 6 worker agents and a report generator | Real IQVIA / EXIM / paid-DB connectors (mocked per the PS) |
| Live ClinicalTrials.gov v2 and Firecrawl web search | SSO / enterprise IdP, multi-tenant orgs |
| Hybrid RAG over internal PDFs, plus user upload | Real EC2 GPU host (scripts ready; prototype uses LocalStack + a local GPU) |
| PDF/Excel reports archived to Supabase Storage (+ S3 mirror) | Kubernetes, autoscaling, multi-region |
| Supabase auth, per-user threads, audit trail | SOC2 evidence automation |
| Evaluation suite, ML opportunity scorer | Fine-tuned domain LLM |

## 3. Users & journeys
**Portfolio planner**: signs up → asks *"Assess montelukast for repurposing in India"* → watches the plan and the
parallel agents → reads a cited brief with a decision, ML score, tables and evidence → downloads the PDF/Excel →
asks follow-ups in the same thread → reopens past threads from history.

The 5-slide journey in the PS maps as follows:

| PS step | Agents |
|---|---|
| Molecule | Planner |
| Unmet need | IQVIA + internal + candidate profile |
| Ongoing trials | Clinical trials agent |
| Use in other diseases | Web + trials + candidates |
| Patents | Patent agent |
| Product story | Synthesizer + scorer + report |

## 4. Functional requirements
| ID | Requirement | Implementation |
|---|---|---|
| F1 | Interpret the query and decompose it into modular tasks | `planner`: JSON-schema `ResearchPlan` (intent, molecule, indication, region, workers, sub-queries) with heuristic fallback and deterministic validation |
| F2 | Delegate to domain workers in parallel | LangGraph `Send` fan-out → `worker` node; per-agent tool allow-list and call budget |
| F3 | IQVIA insights: market size, CAGR, competition | `run_iqvia`: tables, bar/line charts, burden-to-competition ranking with new indications first |
| F4 | EXIM: trade volumes, sourcing, import dependency | `run_exim`: partner shares, HHI, concentration-risk band, trend chart |
| F5 | Patents: status, expiry, FTO flags, filing heatmap | `run_patent`: weighted FTO score 0–10, expiring ≤ 3y, assignee × claim-type heatmap |
| F6 | Clinical trials: active trials, sponsors, phase distribution | `run_trials`: live CT.gov v2 (stub fallback), saturation band, sponsor table, phase pie |
| F7 | Internal knowledge: summarise internal docs and uploads | `run_internal`: hybrid RAG; `POST /documents/upload` (user-scoped) |
| F8 | Web intelligence: guidelines, publications, news | `run_web`: Firecrawl live (proxy fallback), sanitised and trust-tagged |
| F9 | Synthesise with references | `synthesizer`: sectioned brief, every claim cites `[E#]` |
| F10 | Report generator: PDF/Excel, download link in chat | `report`: ReportLab + matplotlib charts, openpyxl workbook, signed URLs |
| F11 | Archive reports | Supabase Storage `reports/{user}/{id}`, `reports` table, S3 mirror |
| F12 | At least 10 strategic queries | `evals/golden_queries.jsonl` (11 strategic + 1 adversarial) |

## 5. Non-functional requirements
| Area | Target (prototype) | Mechanism |
|---|---|---|
| Groundedness | Evidence coverage ≥ 0.75, citation accuracy ≥ 0.95 | Coverage gate + one redraft + LLM judge |
| Security | No secrets in prompts; injection blocked | Vault (Secrets Manager), regex and pattern guard, untrusted-content sanitiser, DLP |
| Privacy | Per-user isolation | Aegra auth handler stamps and filters `owner`; Supabase RLS on tables |
| Latency | p95 ≤ 240 s per full assessment on one 6 GB GPU | Parallel workers, 3B model for notes and judge, Redis LLM and tool cache |
| Observability | Every node and LLM call traced | LangSmith, `llm_usage`, `audit_log`, CloudWatch |
| Reliability | One worker failing must not fail the run | Per-worker try/except, node `RetryPolicy`, mock fallbacks |

## 6. Data model (Supabase)
| Object | Contents |
|---|---|
| `rag_documents`, `rag_chunks` | `vector(768)` with an HNSW index, generated `tsvector` |
| `hybrid_search()` | SQL function: RRF fusion |
| `reports` | |
| `llm_usage` | |
| `audit_log` | Append-only |
| `feedback` | |
| Aegra tables | `thread`, `runs`, `assistant`, checkpoints and store, via Aegra's own migrations |
| `reports` bucket | Private |

## 7. Interfaces
| Interface | Endpoints |
|---|---|
| Agent Protocol (Aegra) | `/threads`, `/threads/{id}/runs/stream`, `/threads/search`, `/health`. Assistant ID: `repurpora`. |
| Mock APIs | `/iqvia/market`, `/exim/trade`, `/uspto/patents`, `/trials/search`, `/web/search`, `/molecule/profile` (x-api-key); `/documents/upload` (Bearer JWT); `/reports/{id}/url` |

## 8. Evaluation plan
| Suite | Coverage |
|---|---|
| Unit and integration | `backend/tests` (37 tests: guardrails, evidence, chunking, workers, ML, graph routing with a fake LLM, LocalStack AWS) |
| Golden set | `evals/run_evals.py`: routing P/R, molecule accuracy, coverage, citation accuracy, faithfulness, keyword groundedness, block rate, latency p50/p95, tokens, cache hit rate |
| RAG | `evals/rag_bench.py`: fixed vs recursive vs parent-child, scored on Hit@k, MRR and nDCG |
| ML | CV model selection plus hold-out ROC-AUC, PR-AUC, F1, Brier, calibration, over-fit gap |

## 9. Production phase (deferred on purpose)
1. Move Ollama to EC2 g4dn.xlarge (`infra/aws/ec2_ollama.sh`) with an Elastic IP and TLS via Caddy, or move to vLLM for continuous batching.
2. Point `AWS_ENDPOINT_URL` at real AWS: Secrets Manager, S3 archive and CloudWatch (same code).
3. Replace the mock IQVIA/EXIM/USPTO servers with licensed connectors behind the same tool signatures.
4. Aegra in multi-instance mode (`REDIS_BROKER_ENABLED=true`, `RUN_MIGRATIONS_ON_STARTUP=false` + `aegra db upgrade` in CI).
5. Turn on email confirmation / SSO; turn on `REQUIRE_HUMAN_APPROVAL` for GO archival.
6. Retrain the opportunity scorer on real historical portfolio outcomes; add drift monitoring.
7. CI: GitHub Actions running pytest, the golden-set eval gate (`governance/policies/risk_appetite.yaml`), SBOM and image scan.
