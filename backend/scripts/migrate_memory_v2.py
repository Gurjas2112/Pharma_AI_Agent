"""One-off migration: re-render legacy (v1) memory facts into the v2 format.

v1 facts could read "Evaluated colchicine for None in global ..." and lacked updated_at/decision/history.
usage: uv run python scripts/migrate_memory_v2.py [--dry-run]
"""
import json
import re
import sys

from psycopg.types.json import Jsonb

from repurpora.db import conn
from repurpora.memory import _fmt_fact
from repurpora.regions import canonical

dry = "--dry-run" in sys.argv
with conn() as c:
    rows = c.execute("select prefix, key, value, updated_at from store where prefix like 'users.%.memories'").fetchall()
    n = 0
    for prefix, key, value, updated in rows:
        v = value if isinstance(value, dict) else json.loads(value)
        if v.get("updated_at"):
            continue  # already v2
        m = re.search(r": (\w+) \(ML p=([\d.]+)\)", v.get("fact", ""))
        ind = re.search(r" for (.+?) in ", v.get("fact", ""))
        indication = ind.group(1) if ind and ind.group(1) != "None" else None
        plan = {"molecule": v.get("molecule"), "indication": indication, "region": canonical(v.get("region"))}
        scores = {"decision": m.group(1) if m else None, "ml_probability": float(m.group(2)) if m else None}
        v.update({"fact": _fmt_fact(plan, scores), "region": plan["region"], "indication": indication,
                  "decision": scores["decision"], "ml_probability": scores["ml_probability"],
                  "updated_at": updated.isoformat(), "history": v.get("history", [])})
        print(("[dry] " if dry else "") + f"{prefix}/{key}: {v['fact']}")
        if not dry:
            c.execute("update store set value=%s where prefix=%s and key=%s", (Jsonb(v), prefix, key))
        n += 1
    print(f"migrated {n} legacy fact(s)")
