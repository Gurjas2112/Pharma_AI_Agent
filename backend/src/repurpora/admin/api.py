"""Admin API: back-office control surface for the admin panel (/admin in the frontend).

Every route requires a valid Supabase JWT whose ``app_metadata.role`` is ``admin``.
Roles live in ``app_metadata``, which only the service role can write, so users can't promote themselves.
Mutations are validated, applied, and appended to the audit trail.
Generic table editing is deliberately out of scope; the panel links to Supabase Studio for that.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field, ValidationError

from repurpora import runtime_config
from repurpora.guardrails.checks import TOOL_ALLOWLIST
from repurpora.observability import audit
from repurpora.settings import get_settings
from repurpora.vault import get_secret

log = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])


# ------------------------------------------------------------------------ auth --

class Admin(BaseModel):
    id: str
    email: str | None = None


def require_admin(authorization: str | None = Header(default=None)) -> Admin:
    from repurpora.auth import verify

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "missing bearer token")
    try:
        claims = verify(authorization.split(" ", 1)[1])
    except Exception as exc:
        raise HTTPException(401, "invalid or expired token") from exc
    role = (claims.get("app_metadata") or {}).get("role")
    if role != "admin":
        raise HTTPException(403, "admin role required")
    return Admin(id=claims["sub"], email=claims.get("email"))


def _q(sql: str, params: tuple | dict = ()) -> list[tuple]:
    from repurpora.db import conn

    with conn() as c:
        return c.execute(sql, params).fetchall()


def _sb_admin(method: str, path: str, **kw) -> httpx.Response:
    s = get_settings()
    key = get_secret("SUPABASE_SECRET_KEY") or s.supabase_secret_key
    r = httpx.request(method, f"{s.supabase_url}/auth/v1/admin{path}", timeout=20,
                      headers={"apikey": key or "", "Authorization": f"Bearer {key}"}, **kw)
    if r.status_code >= 400:
        raise HTTPException(r.status_code, f"supabase admin error: {r.text[:200]}")
    return r


@router.get("/me")
def me(admin: Admin = Depends(require_admin)) -> dict:
    return {"id": admin.id, "email": admin.email, "role": "admin"}


# -------------------------------------------------------------------- overview --

@router.get("/overview")
def overview(days: int = Query(14, ge=1, le=90), admin: Admin = Depends(require_admin)) -> dict[str, Any]:
    win = {"d": days}
    usage_by_day = _q(
        "select to_char(date_trunc('day', created_at), 'YYYY-MM-DD') d, count(*), "
        "coalesce(sum(input_tokens + output_tokens),0), round(avg(latency_ms)), "
        "round(percentile_cont(0.95) within group (order by latency_ms)) "
        "from llm_usage where created_at > now() - make_interval(days => %(d)s) group by 1 order by 1", win)
    by_model = _q(
        "select model, count(*), coalesce(sum(input_tokens + output_tokens),0), round(avg(latency_ms)) "
        "from llm_usage where created_at > now() - make_interval(days => %(d)s) group by 1 order by 3 desc", win)
    by_node = _q(
        "select node, count(*), coalesce(sum(input_tokens + output_tokens),0) from llm_usage "
        "where created_at > now() - make_interval(days => %(d)s) group by 1 order by 3 desc limit 12", win)
    decisions = _q("select coalesce(decision,'n/a'), count(*) from reports "
                   "where created_at > now() - make_interval(days => %(d)s) group by 1 order by 2 desc", win)
    quality = _q(
        "select to_char(date_trunc('day', created_at), 'YYYY-MM-DD'), round(avg(evidence_coverage)::numeric, 3), "
        "round(avg(ml_score)::numeric, 3), count(*) from reports "
        "where created_at > now() - make_interval(days => %(d)s) group by 1 order by 1", win)
    events = _q("select event, count(*) from audit_log where ts > now() - make_interval(days => %(d)s) "
                "group by 1 order by 2 desc", win)
    blocked = _q("select count(*) from audit_log where event = 'guard_input' and detail->>'allowed' = 'false' "
                 "and ts > now() - make_interval(days => %(d)s)", win)[0][0]
    active = _q("select count(distinct owner) from reports where owner is not null "
                "and created_at > now() - make_interval(days => %(d)s)", win)[0][0]
    cfg = runtime_config.get()
    tokens = sum(r[2] for r in usage_by_day)
    calls = sum(r[1] for r in usage_by_day)
    n_reports = sum(r[1] for r in decisions)
    est_cost = round(tokens / 1000 * cfg.cost_per_1k_tokens_usd, 4)
    return {
        "window_days": days,
        "kpis": {"llm_calls": calls, "tokens": tokens, "reports": n_reports, "active_users": active,
                 "guard_blocks": blocked, "est_cost_usd": est_cost,
                 "cost_per_report_usd": round(est_cost / n_reports, 4) if n_reports else None,
                 "kill_switch": cfg.kill_switch},
        "usage_by_day": [{"day": d, "calls": c, "tokens": t, "avg_latency_ms": a, "p95_latency_ms": p}
                         for d, c, t, a, p in usage_by_day],
        "by_model": [{"model": m, "calls": c, "tokens": t, "avg_latency_ms": a} for m, c, t, a in by_model],
        "by_node": [{"node": n, "calls": c, "tokens": t} for n, c, t in by_node],
        "decisions": [{"decision": d, "count": c} for d, c in decisions],
        "quality_by_day": [{"day": d, "evidence_coverage": float(e) if e is not None else None,
                            "ml_score": float(m) if m is not None else None, "reports": n} for d, e, m, n in quality],
        "audit_events": [{"event": e, "count": c} for e, c in events],
    }


# ---------------------------------------------------------------- model config --

class ConfigUpdate(BaseModel):
    changes: dict[str, Any]
    reason: str = Field(min_length=3, max_length=300)


@router.get("/config")
def get_config(admin: Admin = Depends(require_admin)) -> dict:
    return {"config": runtime_config.get(force=True).model_dump(), "agents": runtime_config.ALL_AGENTS,
            "provider": get_settings().llm_provider}


@router.put("/config")
def put_config(body: ConfigUpdate, admin: Admin = Depends(require_admin)) -> dict:
    unknown = set(body.changes) - set(runtime_config.RuntimeConfig.model_fields)
    if unknown:
        raise HTTPException(422, f"unknown settings: {sorted(unknown)}")
    try:
        cfg = runtime_config.update(body.changes, actor=admin.email or admin.id, reason=body.reason)
    except (ValidationError, ValueError) as exc:
        raise HTTPException(422, str(exc)[:400]) from exc
    audit("admin_config_update", {"changes": body.changes, "reason": body.reason}, owner=admin.id)
    return {"config": cfg.model_dump()}


@router.get("/config/history")
def config_history(limit: int = Query(50, ge=1, le=500), admin: Admin = Depends(require_admin)) -> list[dict]:
    rows = _q("select key, old_value, new_value, version, changed_by, reason, changed_at from app_config_history "
              "order by changed_at desc limit %s", (limit,))
    return [{"key": k, "old": o, "new": n, "version": v, "by": b, "reason": r, "at": t.isoformat()}
            for k, o, n, v, b, r, t in rows]


# ----------------------------------------------------------- agents & RAG ----

@router.get("/agents")
def agents(admin: Admin = Depends(require_admin)) -> list[dict]:
    disabled = set(runtime_config.get().disabled_agents)
    return [{"agent": a, "tools": sorted(t), "enabled": a not in disabled} for a, t in TOOL_ALLOWLIST.items()
            if a in runtime_config.ALL_AGENTS]


@router.get("/rag/documents")
def rag_documents(admin: Admin = Depends(require_admin)) -> dict:
    rows = _q("select d.id, d.source, d.owner, d.created_at, count(c.id) chunks, "
              "coalesce(sum(length(c.content)),0) chars from rag_documents d "
              "left join rag_chunks c on c.document_id = d.id group by d.id order by d.created_at desc")
    total = _q("select count(*), count(distinct document_id) from rag_chunks")[0]
    return {"index": {"type": "pgvector HNSW (cosine) + Postgres FTS, fused with RRF k=60", "dim": 768,
                      "chunks": total[0], "documents": total[1]},
            "documents": [{"id": i, "source": s, "scope": "shared" if o is None else "private", "owner": o,
                           "created_at": t.isoformat(), "chunks": n, "chars": ch} for i, s, o, t, n, ch in rows]}


@router.delete("/rag/documents/{doc_id}")
def delete_document(doc_id: int, admin: Admin = Depends(require_admin)) -> dict:
    from repurpora.db import conn

    with conn() as c:
        row = c.execute("delete from rag_documents where id = %s returning source", (doc_id,)).fetchone()
    if not row:
        raise HTTPException(404, "document not found")
    audit("admin_rag_delete", {"doc_id": doc_id, "source": row[0]}, owner=admin.id)
    return {"deleted": doc_id, "source": row[0]}


# ---------------------------------------------------------------------- users --

class RoleUpdate(BaseModel):
    role: Literal["admin", "analyst"]


class SuspendUpdate(BaseModel):
    suspend: bool


@router.get("/users")
def users(admin: Admin = Depends(require_admin)) -> list[dict]:
    data = _sb_admin("GET", "/users", params={"page": 1, "per_page": 200}).json()
    counts = dict(_q("select owner, count(*) from reports where owner is not null group by owner"))
    out = []
    for u in data.get("users", []):
        out.append({"id": u["id"], "email": u.get("email"),
                    "role": (u.get("app_metadata") or {}).get("role", "analyst"),
                    "suspended": bool(u.get("banned_until")), "created_at": u.get("created_at"),
                    "last_sign_in_at": u.get("last_sign_in_at"), "reports": counts.get(u["id"], 0)})
    return sorted(out, key=lambda x: x.get("last_sign_in_at") or "", reverse=True)


@router.post("/users/{uid}/role")
def set_role(uid: str, body: RoleUpdate, admin: Admin = Depends(require_admin)) -> dict:
    if uid == admin.id and body.role != "admin":
        raise HTTPException(400, "you cannot remove your own admin role")
    current = _sb_admin("GET", f"/users/{uid}").json()
    meta = {**(current.get("app_metadata") or {}), "role": body.role}
    _sb_admin("PUT", f"/users/{uid}", json={"app_metadata": meta})
    audit("admin_role_change", {"user": uid, "role": body.role}, owner=admin.id)
    return {"id": uid, "role": body.role}


@router.post("/users/{uid}/suspend")
def suspend(uid: str, body: SuspendUpdate, admin: Admin = Depends(require_admin)) -> dict:
    if uid == admin.id:
        raise HTTPException(400, "you cannot suspend yourself")
    _sb_admin("PUT", f"/users/{uid}", json={"ban_duration": "876000h" if body.suspend else "none"})
    audit("admin_suspend" if body.suspend else "admin_unsuspend", {"user": uid}, owner=admin.id)
    return {"id": uid, "suspended": body.suspend}


@router.get("/users/{uid}/activity")
def user_activity(uid: str, limit: int = Query(50, ge=1, le=500), admin: Admin = Depends(require_admin)) -> list[dict]:
    rows = _q("select ts, event, detail from audit_log where owner = %s order by ts desc limit %s", (uid, limit))
    return [{"ts": t.isoformat(), "event": e, "detail": d} for t, e, d in rows]


@router.get("/audit")
def audit_log(event: str | None = None, limit: int = Query(100, ge=1, le=1000),
              admin: Admin = Depends(require_admin)) -> list[dict]:
    if event:
        rows = _q("select ts, event, owner, thread_id, detail from audit_log where event = %s "
                  "order by ts desc limit %s", (event, limit))
    else:
        rows = _q("select ts, event, owner, thread_id, detail from audit_log order by ts desc limit %s", (limit,))
    return [{"ts": t.isoformat(), "event": e, "owner": o, "thread_id": th, "detail": d} for t, e, o, th, d in rows]
