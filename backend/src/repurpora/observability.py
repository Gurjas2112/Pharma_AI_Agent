"""Observability: LangSmith tracing (env-driven), token telemetry, audit trail.

* LangSmith: set ``LANGSMITH_TRACING=true`` + ``LANGSMITH_API_KEY``; every node,
  LLM call and tool call is traced under project ``LANGSMITH_PROJECT``.
* ``UsageCallback``: captures per-call token usage + latency -> ``llm_usage``.
* ``audit``: append-only events -> ``audit_log`` table and CloudWatch Logs
  (LocalStack in prototype). Prompts are stored as SHA-256 only.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

from repurpora.settings import get_settings

log = logging.getLogger("repurpora.audit")
_cw_lock = threading.Lock()
_cw_ready = False


def _bg(fn, *a):
    threading.Thread(target=fn, args=a, daemon=True).start()


def _cloudwatch(event: dict[str, Any]) -> None:
    global _cw_ready
    s = get_settings()
    if not s.aws_endpoint_url:
        return
    try:
        import boto3

        cw = boto3.client("logs", endpoint_url=s.aws_endpoint_url, region_name=s.aws_region)
        with _cw_lock:
            if not _cw_ready:
                for fn, kw in ((cw.create_log_group, {"logGroupName": s.aws_log_group}),
                               (cw.create_log_stream, {"logGroupName": s.aws_log_group, "logStreamName": "graph"})):
                    try:
                        fn(**kw)
                    except cw.exceptions.ResourceAlreadyExistsException:
                        pass
                _cw_ready = True
        cw.put_log_events(logGroupName=s.aws_log_group, logStreamName="graph",
                          logEvents=[{"timestamp": int(time.time() * 1000), "message": json.dumps(event, default=str)}])
    except Exception as exc:
        log.debug("cloudwatch skipped: %s", type(exc).__name__)


def _db_audit(event: str, thread_id: str | None, owner: str | None, detail: dict, prompt_sha: str | None) -> None:
    try:
        from psycopg.types.json import Jsonb

        from repurpora.db import conn

        with conn() as c:
            c.execute("insert into audit_log(thread_id, owner, event, detail, prompt_sha) values (%s,%s,%s,%s,%s)",
                      (thread_id, owner, event, Jsonb(detail), prompt_sha))
    except Exception as exc:
        log.debug("audit db skipped: %s", type(exc).__name__)


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:24]


def audit(event: str, detail: dict[str, Any], thread_id: str | None = None, owner: str | None = None,
          prompt: str | None = None) -> None:
    rec = {"event": event, "thread_id": thread_id, "owner": owner, "detail": detail}
    log.info("audit %s", json.dumps(rec, default=str)[:500])
    p = sha(prompt) if prompt else None
    _bg(_db_audit, event, thread_id, owner, detail, p)
    _bg(_cloudwatch, rec)


class UsageCallback(BaseCallbackHandler):
    """Token telemetry (reference image 8) - non-blocking writes."""

    def __init__(self, thread_id: str | None = None, owner: str | None = None):
        self.thread_id, self.owner = thread_id, owner
        self._t: dict[UUID, tuple[float, str, str]] = {}
        self.totals = {"input_tokens": 0, "output_tokens": 0, "calls": 0}

    def on_chat_model_start(self, serialized, messages, *, run_id, tags=None, metadata=None, **kw):
        model = (metadata or {}).get("ls_model_name") or (serialized or {}).get("kwargs", {}).get("model", "?")
        node = (metadata or {}).get("langgraph_node", "?")
        self._t[run_id] = (time.perf_counter(), str(model), str(node))

    def on_llm_end(self, response: LLMResult, *, run_id, **kw):
        t0, model, node = self._t.pop(run_id, (time.perf_counter(), "?", "?"))
        it = ot = 0
        for gens in response.generations:
            for g in gens:
                um = getattr(getattr(g, "message", None), "usage_metadata", None) or {}
                it += um.get("input_tokens", 0)
                ot += um.get("output_tokens", 0)
        self.totals["input_tokens"] += it
        self.totals["output_tokens"] += ot
        self.totals["calls"] += 1
        row = (str(run_id), self.thread_id, self.owner, model, node, it, ot, int((time.perf_counter() - t0) * 1000))
        _bg(self._write, row)

    @staticmethod
    def _write(row) -> None:
        try:
            from repurpora.db import conn

            with conn() as c:
                c.execute("insert into llm_usage(run_id, thread_id, owner, model, node, input_tokens, output_tokens,"
                          " latency_ms) values (%s,%s,%s,%s,%s,%s,%s,%s)", row)
        except Exception:
            pass
