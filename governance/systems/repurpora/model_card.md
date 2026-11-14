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

## Opportunity scorer metrics (hold-out, synthetic data)
5-fold CV ROC-AUC: logistic regression 0.796, random forest 0.781, gradient boosting 0.783.
Selected model: logistic regression. Test ROC-AUC 0.803, PR-AUC 0.824, F1 0.771, Brier 0.180.
Train-test AUC gap is -0.005, so there is no over-fitting.
Label noise in the synthetic generator caps achievable AUC. The simpler model won on purpose: the latent function
is close to linear in the transformed features.

## Known limitations
- Market, trade and patent data are synthetic mocks, as the problem statement requires. Clinical trials and web search are live.
- Small local LLMs can mis-route or under-cite. Mitigations: schema validation, deterministic plan post-validation, a coverage gate, redraft, and a judge.
- The ML model is trained on synthetic data, so its probability is illustrative until it is retrained on real portfolio history.
