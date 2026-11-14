"""Graph state + structured schemas shared across nodes."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field
from typing_extensions import TypedDict

from repurpora.evidence import Evidence

WorkerName = Literal["iqvia", "exim", "patent", "clinical_trials", "internal", "web"]
ALL_WORKERS: list[str] = ["iqvia", "exim", "patent", "clinical_trials", "internal", "web"]


RESET = {"__reset__": True}


def resettable(old: list | None, new: list | None) -> list:
    """List reducer that appends, unless the update starts with the RESET marker."""
    old, new = old or [], new or []
    if new and isinstance(new[0], dict) and new[0].get("__reset__"):
        return list(new[1:])
    return old + new


class ResearchPlan(BaseModel):
    """Master agent's decomposition of the user query (structured output)."""

    intent: Literal["research", "archive_query", "chit_chat", "follow_up", "out_of_scope"] = Field(
        description="research = needs data agents; archive_query = question about the user's own saved "
                    "reports/sessions/usage; follow_up = answer from prior report; chit_chat = greeting/help"
    )
    molecule: str | None = Field(default=None, description="Primary molecule (INN, lowercase) if any")
    indication: str | None = Field(default=None, description="Target disease/indication if stated")
    therapy_area: str | None = Field(default=None, description="e.g. Respiratory, Metabolic")
    region: str | None = Field(default=None, description="Market/geography named by the user, else null")
    angle: str | None = Field(default=None, description="new indication | dosage form | patient population")
    workers: list[WorkerName] = Field(default_factory=list, description="Worker agents to run")
    sub_queries: dict[str, str] = Field(default_factory=dict, description="worker -> focused sub-question")
    want_report: bool = Field(default=True, description="Generate a PDF report")


class Table(BaseModel):
    title: str
    columns: list[str]
    rows: list[list[Any]]
    evidence_ids: list[str] = Field(default_factory=list)


class WorkerResult(BaseModel):
    agent: str
    summary: str = ""
    tables: list[Table] = Field(default_factory=list)
    charts: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    latency_ms: int = 0


class ResearchState(TypedDict, total=False):
    messages: Annotated[list[AnyMessage], add_messages]
    # control
    guard: dict[str, Any]
    plan: dict[str, Any]
    step_log: Annotated[list, resettable]
    # worker fan-in (reducer concatenates parallel results)
    results: Annotated[list[dict[str, Any]], resettable]
    evidence: list[dict[str, Any]]
    scores: dict[str, Any]
    draft: str
    judge: dict[str, Any]
    redrafts: int
    report: dict[str, Any]
    memory: dict[str, Any]
    summary: str  # compacted conversation summary


class WorkerTask(TypedDict):
    agent: str
    plan: dict[str, Any]
    query: str
