"""Runtime configuration managed from the admin panel.

Values live in the ``app_config`` table, versioned, with each change appended to ``app_config_history``.
The graph reads them through :func:`get` with a short TTL, so admin changes apply within seconds and
without a redeploy. If the DB is unreachable, the env-driven :mod:`repurpora.settings` defaults apply.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from pydantic import BaseModel, Field

from repurpora.settings import get_settings

log = logging.getLogger(__name__)
ALL_AGENTS = ["iqvia", "exim", "patent", "clinical_trials", "internal", "web"]
_TTL_S = 15
_cache: dict[str, Any] = {"at": 0.0, "cfg": None}


class RuntimeConfig(BaseModel):
    """Admin-editable knobs. Field constraints are the validation contract for the admin API."""

    llm_model_primary: str = Field(min_length=1, max_length=80)
    llm_model_fast: str = Field(min_length=1, max_length=80)
    llm_temperature: float = Field(ge=0.0, le=1.5)
    evidence_coverage_threshold: float = Field(ge=0.0, le=1.0)
    max_redrafts: int = Field(ge=0, le=3)
    require_human_approval: bool
    disabled_agents: list[str] = Field(default_factory=list)
    kill_switch: bool = False
    maintenance_message: str = Field(default="Repurpora is temporarily paused by an administrator.", max_length=300)
    cost_per_1k_tokens_usd: float = Field(default=0.0004, ge=0, le=1)  # self-hosted GPU amortised estimate

    def model_post_init(self, __context) -> None:
        bad = set(self.disabled_agents) - set(ALL_AGENTS)
        if bad:
            raise ValueError(f"unknown agents: {sorted(bad)}")
        if len(set(self.disabled_agents)) == len(ALL_AGENTS):
            raise ValueError("at least one agent must stay enabled")


def defaults() -> RuntimeConfig:
    s = get_settings()
    return RuntimeConfig(llm_model_primary=s.llm_model_primary, llm_model_fast=s.llm_model_fast,
                         llm_temperature=s.llm_temperature, evidence_coverage_threshold=s.evidence_coverage_threshold,
                         max_redrafts=s.max_redrafts, require_human_approval=s.require_human_approval)


def _load() -> RuntimeConfig:
    base = defaults().model_dump()
    try:
        from repurpora.db import conn

        with conn() as c:
            rows = c.execute("select key, value from app_config").fetchall()
        for k, v in rows:
            if k in base:
                base[k] = v
    except Exception as exc:
        log.debug("runtime config from DB unavailable (%s) - using defaults", type(exc).__name__)
    try:
        return RuntimeConfig(**base)
    except Exception as exc:  # corrupt row -> never take the service down
        log.warning("invalid runtime config in DB (%s) - using defaults", exc)
        return defaults()


def get(force: bool = False) -> RuntimeConfig:
    now = time.time()
    if force or _cache["cfg"] is None or now - _cache["at"] > _TTL_S:
        _cache["cfg"], _cache["at"] = _load(), now
    return _cache["cfg"]


def update(changes: dict[str, Any], actor: str, reason: str = "") -> RuntimeConfig:
    """Validate the merged config, then upsert each changed key and record history in one transaction."""
    from psycopg.types.json import Jsonb

    from repurpora.db import conn

    current = get(force=True)
    merged = RuntimeConfig(**{**current.model_dump(), **changes})  # raises on invalid input
    diff = {k: v for k, v in merged.model_dump().items() if current.model_dump().get(k) != v}
    if diff:
        with conn() as c, c.transaction():
            for k, v in diff.items():
                row = c.execute(
                    "insert into app_config(key, value, version, updated_by) values (%s,%s,1,%s) "
                    "on conflict (key) do update set value = excluded.value, version = app_config.version + 1, "
                    "updated_by = excluded.updated_by, updated_at = now() returning version",
                    (k, Jsonb(v), actor),
                ).fetchone()
                c.execute("insert into app_config_history(key, old_value, new_value, version, changed_by, reason) "
                          "values (%s,%s,%s,%s,%s,%s)",
                          (k, Jsonb(current.model_dump().get(k)), Jsonb(v), row[0], actor, reason[:300]))
    _cache["cfg"] = None
    return get(force=True)
