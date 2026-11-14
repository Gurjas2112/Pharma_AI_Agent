# Change log (model swaps and prompt changes)

| Date | Change | Reason | Evidence |
|---|---|---|---|
| 2026-11-14 | Replaced the CrewAI prototype with a LangGraph master/worker graph | PS alignment; the old system made no LLM calls | backend/tests, evals/results |
| 2026-11-14 | LLMs: Mistral-7B GGUF -> qwen2.5 7B/3B via Ollama behind a bearer proxy | Tool and JSON-schema reliability | evals/results/latest.md |
| 2026-11-14 | Embeddings: padded-Mistral 1536-d -> nomic-embed-text 768-d | Real semantic retrieval | evals/results/rag_bench.md |
| 2026-11-14 | Evidence coverage gate 0.80 -> 0.75 | 3B judge + strict sentence splitter over-triggered redrafts | golden-set run |
| 2026-11-14 | Off-topic guard risk 0.5 -> 0.6 (now blocks) | Unit test showed off-topic requests passing | backend/tests/test_units.py |
| 2026-11-14 | Synthetic patent generator: older compound patents, fewer active secondaries | Off-patent generics were showing FTO 10/10 | API e2e run |
