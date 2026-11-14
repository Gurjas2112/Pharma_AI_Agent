"""Hybrid retrieval: dense (pgvector HNSW, cosine) + sparse (Postgres FTS / BM25)
fused with Reciprocal Rank Fusion (k=60), then MMR de-duplication and a
corrective relevance gate (CRAG-style: weak retrieval -> return nothing so the
planner's web agent covers it instead of hallucinating from noise).

Falls back to a local in-memory index (numpy cosine + rank_bm25-style scoring)
when the database is unavailable.
"""

from __future__ import annotations

import json
import logging
import math
import re
from collections import Counter
from functools import lru_cache

import numpy as np

from repurpora.cache import cached

log = logging.getLogger(__name__)
RRF_K = 60
MIN_DENSE_SIM = 0.45  # corrective gate on best cosine similarity


def _embed_query(q: str) -> list[float]:
    from repurpora.llm import get_embeddings

    return get_embeddings().embed_query(f"search_query: {q}")


# ------------------------------------------------------------- DB path -----

def _db_search(q: str, qv: list[float], k: int, owner: str | None) -> list[dict]:
    from repurpora.db import conn, vec_literal

    with conn() as c:
        rows = c.execute(
            "select id, source, page, content, parent_content, dense_sim, rrf_score "
            "from hybrid_search(%s::vector, %s, %s, %s)",
            (vec_literal(qv), q, k * 3, owner),
        ).fetchall()
    return [{"id": r[0], "source": r[1], "page": r[2], "content": r[4] or r[3], "dense": float(r[5] or 0),
             "score": float(r[6]), "mode": "pgvector+fts"} for r in rows]


# ---------------------------------------------------------- local path -----

_TOK = re.compile(r"[a-z0-9]+")


class LocalIndex:
    def __init__(self, rows: list[dict]):
        self.rows = rows
        self.mat = np.array([r["embedding"] for r in rows], dtype=np.float32) if rows else np.zeros((0, 768))
        if len(self.mat):
            self.mat /= np.linalg.norm(self.mat, axis=1, keepdims=True) + 1e-9
        self.toks = [_TOK.findall(r["content"].lower()) for r in rows]
        self.df = Counter(t for doc in self.toks for t in set(doc))
        self.avgdl = (sum(map(len, self.toks)) / len(self.toks)) if self.toks else 1.0

    def bm25(self, q: str, k1: float = 1.5, b: float = 0.75) -> np.ndarray:
        n = len(self.toks)
        scores = np.zeros(n)
        for t in set(_TOK.findall(q.lower())):
            df = self.df.get(t)
            if not df:
                continue
            idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
            for i, doc in enumerate(self.toks):
                tf = doc.count(t)
                if tf:
                    scores[i] += idf * tf * (k1 + 1) / (tf + k1 * (1 - b + b * len(doc) / self.avgdl))
        return scores

    def search(self, q: str, qv: list[float], k: int) -> list[dict]:
        if not self.rows:
            return []
        v = np.array(qv, dtype=np.float32)
        v /= np.linalg.norm(v) + 1e-9
        dense = self.mat @ v
        sparse = self.bm25(q)
        d_rank = {i: r for r, i in enumerate(np.argsort(-dense)[: k * 4])}
        s_rank = {i: r for r, i in enumerate(np.argsort(-sparse)[: k * 4]) if sparse[i] > 0}
        fused = Counter()
        for i, r in d_rank.items():
            fused[i] += 1 / (RRF_K + r + 1)
        for i, r in s_rank.items():
            fused[i] += 1 / (RRF_K + r + 1)
        out = []
        for i, sc in fused.most_common(k * 3):
            row = self.rows[i]
            out.append({"id": i, "source": row["source"], "page": row["page"], "content": row["content"],
                        "dense": float(dense[i]), "score": float(sc), "mode": "local-hybrid",
                        "_vec": self.mat[i]})
        return out


@lru_cache(maxsize=1)
def _local() -> LocalIndex:
    from repurpora.rag.ingest import LOCAL_INDEX

    rows = []
    if LOCAL_INDEX.exists():
        rows = [json.loads(ln) for ln in LOCAL_INDEX.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return LocalIndex(rows)


def reset_local_index() -> None:
    _local.cache_clear()


def _mmr(cands: list[dict], k: int, lam: float = 0.7) -> list[dict]:
    """Maximal marginal relevance on text overlap (cheap diversity filter)."""
    chosen: list[dict] = []
    sets = [set(_TOK.findall(c["content"].lower())) for c in cands]
    rel = [c["score"] for c in cands]
    mx = max(rel) if rel else 1
    idx = list(range(len(cands)))
    while idx and len(chosen) < k:
        best, best_s = None, -1e9
        for i in idx:
            div = max((len(sets[i] & sets[j]) / (len(sets[i] | sets[j]) or 1) for j in
                       [cands.index(c) for c in chosen]), default=0)
            s = lam * rel[i] / mx - (1 - lam) * div
            if s > best_s:
                best, best_s = i, s
        chosen.append(cands[best])
        idx.remove(best)
    return chosen


@cached("rag", ttl=1800)
def rag_search(query: str, k: int = 5, owner: str | None = None) -> list[dict]:
    try:
        qv = _embed_query(query)
    except Exception as exc:
        log.warning("embedding unavailable: %s", exc)
        return []
    cands: list[dict] = []
    try:
        cands = _db_search(query, qv, k, owner)
    except Exception as exc:
        log.info("db retrieval unavailable (%s) -> local index", type(exc).__name__)
    if not cands:
        cands = _local().search(query, qv, k)
    if not cands or max(c["dense"] for c in cands) < MIN_DENSE_SIM:
        return []  # corrective gate
    out = _mmr(cands, k)
    for c in out:
        c.pop("_vec", None)
    return out
