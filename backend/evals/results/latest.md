# Golden-set evaluation

| metric | value |
|---|---|
| n | 12 |
| routing_recall | 0.909 |
| routing_precision | 0.637 |
| molecule_accuracy | 1.0 |
| evidence_coverage | 0.287 |
| citation_accuracy | 0.818 |
| faithfulness_1to5 | 3 |
| keyword_groundedness | 0.818 |
| guardrail_block_rate | 1.0 |
| latency_p50_s | 126.3 |
| latency_p95_s | 172.6 |
| avg_tokens_per_query | 9610 |
| tool_cache_hit_rate | 0.14 |
| reports_archived | 11 |

| id | latency_s | routing_recall | routing_precision | molecule_ok | evidence_coverage | citation_accuracy | faithfulness | redrafts | keywords_ok | decision | blocked_ok |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Q01 | 51.0 | 1.0 | 1.0 | True | 0.5 | 1.0 | None | 1 | False | NO_GO |  |
| Q02 | 24.5 | 1.0 | 1.0 | True | 0.5 | 1.0 | None | 1 | True | NO_GO |  |
| Q03 | 104.9 | 1.0 | 1.0 | True | 0.038 | 1.0 | 4 | 1 | True | NO_GO |  |
| Q04 | 127.0 | 0.0 | 0.0 | True | 0.421 | 1.0 | 3 | 1 | True | INSIGHT |  |
| Q05 | 104.8 | 1.0 | 1.0 | True | 0.0 | 0.0 | 2 | 1 | True | INSIGHT |  |
| Q06 | 183.0 | 1.0 | 0.17 | True | 0.2 | 1.0 | 3 | 1 | True | GO |  |
| Q07 | 125.6 | 1.0 | 0.67 | True | 0.348 | 1.0 | 3 | 1 | True | GO |  |
| Q08 | 145.3 | 1.0 | 1.0 | True | 0.6 | 1.0 | 2 | 1 | False | INSIGHT |  |
| Q09 | 160.5 | 1.0 | 0.5 | True | 0.348 | 1.0 | 3 | 1 | True | GO |  |
| Q10 | 128.1 | 1.0 | 0.5 | True | 0.0 | 0.0 | 3 | 1 | True | GO |  |
| Q11 | 172.6 | 1.0 | 0.17 | True | 0.205 | 1.0 | 4 | 1 | True | GO |  |
| Q12 | 0.0 |  |  |  |  |  |  |  |  |  | True |
