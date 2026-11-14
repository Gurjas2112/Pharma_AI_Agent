"""Graph nodes for the Master agent orchestration.

Flow (enforced in code - the LLM proposes, the state machine decides):
guard_input -> memory_load -> planner -> (Send x N) worker -> evidence_merge
 -> scorer -> synthesizer -> judge -(redraft <= 1)-> report -> finalize
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any, Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command, Send, interrupt

from repurpora.agents.workers import run_worker
from repurpora.evidence import (
    Evidence,
    attribute_citations,
    citation_accuracy,
    coverage,
    evidence_digest,
    number_evidence,
)
from repurpora.guardrails.checks import dlp_redact, scan_input
from repurpora.llm import get_llm
from repurpora.mock_apis.data import MOLECULES
from repurpora.observability import audit
from repurpora.settings import get_settings
from repurpora.state import ALL_WORKERS, RESET, ResearchPlan, ResearchState, WorkerTask

log = logging.getLogger(__name__)


def jsonable(obj: Any) -> Any:
    """Coerce numpy / pandas scalars into plain Python for checkpoint serialization."""
    def _default(o):
        if hasattr(o, "item"):
            return o.item()
        if hasattr(o, "tolist"):
            return o.tolist()
        return str(o)
    return json.loads(json.dumps(obj, default=_default))


def _cfg(config: RunnableConfig) -> tuple[str | None, str | None]:
    c = (config or {}).get("configurable", {})
    return c.get("thread_id"), c.get("user_id")


def _last_user_text(state: ResearchState) -> str:
    for m in reversed(state.get("messages", [])):
        if isinstance(m, HumanMessage) or getattr(m, "type", "") == "human":
            c = m.content
            if isinstance(c, list):
                c = " ".join(p.get("text", "") for p in c if isinstance(p, dict))
            return str(c)
    return ""


# ------------------------------------------------------------- guard_input --

def guard_input(state: ResearchState, config: RunnableConfig) -> Command[Literal["memory_load", "__end__"]]:
    thread, owner = _cfg(config)
    text = _last_user_text(state)
    g = scan_input(text, get_settings().max_input_chars)
    audit("guard_input", {"allowed": g.allowed, "risk": g.risk, "reasons": g.reasons}, thread, owner, prompt=text)
    if not g.allowed:
        reason = "; ".join(g.reasons) or "policy"
        msg = ("I can't help with that request. Repurpora is scoped to pharmaceutical portfolio research "
               f"(repurposing, markets, trials, patents, supply). _Guardrail: {reason}._")
        return Command(goto="__end__", update={"guard": {"allowed": False, "reasons": g.reasons},
                                               "messages": [AIMessage(msg)]})
    return Command(goto="memory_load", update={"guard": {"allowed": True, "risk": g.risk, "reasons": g.reasons},
                                               "results": [RESET], "redrafts": 0, "judge": {}, "report": {},
                                               "step_log": [RESET, "guard_input: pass"]})


# ------------------------------------------------------------- memory -------

def _store():
    try:
        from langgraph.config import get_store

        return get_store()
    except Exception:
        return None


def memory_load(state: ResearchState, config: RunnableConfig) -> dict:
    from repurpora import memory

    _, owner = _cfg(config)
    mem = memory.load(_store(), owner, _last_user_text(state))
    return {"memory": jsonable(mem), "step_log": [f"memory_load: {len(mem['facts'])} facts"]}


def memory_write(state: ResearchState, config: RunnableConfig) -> dict:
    from repurpora import memory

    thread, owner = _cfg(config)
    ok = memory.write_research(_store(), owner, thread, state.get("plan") or {}, state.get("scores") or {},
                               state.get("report") or {})
    if ok:
        audit("memory_write", {"molecule": (state.get("plan") or {}).get("molecule")}, thread, owner)
    return {}


# ------------------------------------------------------------- planner ------

PLANNER_SYS = """You are the Master Agent of Repurpora, a pharmaceutical drug-repurposing research copilot
for a generic-pharma portfolio team. Decompose the user's request into a research plan.

Worker agents available:
- iqvia: market size, growth/CAGR, competition, patient burden by therapy area/indication
- exim: API/formulation import-export volumes, sourcing concentration, import dependency
- patent: USPTO-style patent filings, expiry timelines, freedom-to-operate (FTO) risk
- clinical_trials: ongoing trials, phases, sponsors (ClinicalTrials.gov)
- internal: internal strategy docs / research papers (RAG over company knowledge base)
- web: guidelines, publications, news, patient forums

Rules:
- intent=research for any analytical pharma question; select the workers that are actually needed
  (a full molecule repurposing assessment uses all six).
- Questions about a disease area without a molecule (e.g. "which respiratory diseases have low competition")
  need iqvia + web (+ internal), and set therapy_area.
- intent=follow_up if the user asks about the previous answer/report; intent=chit_chat for greetings/help.
- molecule must be a lowercase INN generic name (translate brand names to the generic) or null.
- region: one of India, US, EU, UK, China, Japan, Brazil, Africa, Southeast Asia, Middle East, Global.
  Use the region the user names; otherwise the user's usual region from memory; otherwise {default_region}.
- The user may write in any language; plan in English.
- Provide a focused sub_query for internal and web workers.
Context from memory and prior conversation:
{context}
Respond ONLY with JSON matching the schema."""


_KNOWN_AREAS = ["respiratory", "metabolic", "cardiovascular", "oncology", "cns", "dermatology", "renal",
                "gastro", "anti-infective", "women's health"]


def heuristic_plan(text: str) -> ResearchPlan:
    t = text.lower()
    mol = next((m for m in MOLECULES if m in t), None)
    if not mol and (m := re.search(r"\b([a-z]{5,}(?:mab|nib|pril|sartan|statin|olol|mide|azole|cycline|formin|lukast|afil|sone|ine))\b", t)):
        mol = m.group(1)
    area = next((a.title() for a in _KNOWN_AREAS if a in t), None)
    from repurpora.regions import detect

    region = detect(text)  # None -> planner applies the user's learned region or the configured default
    if re.fullmatch(r"\s*(hi|hello|hey|help|thanks|thank you)[!. ]*", t):
        return ResearchPlan(intent="chit_chat")
    workers = ALL_WORKERS if mol else ["iqvia", "web", "internal"]
    return ResearchPlan(intent="research", molecule=mol, therapy_area=area if not mol else None, region=region,
                        workers=workers, sub_queries={"web": text[:200], "internal": text[:200]})


def planner(state: ResearchState, config: RunnableConfig) -> Command[Literal["worker", "follow_up", "__end__"]]:
    thread, owner = _cfg(config)
    text = _last_user_text(state)
    from repurpora import memory, regions

    mem_state = state.get("memory") or {}
    prior = state.get("plan") or {}
    # user control over long-term memory (handled deterministically, never by the LLM)
    if memory.FORGET_RE.search(text):
        n = memory.forget(_store(), owner)
        audit("memory_forget", {"deleted": n}, thread, owner)
        return Command(goto="__end__", update={"messages": [AIMessage(
            f"🧹 Done - I erased {n} saved memory item(s). Your past threads remain in history until you delete them.")]})
    if memory.SHOW_RE.search(text):
        return Command(goto="__end__", update={"messages": [AIMessage(memory.render_for_user(_store(), owner))]})
    preferred = (mem_state.get("profile") or {}).get("preferred_region")
    default_region = preferred or get_settings().default_region
    ctx = []
    if state.get("summary"):
        ctx.append("Conversation summary: " + state["summary"])
    if prior:
        ctx.append(f"Previous plan: molecule={prior.get('molecule')}, indication={prior.get('indication')}, "
                   f"region={prior.get('region')}")
    ctx += memory.context_lines(mem_state)
    plan: ResearchPlan
    try:
        llm = get_llm("primary").with_structured_output(ResearchPlan, method="json_schema")
        plan = llm.invoke([SystemMessage(PLANNER_SYS.format(context="\n".join(ctx) or "none")), HumanMessage(text)],
                          config={"run_name": "master_planner"})
        if plan.intent == "research" and not plan.workers:
            plan.workers = heuristic_plan(text).workers
    except Exception as exc:
        log.warning("structured planning failed (%s) -> heuristic planner", exc)
        plan = heuristic_plan(text)
    # deterministic post-validation (state machine owns the rules)
    explicit = regions.detect(text)
    plan.region = explicit or (regions.canonical(plan.region, default_region) if plan.region else default_region)
    if not explicit and prior.get("region") and plan.intent == "research":
        plan.region = prior["region"]  # follow-ups stay in the same market
    region_explicit = explicit is not None
    if plan.molecule:
        plan.molecule = plan.molecule.strip().lower()
    if plan.intent == "research" and not plan.molecule and prior.get("molecule") and \
            re.search(r"\b(it|this|that|same|the molecule)\b", text.lower()):
        plan.molecule = prior["molecule"]
    plan.workers = [w for w in dict.fromkeys(plan.workers) if w in ALL_WORKERS][: get_settings().max_workers_per_query]
    if plan.intent == "research" and plan.molecule:
        # routing floor: a molecule assessment always needs market, IP and clinical context
        for core_w in ("iqvia", "patent", "clinical_trials"):
            if core_w not in plan.workers:
                plan.workers.append(core_w)
    if plan.intent == "research" and not plan.molecule:
        plan.workers = [w for w in plan.workers if w not in ("exim", "patent", "clinical_trials")] or ["iqvia", "web"]
    audit("plan", plan.model_dump(), thread, owner)
    pd_ = {**plan.model_dump(), "region_explicit": region_explicit}

    if plan.intent in ("chit_chat", "out_of_scope"):
        return Command(goto="__end__", update={"messages": [AIMessage(_HELP)], "plan": pd_})
    if plan.intent == "follow_up" and state.get("draft"):
        return Command(goto="follow_up", update={"plan": {**prior, "followup": True}})

    label = {"iqvia": "IQVIA Insights", "exim": "EXIM Trends", "patent": "Patent Landscape",
             "clinical_trials": "Clinical Trials", "internal": "Internal Knowledge", "web": "Web Intelligence"}
    subject = (plan.molecule or plan.therapy_area or "the portfolio question").title()
    note = (f"🧭 **Research plan** for **{subject}** ({plan.region}"
            f"{', ' + plan.indication if plan.indication else ''}) → dispatching "
            + ", ".join(f"`{label[w]}`" for w in plan.workers) + " in parallel…")
    sends = [Send("worker", WorkerTask(agent=w, plan=pd_, query=plan.sub_queries.get(w, text))) for w in plan.workers]
    return Command(goto=sends, update={"plan": pd_, "messages": [AIMessage(note)],
                                       "step_log": [f"planner: {plan.workers}"]})


_HELP = """👋 I'm **Repurpora**, your drug-repurposing research copilot.

Ask me things like:
- *"Assess metformin repurposing opportunities in India — unmet needs, trials, patents."*
- *"Which respiratory diseases show low competition but high patient burden in India?"*
- *"Check the patent landscape and FTO risk for colchicine in cardiovascular prevention."*
- *"Is there an innovative dosage-form opportunity for budesonide?"*

I coordinate six specialist agents (IQVIA, EXIM, Patents, Clinical Trials, Internal Knowledge, Web),
score the opportunity with an ML model, and archive a cited PDF/Excel report."""


# ------------------------------------------------------------- worker -------

def worker(task: WorkerTask, config: RunnableConfig) -> dict:
    thread, owner = _cfg(config)
    res = run_worker(task["agent"], task["plan"], task.get("query", ""))
    audit("tool_call", {"agent": res.agent, "error": res.error, "latency_ms": res.latency_ms,
                        "n_evidence": len(res.evidence)}, thread, owner)
    return {"results": [jsonable(res.model_dump())], "step_log": [f"worker {res.agent}: {'ok' if not res.error else res.error}"]}


# ------------------------------------------------------------- evidence -----

def evidence_merge(state: ResearchState) -> dict:
    ev = [Evidence(**e) for r in state.get("results", []) for e in r.get("evidence", [])]
    numbered = number_evidence(ev)
    by_agent: dict[str, list[str]] = {}
    for e in numbered:
        by_agent.setdefault(e.agent, []).append(e.id)
    results = []
    for r in state.get("results", []):
        r = dict(r)
        r["tables"] = [{**t, "evidence_ids": by_agent.get(r["agent"], [])} for t in r.get("tables", [])]
        results.append(r)
    return {"evidence": [e.model_dump() for e in numbered], "step_log": [f"evidence_merge: {len(numbered)} items"]}


# ------------------------------------------------------------- scorer -------

THRESH = {"market_usd_mn": 50, "cagr_pct": 3, "fto_max": 7, "trials_max": 15}


def scorer(state: ResearchState) -> dict:
    from repurpora.ml.opportunity_scorer import features_from_results, predict

    plan = state.get("plan") or {}
    metrics: dict[str, Any] = {}
    for r in state.get("results", []):
        metrics.update(r.get("metrics", {}))
    checks = {}
    mkt = metrics.get("best_market_usd_mn") or metrics.get("top_market_usd_mn")
    cagr = metrics.get("best_cagr_pct") or metrics.get("molecule_sales_cagr_pct")
    if mkt is not None:
        checks["market"] = mkt >= THRESH["market_usd_mn"] and (cagr or 0) >= THRESH["cagr_pct"]
    if metrics.get("fto_risk_score") is not None:
        checks["ip"] = metrics["fto_risk_score"] <= THRESH["fto_max"]
    if metrics.get("active_trials") is not None:
        checks["clinical_space"] = metrics["active_trials"] <= THRESH["trials_max"]
    passed = sum(checks.values())
    if checks and passed == len(checks):
        decision, conf = "GO", 85
    elif checks.get("market") and checks.get("ip", True):
        decision, conf = "PARTIAL_GO", 65
    elif not checks:
        decision, conf = "INSIGHT", 60
    else:
        decision, conf = "NO_GO", 40
    # unmet need + evidence strength from curated profile / evidence mix
    from repurpora.tools.sources import molecule_profile as enriched_profile

    prof = enriched_profile(plan["molecule"]) if plan.get("molecule") else None
    unmet = 0.6
    target = plan.get("indication") or metrics.get("best_opportunity")
    if prof:
        cands = {c[0].lower(): c[1] for c in prof["candidates"]}
        unmet = next((v for k, v in cands.items() if target and (k in target.lower() or target.lower() in k)),
                     max(cands.values()) if cands else 0.6)
    ev = state.get("evidence", [])
    strong = sum(1 for e in ev if e["trust"] in ("registry", "regulatory", "internal", "licensed_db"))
    strength = min(1.0, 0.25 + strong / max(len(ev), 1) * 0.6 + (0.15 if metrics.get("live_source") else 0))
    reform = bool(plan.get("angle") and "dosage" in plan["angle"].lower()) or bool(prof and prof.get("curated"))
    scores: dict[str, Any] = {"decision": decision, "confidence": conf, "checks": checks, "metrics": metrics,
                              "unmet_need": round(unmet, 2), "evidence_strength": round(strength, 2),
                              "best_opportunity": target}
    try:
        ml = predict(features_from_results(metrics, unmet, strength, reform))
        scores.update({"ml_probability": ml["probability"], "ml_model": ml["model"], "ml_auc": ml["test_roc_auc"],
                       "ml_drivers": ml["drivers"]})
    except Exception as exc:
        log.warning("ml scorer failed: %s", exc)
        scores.update({"ml_probability": 0.0, "ml_model": "unavailable"})
    if prof:
        scores["innovation_hint"] = prof.get("innovation")
        scores["candidates"] = [{"indication": c[0], "unmet_need": c[1], "note": c[2]} for c in prof["candidates"]]
    return {"scores": jsonable(scores), "step_log": [f"scorer: {decision} p={scores.get('ml_probability')}"]}


# ------------------------------------------------------------- synthesizer --

SYNTH_SYS = """You are the Master Agent writing the final innovation brief for a pharma portfolio planner.
Use ONLY the evidence register and worker notes provided. Never invent numbers, trials, patents or sources.
CITATION RULE: every sentence or bullet that states a fact MUST end with evidence ids in square brackets,
e.g. "Montelukast faces 46 competitors in asthma [E1]." or "- FTO risk is Low (2/10) [E4][E5]".
Use only ids that appear in the EVIDENCE REGISTER. Synthetic/mock sources must not be called real-world facts.

Write GitHub markdown with EXACTLY these sections, in this order, and no others:
{sections}
Keep it under {words} words. Be specific and quantitative.
Write the brief in the same language as the user's question (section headings may stay in English)."""

SECTION_SPEC = {
    "summary": "## Executive summary  (2-3 sentences: decision, ML probability, best opportunity)",
    "unmet": "## Unmet need & opportunity",
    "iqvia": "## Market dynamics",
    "clinical_trials": "## Clinical trial landscape",
    "patent": "## Patent & FTO",
    "exim": "## Supply chain (EXIM)",
    "internal": "## Internal knowledge insights",
    "web": "## Guidelines & publications",
    "story": "## Innovative product story  (concrete proposal: new indication / dosage form / population; cite the "
             "innovation-hypothesis or candidate evidence plus supporting evidence)",
    "risks": "## Risks & next steps  (3 bullets)",
}


def _sections_for(state: ResearchState) -> str:
    ran = {r["agent"] for r in state.get("results", []) if not r.get("error")}
    plan = state.get("plan") or {}
    keys = ["summary"]
    if "iqvia" in ran or plan.get("molecule"):
        keys.append("unmet")
    keys += [k for k in ("iqvia", "clinical_trials", "patent", "exim", "internal", "web") if k in ran]
    if plan.get("molecule"):
        keys.append("story")
    keys.append("risks")
    return "\n".join(SECTION_SPEC[k] for k in keys)


def _compact_context(state: ResearchState) -> str:
    """Context engineering: compact digest within a token budget (~4 chars/token)."""
    budget_chars = get_settings().context_token_budget * 4
    parts = []
    sc = state.get("scores", {})
    parts.append(f"DECISION: {sc.get('decision')} (rule confidence {sc.get('confidence')}%), "
                 f"ML success probability {sc.get('ml_probability')} via {sc.get('ml_model')}; checks={sc.get('checks')}; "
                 f"unmet_need={sc.get('unmet_need')}; best_opportunity={sc.get('best_opportunity')}")
    if sc.get("candidates"):
        parts.append("CANDIDATE INDICATIONS (synthetic analyst profile): " +
                     "; ".join(f"{c['indication']} (unmet {c['unmet_need']}): {c['note']}" for c in sc["candidates"]))
    if sc.get("innovation_hint"):
        parts.append(f"INNOVATION HINT: {sc['innovation_hint']}")
    for r in state.get("results", []):
        if r.get("summary"):
            parts.append(f"{r['agent'].upper()} NOTE: {r['summary'][:600]}")
        if r.get("flags"):
            parts.append(f"{r['agent'].upper()} FLAGS: {' | '.join(r['flags'])}")
    ev = [Evidence(**e) for e in state.get("evidence", [])]
    head = "\n".join(parts)
    reg = evidence_digest(ev, max_chars=260)
    if len(head) + len(reg) > budget_chars:
        reg = evidence_digest(ev, max_chars=140)[: max(1000, budget_chars - len(head))]
    return head + "\n\nEVIDENCE REGISTER:\n" + reg


def synthesizer(state: ResearchState, config: RunnableConfig) -> dict:
    ctx = _compact_context(state)
    judge = state.get("judge") or {}
    n_ran = len([r for r in state.get("results", []) if not r.get("error")])
    system = SYNTH_SYS.format(sections=_sections_for(state), words=220 + 45 * n_ran)
    msgs = [SystemMessage(system), HumanMessage(f"User question: {_last_user_text(state)}\n\n{ctx}")]
    if judge.get("uncited"):
        msgs.append(HumanMessage("Revise: these claims lacked valid citations or were unsupported - fix or remove "
                                 "them:\n- " + "\n- ".join(judge["uncited"][:8])))
        msgs.insert(2, AIMessage(state.get("draft", "")))
    try:
        draft = str(get_llm("primary").invoke(msgs, config={"run_name": "synthesizer"}).content)
    except Exception as exc:
        log.error("synthesizer LLM failed: %s", exc)
        draft = _fallback_synthesis(state)
    return {"draft": draft, "redrafts": state.get("redrafts", 0) + (1 if judge else 0),
            "step_log": ["synthesizer: drafted"]}


def _fallback_synthesis(state: ResearchState) -> str:
    sc = state.get("scores", {})
    ev = state.get("evidence", [])
    lines = ["## Executive summary",
             f"Decision **{sc.get('decision')}** with ML success probability {sc.get('ml_probability')} "
             f"(LLM unavailable - deterministic summary) [{ev[0]['id'] if ev else 'E1'}]."]
    for e in ev[:8]:
        lines.append(f"- {e['title']}: {e['snippet'][:180]} [{e['id']}]")
    return "\n".join(lines)


# ------------------------------------------------------------- judge --------

JUDGE_SYS = """You are a strict evaluator (LLM-as-judge). Given an evidence register and a draft brief,
rate faithfulness 1-5 (5 = every claim supported by the cited evidence, 1 = mostly unsupported) and
list up to 5 specific unsupported claims. Respond as JSON: {"faithfulness": int, "unsupported": [str]}"""


def judge(state: ResearchState, config: RunnableConfig) -> Command[Literal["synthesizer", "report"]]:
    thread, owner = _cfg(config)
    ev_objs = [Evidence(**e) for e in state.get("evidence", [])]
    draft, n_attr = attribute_citations(state.get("draft", ""), ev_objs)
    ids = {e.id for e in ev_objs}
    cov, uncited = coverage(draft, ids)
    cacc = citation_accuracy(draft, ids)
    faith, unsupported = None, []
    try:
        raw = get_llm("fast", json_mode=True).invoke(
            [SystemMessage(JUDGE_SYS),
             HumanMessage(f"EVIDENCE:\n{evidence_digest([Evidence(**e) for e in state.get('evidence', [])], 180)}"
                          f"\n\nDRAFT:\n{draft}")], config={"run_name": "judge"}).content
        j = json.loads(raw)
        faith, unsupported = int(j.get("faithfulness", 0)), list(j.get("unsupported", []))[:5]
    except Exception as exc:
        log.info("llm judge unavailable: %s", exc)
    verdict = {"evidence_coverage": round(cov, 3), "citation_accuracy": round(cacc, 3), "auto_attributed": n_attr,
               "faithfulness": faith, "uncited": (uncited + unsupported)[:8]}
    audit("judge", verdict, thread, owner)
    s = get_settings()
    needs_redraft = (cov < s.evidence_coverage_threshold or (faith is not None and faith <= 2))
    if needs_redraft and state.get("redrafts", 0) < s.max_redrafts:
        return Command(goto="synthesizer", update={"judge": verdict, "draft": draft,
                                                   "step_log": [f"judge: redraft cov={cov:.2f}"]})
    return Command(goto="report", update={"judge": verdict, "draft": draft, "step_log": [f"judge: accept cov={cov:.2f}"]})


# ------------------------------------------------------------- report -------

def report(state: ResearchState, config: RunnableConfig) -> dict:
    from repurpora.report.archive import archive
    from repurpora.report.builder import build_excel, build_pdf

    thread, owner = _cfg(config)
    plan, sc = state.get("plan") or {}, state.get("scores") or {}
    if not plan.get("want_report", True):
        return {"report": {}}
    if get_settings().require_human_approval and sc.get("decision") == "GO":
        decision = interrupt({"type": "approve_archive", "decision": sc.get("decision"),
                              "question": "Approve archiving this GO recommendation? (yes/no)"})
        if str(decision).strip().lower() not in ("yes", "y", "approve", "true"):
            return {"report": {"skipped": "human reviewer declined archiving"}}
    rid = f"RPR-{uuid.uuid4().hex[:8].upper()}"
    ctx = {"report_id": rid, "query": _last_user_text(state), "plan": plan, "scores": sc,
           "synthesis": state.get("draft", ""), "results": state.get("results", []),
           "evidence": state.get("evidence", []), "coverage": (state.get("judge") or {}).get("evidence_coverage", 0)}
    try:
        pdf, xlsx = build_pdf(ctx), build_excel(ctx)
        meta = {"thread_id": thread, "query": ctx["query"][:500], "molecule": plan.get("molecule"),
                "indication": plan.get("indication") or sc.get("best_opportunity"), "decision": sc.get("decision"),
                "confidence": sc.get("confidence"), "ml_score": sc.get("ml_probability"),
                "coverage": ctx["coverage"],
                "findings": {"checks": sc.get("checks"), "judge": state.get("judge"),
                             "workers": [r["agent"] for r in state.get("results", [])]}}
        out = archive(rid, owner, pdf, xlsx, meta)
        audit("archive", {"report_id": rid, "supabase": out["supabase"], "s3": out["s3_mirror"]}, thread, owner)
    except Exception as exc:
        log.exception("report failed")
        out = {"report_id": rid, "error": str(exc)[:200]}
    return {"report": out, "step_log": [f"report: {rid}"]}


# ------------------------------------------------------------- finalize -----

def _md_table(t: dict, max_rows: int = 6) -> str:
    cols = t["columns"][:6]
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for r in t["rows"][:max_rows]:
        cells = []
        for v in r[:6]:
            s = f"{v:,.2f}".rstrip("0").rstrip(".") if isinstance(v, float) else str(v if v is not None else "–")
            cells.append(s.replace("|", "/")[:48])
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def finalize(state: ResearchState, config: RunnableConfig) -> dict:
    thread, owner = _cfg(config)
    sc, rep, j = state.get("scores") or {}, state.get("report") or {}, state.get("judge") or {}
    out = [state.get("draft", "")]
    out.append("\n---\n### 📊 Key data")
    for r in state.get("results", []):
        if r.get("tables"):
            t = r["tables"][0]
            ids = " ".join(f"[{i}]" for i in (t.get("evidence_ids") or [])[:3])
            out.append(f"**{t['title']}** _({r['agent'].replace('_', ' ')})_ {ids}\n\n{_md_table(t)}\n")
    if sc.get("ml_drivers"):
        out.append("**ML opportunity drivers** (Δ success probability vs. median): " +
                   ", ".join(f"`{f}` {v:+.2f}" for f, v in sc["ml_drivers"][:4]))
    out.append("\n### 🧾 Evidence")
    for e in state.get("evidence", [])[:14]:
        link = f"[{e['title'][:70]}]({e['url']})" if e.get("url") else e["title"][:70]
        out.append(f"- **{e['id']}** · {e['source']} · _{e['trust']}_ — {link}")
    errs = [f"{r['agent']}: {r['error']}" for r in state.get("results", []) if r.get("error")]
    if errs:
        out.append("\n> ⚠️ Partial results — " + "; ".join(errs))
    q = (f"\n### ✅ Quality gates\nEvidence coverage **{j.get('evidence_coverage', 0):.0%}** · citation accuracy "
         f"**{j.get('citation_accuracy', 0):.0%}** · judge faithfulness **{j.get('faithfulness') or 'n/a'}/5** · "
         f"redrafts {state.get('redrafts', 0)}")
    out.append(q)
    if rep.get("pdf_url"):
        out.append(f"\n### 📥 Report `{rep['report_id']}`\n[Download PDF]({rep['pdf_url']}) · "
                   f"[Download Excel]({rep.get('excel_url')}) — archived to Supabase Storage"
                   f"{' + S3' if rep.get('s3_mirror') else ''}.")
    elif rep.get("report_id"):
        out.append(f"\n### 📥 Report `{rep['report_id']}` saved locally (cloud archive unavailable).")
    text, found = dlp_redact("\n".join(out))
    if found:
        audit("dlp_redaction", {"types": found}, thread, owner)
    return {"messages": [AIMessage(text, response_metadata={"report": rep, "decision": sc.get("decision")})]}


# ------------------------------------------------------------- follow-up ----

def follow_up(state: ResearchState, config: RunnableConfig) -> dict:
    ev = [Evidence(**e) for e in state.get("evidence", [])]
    msgs = [SystemMessage("Answer the follow-up question using only the previous brief and evidence register. "
                          "Cite [E#]. Be concise."),
            HumanMessage(f"PREVIOUS BRIEF:\n{state.get('draft', '')}\n\nEVIDENCE:\n{evidence_digest(ev, 160)}"
                         f"\n\nQUESTION: {_last_user_text(state)}")]
    try:
        ans = str(get_llm("primary").invoke(msgs, config={"run_name": "follow_up"}).content)
    except Exception as exc:
        ans = f"(LLM unavailable: {type(exc).__name__})"
    text, _ = dlp_redact(ans)
    return {"messages": [AIMessage(text)]}


# ------------------------------------------------------------- compaction ---

def maybe_compact(state: ResearchState) -> dict:
    """Summarise older turns once the transcript exceeds the token budget."""
    msgs = state.get("messages", [])
    chars = sum(len(str(m.content)) for m in msgs)
    if chars < get_settings().context_token_budget * 4 or len(msgs) < 8:
        return {}
    older = "\n".join(f"{m.type}: {str(m.content)[:500]}" for m in msgs[:-4])
    try:
        s = get_llm("fast").invoke([SystemMessage("Summarise this research conversation in <=120 words: molecules, "
                                                  "indications, decisions, open questions."), HumanMessage(older)])
        return {"summary": str(s.content)}
    except Exception:
        return {}
