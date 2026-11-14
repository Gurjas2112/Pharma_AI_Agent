"""RAG chunking-strategy benchmark: fixed vs recursive vs parent-child.

Self-supervised retrieval benchmark: for each document we sample sentences,
compress them into keyword queries (stop-words dropped, truncated), and check
whether the retrieved chunk contains the source sentence. Reports Hit@1,
Hit@5, MRR@10 and nDCG@10 per strategy, plus index size and latency.

usage: uv run python evals/rag_bench.py [--docs 4] [--queries 15]
"""

from __future__ import annotations

import argparse
import json
import math
import random
import re
import time
from pathlib import Path

import numpy as np

from repurpora.llm import get_embeddings
from repurpora.rag.chunking import STRATEGIES, clean
from repurpora.rag.ingest import pdf_pages
from repurpora.rag.retriever import LocalIndex
from repurpora.settings import BACKEND_DIR

STOP = set("the a an of and or to in for on with by is are was were be been this that these those as at from it its".split())


def make_queries(pages, n, rng):
    sents = [s.strip() for _, t in pages for s in re.split(r"(?<=[.!?])\s+", clean(t)) if 80 < len(s) < 260]
    rng.shuffle(sents)
    out = []
    for s in sents[:n]:
        words = [w for w in re.findall(r"[A-Za-z0-9\-]+", s) if w.lower() not in STOP]
        out.append((" ".join(words[: max(6, int(len(words) * 0.7))]), " ".join(s.split())[:40]))
    return out


def evaluate(strategy, pages, source, queries, emb):
    chunks = STRATEGIES[strategy](pages, source)
    t0 = time.time()
    vecs = emb.embed_documents([f"search_document: {c.content}" for c in chunks])
    idx = LocalIndex([{"source": source, "page": c.page, "content": c.parent or c.content, "embedding": v}
                      for c, v in zip(chunks, vecs, strict=True)])
    build = time.time() - t0
    hits1 = hits5 = rr = ndcg = 0.0
    lat = []
    for q, needle in queries:
        t = time.time()
        res = idx.search(q, emb.embed_query(f"search_query: {q}"), 10)
        lat.append(time.time() - t)
        ranks = [i for i, r in enumerate(res[:10]) if needle in " ".join(r["content"].split())]
        if ranks:
            k = ranks[0]
            hits1 += k == 0
            hits5 += k < 5
            rr += 1 / (k + 1)
            ndcg += 1 / math.log2(k + 2)
    n = len(queries) or 1
    return {"strategy": strategy, "chunks": len(chunks), "hit@1": hits1 / n, "hit@5": hits5 / n,
            "mrr@10": rr / n, "ndcg@10": ndcg / n, "embed_build_s": build, "query_ms_p50": 1000 * float(np.median(lat))}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", type=int, default=4)
    ap.add_argument("--queries", type=int, default=15)
    a = ap.parse_args()
    rng = random.Random(7)
    emb = get_embeddings()
    docs = sorted((BACKEND_DIR / "data" / "internal_docs").glob("*.pdf"), key=lambda p: p.stat().st_size)[: a.docs]
    agg: dict[str, list[dict]] = {}
    for d in docs:
        pages = pdf_pages(d.read_bytes(), max_pages=30)
        qs = make_queries(pages, a.queries, rng)
        for strat in STRATEGIES:
            agg.setdefault(strat, []).append(evaluate(strat, pages, d.name, qs, emb))
    keys = ["chunks", "hit@1", "hit@5", "mrr@10", "ndcg@10", "query_ms_p50"]
    table = [{"strategy": s, **{k: round(float(np.mean([r[k] for r in rows])), 3) for k in keys}} for s, rows in agg.items()]
    out = Path(__file__).parent / "results"
    out.mkdir(exist_ok=True)
    (out / "rag_bench.json").write_text(json.dumps({"docs": [d.name for d in docs], "results": table}, indent=2))
    md = ["| strategy | avg chunks/doc | Hit@1 | Hit@5 | MRR@10 | nDCG@10 | query ms p50 |", "|---|---|---|---|---|---|---|"]
    md += [f"| {r['strategy']} | {r['chunks']} | {r['hit@1']} | {r['hit@5']} | {r['mrr@10']} | {r['ndcg@10']} | "
           f"{r['query_ms_p50']} |" for r in table]
    (out / "rag_bench.md").write_text("# RAG chunking benchmark\n\nDocs: " + ", ".join(d.name for d in docs)
                                      + "\n\n" + "\n".join(md) + "\n")
    print("\n".join(md))
