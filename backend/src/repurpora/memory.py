"""Long-term memory layer (LangGraph Store, Postgres-backed in Aegra).

Design (reference images 6 + 13 + 1):
* **Scoped**: everything lives under ``("users", <user_id>, ...)``. One user can never read another's memory.
* **Small and capped**: at most ``MEM_CAP`` research facts. It stores facts, not transcripts, and evicts the oldest.
* **Provenance**: every fact records thread_id, report_id and a timestamp.
* **Versioned, self-correcting**: re-evaluating a molecule/indication keeps the previous verdicts
  in ``history`` (closed, not deleted). Facts older than ``STALE_DAYS`` are flagged ``stale``, never silently trusted.
* **Personalisation**: a ``profile`` item learns the user's usual region and recurring molecules, and
  the planner uses it as a default.
* **User control**: users can ask "what do you remember?" and "forget my history" (right to erasure).
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any

log = logging.getLogger(__name__)

MEM_CAP = 40
HISTORY_CAP = 5
STALE_DAYS = 30

SHOW_RE = re.compile(r"\b(what do you (remember|know about me)|show (me )?(my )?(memory|memories|history)|"
                     r"my (research )?history|what have i (researched|asked))\b", re.I)
FORGET_RE = re.compile(r"\b(forget|delete|erase|clear)\b.{0,30}\b(my|all)?\s*(memory|memories|history|data)\b", re.I)


def _ns(owner: str, kind: str = "memories") -> tuple[str, ...]:
    return ("users", owner, kind)


def _now() -> datetime:
    return datetime.now(UTC)


def _parse(ts: str | None) -> datetime | None:
    try:
        return datetime.fromisoformat(ts) if ts else None
    except ValueError:
        return None


# --------------------------------------------------------------------- read --

def load(store, owner: str | None, query: str = "", limit: int = 8) -> dict[str, Any]:
    """Return {'facts': [...ranked...], 'profile': {...}}; never raises."""
    if not (store and owner):
        return {"facts": [], "profile": {}}
    try:
        items = store.search(_ns(owner), limit=MEM_CAP)
        prof_item = store.get(_ns(owner, "profile"), "profile")
    except Exception as exc:
        log.debug("memory load failed: %s", exc)
        return {"facts": [], "profile": {}}
    q = set(re.findall(r"[a-z]{4,}", query.lower()))
    now = _now()
    facts = []
    for it in items:
        v = dict(it.value)
        ts = _parse(v.get("updated_at")) or it.updated_at
        v["stale"] = bool(ts and now - ts > timedelta(days=STALE_DAYS))
        words = set(re.findall(r"[a-z]{4,}", v.get("fact", "").lower()))
        v["_relevance"] = len(q & words) + (2 if v.get("molecule") and v["molecule"] in q else 0)
        v["_ts"] = ts.isoformat() if ts else ""
        facts.append(v)
    facts.sort(key=lambda f: (f["_relevance"], f["_ts"]), reverse=True)
    return {"facts": facts[:limit], "profile": (prof_item.value if prof_item else {})}


def context_lines(mem: dict[str, Any], k: int = 5) -> list[str]:
    """Compact, token-cheap memory context for the planner prompt."""
    out = []
    prof = mem.get("profile") or {}
    if prof.get("preferred_region"):
        out.append(f"User usually researches region: {prof['preferred_region']}")
    for f in (mem.get("facts") or [])[:k]:
        tag = " (stale - re-verify)" if f.get("stale") else ""
        out.append(f"Past finding{tag}: {f.get('fact')}")
    return out


# -------------------------------------------------------------------- write --

def _fmt_fact(plan: dict, scores: dict) -> str:
    target = plan.get("indication") or scores.get("best_opportunity")
    region = plan.get("region") or "Global"
    p = scores.get("ml_probability")
    ptxt = f", ML success probability {p:.0%}" if isinstance(p, (int, float)) else ""
    what = f"{plan['molecule']} for {target}" if target else f"{plan['molecule']} (broad screen)"
    return f"Evaluated {what} in {region}: {scores.get('decision', 'n/a')}{ptxt}"


def write_research(store, owner: str | None, thread_id: str | None, plan: dict, scores: dict,
                   report: dict) -> bool:
    if not (store and owner and plan.get("molecule")):
        return False
    try:
        ns = _ns(owner)
        key = f"{plan['molecule']}:{(plan.get('indication') or 'any').lower()}"
        prev = store.get(ns, key)
        history = []
        if prev:
            pv = prev.value
            history = ([{k: pv.get(k) for k in ("fact", "decision", "updated_at", "provenance")}]
                       + pv.get("history", []))[:HISTORY_CAP]
        else:
            existing = store.search(ns, limit=MEM_CAP + 5)
            if len(existing) >= MEM_CAP:  # hard cap: evict least-recently updated
                for it in sorted(existing, key=lambda i: i.updated_at)[: len(existing) - MEM_CAP + 1]:
                    store.delete(ns, it.key)
        store.put(ns, key, {
            "fact": _fmt_fact(plan, scores),
            "molecule": plan["molecule"],
            "indication": plan.get("indication") or scores.get("best_opportunity"),
            "region": plan.get("region"),
            "decision": scores.get("decision"),
            "ml_probability": scores.get("ml_probability"),
            "updated_at": _now().isoformat(),
            "provenance": {"thread_id": thread_id, "report_id": report.get("report_id")},
            "history": history,
        })
        _update_profile(store, owner, plan)
        return True
    except Exception as exc:
        log.debug("memory write failed: %s", exc)
        return False


def _update_profile(store, owner: str, plan: dict) -> None:
    ns = _ns(owner, "profile")
    cur = store.get(ns, "profile")
    prof = dict(cur.value) if cur else {"regions": {}, "molecules": {}}
    regions = Counter(prof.get("regions", {}))
    mols = Counter(prof.get("molecules", {}))
    if plan.get("region_explicit") and plan.get("region"):
        regions[plan["region"]] += 1
    if plan.get("molecule"):
        mols[plan["molecule"]] += 1
    prof.update({
        "regions": dict(regions), "molecules": dict(mols.most_common(15)),
        "preferred_region": regions.most_common(1)[0][0] if regions else None,
        "updated_at": _now().isoformat(),
    })
    store.put(ns, "profile", prof)


# --------------------------------------------------------------- user control --

def render_for_user(store, owner: str | None) -> str:
    mem = load(store, owner, limit=MEM_CAP)
    facts, prof = mem["facts"], mem["profile"]
    if not facts and not prof:
        return ("I don't have any saved research memory for you yet. After each assessment I remember the molecule, "
                "indication, region and verdict (with a link back to the report) so I can build on it next time.")
    lines = ["### 🧠 What I remember about your research", ""]
    if prof.get("preferred_region"):
        lines.append(f"- **Usual region:** {prof['preferred_region']}")
    if prof.get("molecules"):
        lines.append("- **Molecules you've explored:** " + ", ".join(f"{m} ({n}×)" for m, n in prof["molecules"].items()))
    lines.append("")
    for f in sorted(facts, key=lambda x: x.get("_ts", ""), reverse=True):
        stale = " _(stale - older than 30 days)_" if f.get("stale") else ""
        rid = (f.get("provenance") or {}).get("report_id")
        hist = f" · {len(f.get('history', []))} earlier version(s)" if f.get("history") else ""
        lines.append(f"- {f.get('fact')}{stale}{f' · report `{rid}`' if rid else ''}{hist}")
    lines += ["", "_Say **“forget my history”** to erase all of this._"]
    return "\n".join(lines)


def forget(store, owner: str | None) -> int:
    if not (store and owner):
        return 0
    n = 0
    try:
        for kind in ("memories", "profile"):
            for it in store.search(_ns(owner, kind), limit=MEM_CAP + 10):
                store.delete(_ns(owner, kind), it.key)
                n += 1
    except Exception as exc:
        log.warning("forget failed: %s", exc)
    return n
