# AI Governance Registry: Repurpora / Lazarus Graph

This registry follows the "AI governance registry" structure from the reference material. Every AI system in the
product has a folder under `systems/`. Policies, controls, evidence, monitoring and audit live beside it, so a reviewer
can trace any high-risk inference back to its owner, model, prompts and evidence.

| Folder | Contents |
|---|---|
| `systems/repurpora/` | `manifest.yaml` (owner, purpose, risk tier), `model_card.md`, `change_log.md` |
| `policies/` | acceptable and prohibited use, numeric risk appetite |
| `controls/` | DLP rules, content filters, human-review gates (machine-readable YAML, mirrored in code) |
| `evidence/` | pre-deployment test and eval results (pytest, golden-set eval, RAG bench, ML metrics) |
| `monitoring/` | drift, cost and quality signals, and where each is collected |
| `audit/` | where decision and access logs live, retention schedule |
| `OWNERS.md` | escalation chain |
