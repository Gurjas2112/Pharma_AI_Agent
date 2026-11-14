# Owners and escalation

| Role | Responsibility | Contact |
|---|---|---|
| System owner | Product decisions, risk acceptance | Repository owner (GitHub: Gurjas2112) |
| ML/LLM owner | Models, prompts, evals, guardrails | Repository owner |
| Data owner | Supabase data, retention, RLS | Repository owner |
| Security contact | Key rotation, incident response | Repository owner |

Escalation: incident -> system owner (within 4h) -> rotate affected secrets -> post-mortem in `evidence/incident_log.md`.
