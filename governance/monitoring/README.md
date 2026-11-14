# Monitoring signals
| Signal | Where |
|---|---|
| Traces (every node, LLM call and tool call) | LangSmith projects `repurpora` (local) / `repurpora-prod` (Railway) |
| Token usage and latency per call | Supabase `llm_usage` (UsageCallback) |
| Quality (coverage, citation accuracy, faithfulness) | `audit_log` event `judge`; evals/results |
| Guardrail hits, DLP redactions | `audit_log` events `guard_input`, `dlp_redaction`; CloudWatch `/repurpora/audit` |
| Cost per decision | llm_usage tokens x GPU-hour cost (self-hosted) |
| User feedback | `feedback` table (thumbs up/down) |
