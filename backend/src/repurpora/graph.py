"""LangGraph assembly - the ``repurpora`` assistant served by Aegra.

    START -> compact -> guard_input ─(blocked)→ END
                          └→ memory_load -> planner ─(chit-chat)→ END
                                               ├─(follow-up)→ follow_up -> END
                                               └─ Send × N → worker ─→ evidence_merge -> scorer
                                                    -> synthesizer <-> judge (≤1 redraft)
                                                    -> report -> finalize -> memory_write -> END
"""

from __future__ import annotations

import logging

from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy

from repurpora.nodes import core
from repurpora.state import ResearchState

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

_retry = RetryPolicy(max_attempts=2, initial_interval=1.0)


def build_graph(checkpointer=None, store=None):
    g = StateGraph(ResearchState)
    g.add_node("compact", core.maybe_compact)
    g.add_node("guard_input", core.guard_input)
    g.add_node("memory_load", core.memory_load)
    g.add_node("planner", core.planner, retry_policy=_retry)
    g.add_node("worker", core.worker, retry_policy=_retry)
    g.add_node("evidence_merge", core.evidence_merge)
    g.add_node("scorer", core.scorer)
    g.add_node("synthesizer", core.synthesizer, retry_policy=_retry)
    g.add_node("judge", core.judge)
    g.add_node("report", core.report)
    g.add_node("finalize", core.finalize)
    g.add_node("memory_write", core.memory_write)
    g.add_node("follow_up", core.follow_up)

    g.add_edge(START, "compact")
    g.add_edge("compact", "guard_input")
    g.add_edge("memory_load", "planner")
    g.add_edge("worker", "evidence_merge")
    g.add_edge("evidence_merge", "scorer")
    g.add_edge("scorer", "synthesizer")
    g.add_edge("synthesizer", "judge")
    g.add_edge("report", "finalize")
    g.add_edge("finalize", "memory_write")
    g.add_edge("memory_write", END)
    g.add_edge("follow_up", END)
    return g.compile(checkpointer=checkpointer, store=store, name="repurpora")


# Aegra / LangGraph server entrypoint (server injects Postgres checkpointer + store)
from repurpora.observability import UsageCallback  # noqa: E402

graph = build_graph().with_config({"callbacks": [UsageCallback()], "recursion_limit": 40})
