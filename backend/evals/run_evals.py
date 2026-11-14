"""Golden-set evaluation of the full graph (real Ollama models).

Metrics per query (reference images 7, 12, 15, 20): routing precision/recall,
molecule extraction accuracy, evidence coverage, citation accuracy, judge
faithfulness, keyword groundedness, guardrail block accuracy, latency, tokens,
cache hit rate. Writes evals/results/latest.{json,md}; with --langsmith also
syncs the golden set as a LangSmith dataset.

usage: uv run python evals/run_evals.py [--limit N] [--ids Q01,Q02] [--langsmith]
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

from repurpora.cache import STATS, hit_rate
from repurpora.graph import build_graph
from repurpora.observability import UsageCallback

HERE = Path(__file__).parent
OUT = HERE / "results"


def run_one(g, case: dict) -> dict:
    cb = UsageCallback()
    cfg = {"configurable": {"thread_id": f"eval-{case['id']}-{int(time.time())}", "user_id": "eval"},
           "callbacks": [cb], "recursion_limit": 40, "tags": ["eval", case["id"]]}
    t0 = time.time()
    st = g.invoke({"messages": [("user", case["query"])]}, cfg)
    lat = time.time() - t0
    final = str(st["messages"][-1].content)
    row = {"id": case["id"], "latency_s": round(lat, 1), "tokens_in": cb.totals["input_tokens"],
           "tokens_out": cb.totals["output_tokens"], "llm_calls": cb.totals["calls"]}
    if case.get("expect_blocked"):
        row["blocked_ok"] = (st.get("guard") or {}).get("allowed") is False
        return row
    plan = st.get("plan") or {}
    got = set(plan.get("workers") or [])
    exp = set(case["expect_workers"])
    row["routing_recall"] = round(len(got & exp) / len(exp), 2) if exp else 1.0
    row["routing_precision"] = round(len(got & exp) / len(got), 2) if got else 0.0
    row["molecule_ok"] = (plan.get("molecule") or None) == case.get("expect_molecule")
    j = st.get("judge") or {}
    row["evidence_coverage"] = j.get("evidence_coverage")
    row["citation_accuracy"] = j.get("citation_accuracy")
    row["faithfulness"] = j.get("faithfulness")
    row["redrafts"] = st.get("redrafts", 0)
    row["keywords_ok"] = all(k.lower() in final.lower() for k in case.get("must_mention", []))
    row["decision"] = (st.get("scores") or {}).get("decision")
    row["report_archived"] = bool((st.get("report") or {}).get("pdf_url"))
    return row


def summarise(rows: list[dict]) -> dict:
    research = [r for r in rows if "routing_recall" in r]

    def mean(k):
        v = [r[k] for r in research if isinstance(r.get(k), (int, float)) and not isinstance(r.get(k), bool)]
        return round(statistics.mean(v), 3) if v else None

    lats = sorted(r["latency_s"] for r in rows)
    p95 = lats[min(len(lats) - 1, int(round(0.95 * (len(lats) - 1))))]
    blocked = [r for r in rows if "blocked_ok" in r]
    return {
        "n": len(rows),
        "routing_recall": mean("routing_recall"),
        "routing_precision": mean("routing_precision"),
        "molecule_accuracy": round(sum(r["molecule_ok"] for r in research) / max(len(research), 1), 3),
        "evidence_coverage": mean("evidence_coverage"),
        "citation_accuracy": mean("citation_accuracy"),
        "faithfulness_1to5": mean("faithfulness"),
        "keyword_groundedness": round(sum(r["keywords_ok"] for r in research) / max(len(research), 1), 3),
        "guardrail_block_rate": round(sum(r["blocked_ok"] for r in blocked) / max(1, len(blocked)), 3),
        "latency_p50_s": statistics.median(lats),
        "latency_p95_s": p95,
        "avg_tokens_per_query": round(statistics.mean(r["tokens_in"] + r["tokens_out"] for r in rows)),
        "tool_cache_hit_rate": round(hit_rate(), 3),
        "cache_stats": dict(STATS),
        "reports_archived": sum(r.get("report_archived", False) for r in research),
    }


def to_md(summary: dict, rows: list[dict]) -> str:
    lines = ["# Golden-set evaluation", "", "| metric | value |", "|---|---|"]
    lines += [f"| {k} | {v} |" for k, v in summary.items() if k != "cache_stats"]
    cols = ["id", "latency_s", "routing_recall", "routing_precision", "molecule_ok", "evidence_coverage",
            "citation_accuracy", "faithfulness", "redrafts", "keywords_ok", "decision", "blocked_ok"]
    lines += ["", "| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for r in rows:
        lines.append("| " + " | ".join(str(r.get(c, "")) for c in cols) + " |")
    return "\n".join(lines) + "\n"


def push_langsmith(cases: list[dict]) -> None:
    from langsmith import Client

    client = Client()
    name = "repurpora-golden-v1"
    if not client.has_dataset(dataset_name=name):
        ds = client.create_dataset(name, description="Repurpora strategic pharma queries (golden set)")
        client.create_examples(dataset_id=ds.id, inputs=[{"query": c["query"]} for c in cases],
                               outputs=[{k: v for k, v in c.items() if k != "query"} for c in cases])
    print("LangSmith dataset ready:", name)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--ids", default="")
    ap.add_argument("--langsmith", action="store_true")
    a = ap.parse_args()
    cases = [json.loads(ln) for ln in (HERE / "golden_queries.jsonl").read_text().splitlines() if ln.strip()]
    if a.ids:
        cases = [c for c in cases if c["id"] in a.ids.split(",")]
    if a.limit:
        cases = cases[: a.limit]
    g = build_graph(InMemorySaver(), InMemoryStore())
    rows = []
    for c in cases:
        r = run_one(g, c)
        print(json.dumps(r), flush=True)
        rows.append(r)
    s = summarise(rows)
    OUT.mkdir(exist_ok=True)
    (OUT / "latest.json").write_text(json.dumps({"summary": s, "rows": rows}, indent=2))
    (OUT / "latest.md").write_text(to_md(s, rows))
    print(json.dumps(s, indent=2))
    if a.langsmith:
        push_langsmith(cases)
