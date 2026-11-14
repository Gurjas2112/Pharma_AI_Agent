"""Domain worker agents.

Each worker:
 1. asks the policy gateway before every tool call (allow-list + budget),
 2. fetches data (mock / live) and computes domain analytics in pandas,
 3. emits typed tables, chart specs and provenance-tagged ``Evidence``,
 4. writes a short analyst note with the *fast* model (citing evidence ids).

Analytics thresholds are carried over from the original system (FTO bands,
trial saturation, sourcing concentration) so behaviour is comparable.
"""

from __future__ import annotations

import logging
import time
from collections import Counter
from collections.abc import Callable
from typing import Any

import pandas as pd
from langchain_core.messages import HumanMessage, SystemMessage

from repurpora.evidence import Evidence
from repurpora.guardrails.checks import authorize_tool, sanitize_untrusted
from repurpora.mock_apis.data import YEAR
from repurpora.state import Table, WorkerResult
from repurpora.tools import sources

log = logging.getLogger(__name__)


class ToolBudget:
    def __init__(self, agent: str):
        self.agent, self.calls = agent, 0

    def call(self, tool: str, fn: Callable, *a, **kw):
        ok, why = authorize_tool(self.agent, tool, self.calls)
        if not ok:
            raise PermissionError(why)
        self.calls += 1
        return fn(*a, **kw)


def _tbl(title: str, df: pd.DataFrame, ev_ids: list[str] | None = None, limit: int = 12) -> Table:
    df = df.head(limit)
    return Table(title=title, columns=[str(c) for c in df.columns],
                 rows=df.astype(object).where(pd.notna(df), None).values.tolist(),
                 evidence_ids=ev_ids or [])


# ----------------------------------------------------------------- IQVIA ----

def run_iqvia(plan: dict[str, Any], tb: ToolBudget) -> WorkerResult:
    mol, ta, region = plan.get("molecule"), plan.get("therapy_area"), plan.get("region") or "India"
    raw = tb.call("iqvia_market", sources.iqvia_market, mol, ta if not mol else None, region)
    df = pd.DataFrame(raw["therapy_dynamics"])
    res = WorkerResult(agent="iqvia")
    if df.empty:
        res.error = "no market rows"
        return res
    prof = sources.molecule_profile(mol) if mol else None
    approved = {a.lower() for a in (prof or {}).get("approved", [])}
    df["new_indication"] = ~df.disease.str.lower().isin(approved)
    df = df.sort_values(["new_indication", "burden_to_competition"], ascending=[False, False])
    ev = Evidence(agent="iqvia", source=raw["source"], trust="licensed_db",
                  title=f"Market dynamics ({region})",
                  snippet="; ".join(f"{r.disease}: ${r.market_usd_mn}M, CAGR {r.cagr_5y_pct}%, "
                                    f"{r.competitors} competitors, {r.patients_mn}M patients"
                                    for r in df.head(6).itertuples()))
    res.evidence.append(ev)
    res.tables.append(_tbl("Market size & competition", df[[
        "disease", "therapy_area", "patients_mn", "market_usd_mn", "cagr_5y_pct", "competitors",
        "generic_share", "burden_to_competition"]], ["iqvia"]))
    res.charts.append({"kind": "bar", "title": f"Market size by indication ({region}, USD mn)",
                       "x": df["disease"].tolist()[:8], "y": df["market_usd_mn"].tolist()[:8]})
    if raw.get("molecule_sales"):
        sales = pd.DataFrame(raw["molecule_sales"])
        cagr = (sales.sales_usd_mn.iloc[-1] / sales.sales_usd_mn.iloc[0]) ** (1 / (len(sales) - 1)) - 1
        res.metrics["molecule_sales_cagr_pct"] = round(cagr * 100, 1)
        res.metrics["molecule_sales_latest_usd_mn"] = float(sales.sales_usd_mn.iloc[-1])
        res.tables.append(_tbl(f"{(mol or '').title()} sales trend", sales, ["iqvia"]))
        res.charts.append({"kind": "line", "title": f"{(mol or '').title()} sales (USD mn)",
                           "x": sales.year.tolist(), "y": sales.sales_usd_mn.tolist()})
        res.evidence.append(Evidence(agent="iqvia", source=raw["source"], trust="licensed_db",
                                     title=f"{mol} sales trend",
                                     snippet=f"Sales grew to ${sales.sales_usd_mn.iloc[-1]}M in {sales.year.iloc[-1]} "
                                             f"(5y CAGR {cagr * 100:.1f}%)."))
    if prof:
        for cand, unmet, note in prof.get("candidates", []):
            res.evidence.append(Evidence(agent="iqvia", source="Repurposing analyst profile (synthetic)",
                                         trust="synthetic", title=f"Candidate: {cand}",
                                         snippet=f"Unmet-need score {unmet:.2f}. {note}. MoA: {prof.get('moa')}."))
        if prof.get("innovation"):
            res.evidence.append(Evidence(agent="iqvia", source="Repurposing analyst profile (synthetic)",
                                         trust="synthetic", title="Innovation hypothesis",
                                         snippet=f"{prof['innovation']}. Current forms: {', '.join(prof.get('forms', []))}."))
    newdf = df[df.new_indication]
    top = (newdf if not newdf.empty else df).iloc[0]
    res.metrics.update({
        "top_market_usd_mn": float(df.market_usd_mn.max()),
        "best_opportunity": top.disease,
        "best_cagr_pct": float(top.cagr_5y_pct),
        "best_competitors": int(top.competitors),
        "best_patients_mn": float(top.patients_mn),
        "best_market_usd_mn": float(top.market_usd_mn),
    })
    low_comp = df[(df.competitors <= 6) & (df.patients_mn >= 0.5)]
    if not low_comp.empty:
        res.flags.append("Low-competition / high-burden pockets: " + ", ".join(low_comp.disease.head(4)))
    return res


# ------------------------------------------------------------------ EXIM ----

def run_exim(plan: dict[str, Any], tb: ToolBudget) -> WorkerResult:
    mol = plan.get("molecule") or "metformin"
    region = plan.get("region") or "India"
    raw = tb.call("exim_trade", sources.exim_trade, mol, region)
    res = WorkerResult(agent="exim")
    partners = pd.DataFrame(raw["api_import_partners"])
    trend = pd.DataFrame(raw["trend"])
    top = partners.iloc[0]
    hhi = float((partners.share ** 2).sum())
    risk = "High" if top.share > 0.6 else "Medium" if top.share > 0.4 else "Low"
    dependency = partners[partners.share > 0.3].partner.tolist()
    res.metrics.update({"top_supplier": top.partner, "top_supplier_share": float(top.share),
                        "supplier_hhi": round(hhi, 3), "sourcing_risk": risk,
                        "import_growth_pct": round((trend.imports_tonnes.iloc[-1] / trend.imports_tonnes.iloc[0] - 1) * 100, 1)})
    res.evidence.append(Evidence(agent="exim", source=raw["source"], trust="licensed_db",
                                 title=f"{mol} API import partners ({region})",
                                 snippet=f"Top supplier {top.partner} at {top.share:.0%} share; HHI {hhi:.2f}; "
                                         f"sourcing concentration risk {risk}."))
    res.tables.append(_tbl("API import dependency", partners, ["exim"]))
    res.tables.append(_tbl("Trade volume trend (tonnes)", trend, ["exim"]))
    res.charts.append({"kind": "line2", "title": f"{mol.title()} API trade volume ({region}, tonnes)",
                       "x": trend.year.tolist(), "y": trend.imports_tonnes.tolist(),
                       "y2": trend.exports_tonnes.tolist(), "labels": ["Imports", "Exports"]})
    if dependency:
        res.flags.append(f"Import dependency >30% on: {', '.join(dependency)}")
    return res


# ---------------------------------------------------------------- Patent ----

def _fto(active: pd.DataFrame) -> tuple[int, str]:
    score = 0
    for r in active.itertuples():
        w = {"Composition of matter": 4, "Method of use": 3, "Formulation": 2, "Dosage regimen": 2,
             "Polymorph": 1, "Process": 1}.get(r.type, 1)
        w *= {"Broad": 1.5, "Moderate": 1.0, "Narrow": 0.6}.get(r.claims_scope, 1)
        score += w
    score = min(10, round(score))
    band = "Low" if score <= 3 else "Medium" if score <= 7 else "High"
    return score, band


def run_patent(plan: dict[str, Any], tb: ToolBudget) -> WorkerResult:
    mol = plan.get("molecule") or "metformin"
    raw = tb.call("uspto_patents", sources.uspto_patents, mol, plan.get("indication"))
    df = pd.DataFrame(raw["patents"])
    res = WorkerResult(agent="patent")
    active = df[df.status == "Active"]
    score, band = _fto(active)
    expiring = active[active.expiry_year <= YEAR + 3]
    assignees = Counter(df.assignee).most_common(3)
    res.metrics.update({"fto_risk_score": score, "fto_band": band, "active_patents": int(len(active)),
                        "expiring_within_3y": int(len(expiring)),
                        "latest_expiry": int(active.expiry_year.max()) if len(active) else None})
    rec = {"Low": "Freedom-to-operate appears favourable; proceed to formulation design-around review.",
           "Medium": "Design-around on formulation/method-of-use claims advised; seek IP counsel opinion.",
           "High": "Significant blocking IP; consider licensing or wait for expiry."}[band]
    res.evidence.append(Evidence(agent="patent", source=raw["source"], trust="registry",
                                 title=f"{mol} patent landscape",
                                 snippet=f"{len(active)} active of {len(df)} filings; FTO risk {score}/10 ({band}); "
                                         f"{len(expiring)} expire by {YEAR + 3}. Top assignees: "
                                         + ", ".join(f"{a} ({n})" for a, n in assignees)))
    res.tables.append(_tbl("Patent status", df[["patent_no", "type", "assignee", "filing_year",
                                                  "expiry_year", "status", "claims_scope"]], ["patent"]))
    heat = df.pivot_table(index="assignee", columns="type", values="patent_no", aggfunc="count", fill_value=0)
    res.charts.append({"kind": "heatmap", "title": "Competitive filing heatmap (assignee × claim type)",
                       "rows": heat.index.tolist(), "cols": heat.columns.tolist(), "values": heat.values.tolist()})
    res.flags.append(f"FTO {band} ({score}/10): {rec}")
    return res


# ------------------------------------------------------- Clinical trials ----

def run_trials(plan: dict[str, Any], tb: ToolBudget) -> WorkerResult:
    mol = plan.get("molecule") or "metformin"
    raw = tb.call("clinical_trials", sources.clinical_trials, mol, plan.get("indication"))
    df = pd.DataFrame(raw["trials"])
    res = WorkerResult(agent="clinical_trials")
    if df.empty:
        res.error = "no trials found"
        return res
    active = df[df.status.isin(["RECRUITING", "ACTIVE_NOT_RECRUITING", "NOT_YET_RECRUITING", "ENROLLING_BY_INVITATION"])]
    n_active = len(active)
    sat = "High" if n_active > 20 else "Medium" if n_active > 10 else "Low"
    phases = df.phase.fillna("NA").value_counts().to_dict()
    conds = df.condition.fillna("").str.split(",").str[0].str.strip()
    indications = conds[conds != ""].value_counts()
    sponsors = df.sponsor.fillna("Unknown").value_counts().head(5)
    res.metrics.update({"total_trials": int(len(df)), "active_trials": n_active, "trial_saturation": sat,
                        "distinct_indications": int(indications.size), "live_source": raw.get("_transport") == "live"})
    url = "https://clinicaltrials.gov/search?intr=" + mol if raw.get("_transport") == "live" else None
    res.evidence.append(Evidence(agent="clinical_trials", source=raw["source"],
                                 trust="registry" if url else "synthetic", url=url,
                                 title=f"{mol} trial pipeline",
                                 snippet=f"{len(df)} studies, {n_active} active (saturation {sat}); phases: "
                                         + ", ".join(f"{k}:{v}" for k, v in list(phases.items())[:5])
                                         + "; top conditions: " + ", ".join(indications.head(5).index)))
    for r in df.head(4).itertuples():
        if r.nct_id and not str(r.nct_id).startswith("NCT-MOCK"):
            res.evidence.append(Evidence(agent="clinical_trials", source=raw["source"], trust="registry",
                                         url=f"https://clinicaltrials.gov/study/{r.nct_id}",
                                         title=f"{r.nct_id}: {r.title}", snippet=f"{r.phase} · {r.status} · {r.sponsor}"))
    res.tables.append(_tbl("Active & recent trials", df[["nct_id", "condition", "phase", "status", "sponsor",
                                                        "enrollment"]], ["clinical_trials"]))
    res.tables.append(_tbl("Sponsor profile", sponsors.rename_axis("sponsor").reset_index(name="trials"),
                           ["clinical_trials"]))
    res.charts.append({"kind": "pie", "title": "Trial phase distribution",
                       "labels": list(phases.keys())[:7], "values": list(phases.values())[:7]})
    if indications.size >= 3:
        res.flags.append("Repurposing signal: trials span " + ", ".join(indications.head(4).index))
    return res


# -------------------------------------------------------- Internal (RAG) ----

def run_internal(plan: dict[str, Any], tb: ToolBudget, query: str) -> WorkerResult:
    from repurpora.rag.retriever import rag_search

    res = WorkerResult(agent="internal")
    q = query or f"{plan.get('molecule') or ''} {plan.get('indication') or ''} product selection strategy"
    hits = tb.call("rag_search", rag_search, q, 5)
    if not hits:
        res.error = "internal index empty or unavailable"
        return res
    for h in hits:
        res.evidence.append(Evidence(agent="internal", source=f"Internal KB: {h['source']}", trust="internal",
                                     title=f"{h['source']} (p.{h.get('page', '?')})",
                                     snippet=sanitize_untrusted(h["content"][:600])))
    res.tables.append(Table(title="Internal document matches", columns=["document", "page", "score"],
                            rows=[[h["source"], h.get("page"), round(h.get("score", 0), 3)] for h in hits],
                            evidence_ids=["internal"]))
    res.metrics["internal_hits"] = len(hits)
    res.metrics["retrieval_mode"] = hits[0].get("mode", "hybrid")
    return res


# -------------------------------------------------------------------- Web ----

def run_web(plan: dict[str, Any], tb: ToolBudget, query: str) -> WorkerResult:
    mol = plan.get("molecule") or ""
    q = query or f"{mol} repurposing {plan.get('indication') or 'new indication'} guideline evidence"
    raw = tb.call("web_search", sources.web_search, q, 5)
    res = WorkerResult(agent="web")
    for it in raw["results"]:
        trust = "web" if raw.get("_transport") == "live" else "synthetic"
        res.evidence.append(Evidence(agent="web", source=raw["source"], trust=trust, url=it.get("url"),
                                     title=it.get("title", "")[:160],
                                     snippet=sanitize_untrusted(it.get("snippet", ""))))
    res.tables.append(Table(title="Web intelligence", columns=["title", "url"],
                            rows=[[it.get("title", "")[:90], it.get("url")] for it in raw["results"]],
                            evidence_ids=["web"]))
    res.metrics["web_results"] = len(raw["results"])
    res.metrics["live_source"] = raw.get("_transport") == "live"
    return res


RUNNERS = {"iqvia": run_iqvia, "exim": run_exim, "patent": run_patent, "clinical_trials": run_trials}
QUERY_RUNNERS = {"internal": run_internal, "web": run_web}

NOTE_PROMPT = (
    "You are the {agent} analyst in a pharma repurposing team. Write 2-3 crisp bullet points "
    "interpreting the data below for a portfolio planner. Only use facts present in the data; "
    "do not invent numbers. No preamble."
)


def run_worker(agent: str, plan: dict[str, Any], query: str = "", with_note: bool = True) -> WorkerResult:
    t0 = time.perf_counter()
    tb = ToolBudget(agent)
    try:
        if agent in RUNNERS:
            res = RUNNERS[agent](plan, tb)
        elif agent in QUERY_RUNNERS:
            res = QUERY_RUNNERS[agent](plan, tb, query)
        else:
            res = WorkerResult(agent=agent, error=f"unknown agent {agent}")
    except PermissionError as exc:
        res = WorkerResult(agent=agent, error=f"policy denied: {exc}")
    except Exception as exc:  # isolate worker failures (fault tolerance)
        log.exception("worker %s failed", agent)
        res = WorkerResult(agent=agent, error=f"{type(exc).__name__}: {exc}"[:300])
    if with_note and not res.error and res.evidence:
        res.summary = _note(agent, res)
    elif not res.summary:
        res.summary = "; ".join(res.flags) or (res.error or "")
    res.latency_ms = int((time.perf_counter() - t0) * 1000)
    return res


def _note(agent: str, res: WorkerResult) -> str:
    from repurpora.llm import get_llm

    digest = "\n".join(f"- {e.title}: {e.snippet[:400]}" for e in res.evidence[:5])
    digest += "\nMetrics: " + ", ".join(f"{k}={v}" for k, v in res.metrics.items())
    if res.flags:
        digest += "\nFlags: " + " | ".join(res.flags)
    try:
        msg = get_llm("fast").invoke(
            [SystemMessage(NOTE_PROMPT.format(agent=agent)), HumanMessage(digest)],
            config={"run_name": f"{agent}_note", "tags": [f"agent:{agent}"]},
        )
        return str(msg.content).strip()
    except Exception as exc:
        log.warning("note generation failed for %s: %s", agent, exc)
        return "; ".join(res.flags) or digest[:400]
