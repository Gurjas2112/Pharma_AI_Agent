"""End-to-end smoke run of the graph (in-memory checkpointer + store)."""
import sys
import time

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

from repurpora.graph import build_graph
from repurpora.observability import UsageCallback

q = sys.argv[1] if len(sys.argv) > 1 else "Assess metformin repurposing opportunities in India: unmet needs, trials, patents"
g = build_graph(InMemorySaver(), InMemoryStore())
cb = UsageCallback()
cfg = {"configurable": {"thread_id": "smoke-1", "user_id": "smoke-user"}, "callbacks": [cb], "recursion_limit": 40}
t0 = time.time()
for ev in g.stream({"messages": [("user", q)]}, cfg, stream_mode="updates"):
    for node, upd in ev.items():
        print(f"[{time.time()-t0:6.1f}s] {node}: {', '.join((upd or {}).keys())}")
st = g.get_state(cfg).values
print("\n=== FINAL MESSAGE ===\n", st["messages"][-1].content[:3500])
print("\njudge:", st.get("judge"), "\nscores:", {k: st['scores'].get(k) for k in ('decision','ml_probability','confidence')})
print("tokens:", cb.totals, "elapsed", round(time.time()-t0, 1))
