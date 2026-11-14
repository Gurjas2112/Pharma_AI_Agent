# Model card: Repurpora system

## Intended use
Internal decision support for triaging repurposing opportunities. **Not** for clinical, regulatory or legal
decisions. Every output is a draft for expert review.

## Components
| Component | Model | Role | Notes |
|---|---|---|---|
| Master planner | qwen2.5 7B instruct | Structured `ResearchPlan` (JSON schema) | Heuristic fallback if parsing fails |
| Worker notes | qwen2.5 3B instruct | 2-3 bullet interpretation per agent | Facts only from tool data |
| Synthesizer | qwen2.5 7B instruct | Cited brief (`[E#]`) | Redrafted when evidence coverage < 0.75 |
| Judge | qwen2.5 3B instruct | Faithfulness 1-5 + unsupported claims | Separate from the writer |
| Opportunity scorer | scikit-learn LogisticRegression | p(success) + local drivers | Trained on **synthetic** data |
| Embeddings | nomic-embed-text (768-d) | Hybrid RAG | pgvector HNSW + FTS + RRF |
| Archive SQL agent | qwen2.5 7B (JSON) | Text-to-SQL over the user's own reports | Validator + `archive_reader` role + RLS; template fallback |

## Opportunity scorer metrics (v2 pipeline, out-of-time test 2023–2025, synthetic data)
| Model | 5-fold CV ROC-AUC | Train AUC |
|---|---|---|
| Logistic regression (**selected**, one-SE rule) | 0.775 ± 0.013 | 0.789 |
| Histogram gradient boosting | 0.766 ± 0.009 | 0.927 (over-fits) |
| Random forest | 0.760 ± 0.012 | 0.881 |

Test (n = 1,268):
- ROC-AUC **0.776** (95% CI 0.752–0.802), PR-AUC 0.830, MCC 0.423, balanced accuracy 0.715.
- Calibration: ECE 0.059 (sigmoid calibrated).
- Decision cost (2·FP + FN): **507**, against **721** for the business-rule gate and 1,006 for an always-yes dummy.

The threshold is cost-sensitive (0.66). Full report: `backend/src/repurpora/ml/reports/model_report.md`.

## Known limitations
- Market, trade and patent data are synthetic mocks, as the problem statement requires. Clinical trials and web search are live.
- Small local LLMs can mis-route or under-cite. Mitigations: schema validation, deterministic plan post-validation, a coverage gate, redraft, and a judge.
- The ML model is trained on synthetic data, so its probability is illustrative until it is retrained on real portfolio history.
