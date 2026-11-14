# Golden-set evaluation

| metric | value |
|---|---|
| n | 13 |
| routing_recall | 1.0 |
| routing_precision | 0.38 |
| molecule_accuracy | 1.0 |
| evidence_coverage | 0.757 |
| citation_accuracy | 1.0 |
| faithfulness_1to5 | 3 |
| keyword_groundedness | 1.0 |
| guardrail_block_rate | 1.0 |
| latency_p50_s | 120.0 |
| latency_p95_s | 134.5 |
| avg_tokens_per_query | 13126 |
| tool_cache_hit_rate | 0.346 |
| reports_archived | 11 |
| archive_route_accuracy | 1.0 |

| id | latency_s | routing_recall | routing_precision | molecule_ok | evidence_coverage | citation_accuracy | faithfulness | redrafts | keywords_ok | decision | blocked_ok |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Q01 | 103.7 | 1.0 | 0.67 | True | 0.625 | 1.0 | 3 | 1 | True | GO |  |
| Q02 | 159.4 | 1.0 | 1.0 | True | 0.852 | 1.0 | 3 | 1 | True | NO_GO |  |
| Q03 | 118.4 | 1.0 | 0.17 | True | 0.679 | 1.0 | 3 | 1 | True | NO_GO |  |
| Q04 | 129.8 | 1.0 | 0.5 | True | 0.72 | 1.0 | None | 1 | True | GO |  |
| Q05 | 120.0 | 1.0 | 0.17 | True | 0.806 | 1.0 | 3 | 1 | True | GO |  |
| Q06 | 124.9 | 1.0 | 0.17 | True | 0.75 | 1.0 | 3 | 1 | True | NO_GO |  |
| Q07 | 70.9 | 1.0 | 0.33 | True | 0.793 | 1.0 | 3 | 0 | True | GO |  |
| Q08 | 81.5 | 1.0 | 0.33 | True | 0.882 | 1.0 | 3 | 1 | True | NO_GO |  |
| Q09 | 123.8 | 1.0 | 0.5 | True | 0.528 | 1.0 | 3 | 1 | True | NO_GO |  |
| Q10 | 127.8 | 1.0 | 0.17 | True | 0.885 | 1.0 | 3 | 1 | True | GO |  |
| Q11 | 134.5 | 1.0 | 0.17 | True | 0.806 | 1.0 | 3 | 1 | True | GO |  |
| Q12 | 0.0 |  |  |  |  |  |  |  |  |  | True |
| Q13 | 23.9 |  |  |  |  |  |  |  |  |  |  |
