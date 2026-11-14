"""Data-source clients used by the worker agents.

* Mock sources (IQVIA, EXIM, USPTO clone, trials stub, web proxy) are called
  over HTTP on the ``mock-apis`` service; if it is unreachable we fall back to
  the same functions in-process so the graph never hard-fails in a demo.
* ClinicalTrials.gov **v2** and **Firecrawl** are real, live sources used when
  enabled and reachable; otherwise the mock equivalents are used.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any

import httpx

from repurpora.cache import cached
from repurpora.mock_apis import data as mock
from repurpora.settings import get_settings
from repurpora.vault import get_secret

log = logging.getLogger(__name__)
_TIMEOUT = httpx.Timeout(12.0, connect=4.0)


def _mock_get(path: str, params: dict[str, Any], fallback) -> dict[str, Any]:
    s = get_settings()
    headers = {}
    if key := os.getenv("MOCK_API_KEY"):
        headers["x-api-key"] = key
    try:
        r = httpx.get(f"{s.mock_api_url.rstrip('/')}{path}", params={k: v for k, v in params.items() if v},
                      headers=headers, timeout=_TIMEOUT)
        r.raise_for_status()
        out = r.json()
        out["_transport"] = "http"
        return out
    except Exception as exc:
        log.info("mock api %s unreachable (%s) -> in-process", path, type(exc).__name__)
        out = fallback(**{k: v for k, v in params.items() if v is not None})
        out["_transport"] = "in-process"
        return out


@cached("iqvia")
def iqvia_market(molecule: str | None = None, therapy_area: str | None = None, region: str = "India",
                 indications: str | None = None):
    return _mock_get("/iqvia/market", {"molecule": molecule, "therapy_area": therapy_area, "region": region,
                                       "indications": indications}, mock.iqvia_market)


@cached("exim")
def exim_trade(molecule: str, country: str = "India"):
    return _mock_get("/exim/trade", {"molecule": molecule, "country": country}, mock.exim_trade)


@cached("uspto")
def uspto_patents(molecule: str, indication: str | None = None):
    return _mock_get("/uspto/patents", {"molecule": molecule, "indication": indication}, mock.uspto_patents)


@cached("profile")
def molecule_profile(molecule: str):
    """Curated profile, or - for any other molecule - a profile enriched from LIVE ClinicalTrials.gov
    conditions so candidate indications are real-world rather than placeholders."""
    prof = _mock_get("/molecule/profile", {"molecule": molecule}, mock.molecule_profile)
    if prof.get("curated"):
        return prof
    try:
        trials = clinical_trials(molecule)
        conds = [t.get("condition", "").split(",")[0].strip() for t in trials.get("trials", [])]
        counts: dict[str, int] = {}
        label: dict[str, str] = {}
        for c in conds:
            if not c or "synthetic" in c.lower() or c.lower() in ("healthy", "healthy volunteers"):
                continue
            key = (re.findall(r"[a-z]+", c.lower()) or [c.lower()])[0]  # merge "COVID-19" / "COVID" / "Covid-19 Infection"
            counts[key] = counts.get(key, 0) + 1
            label.setdefault(key, c)
        ranked = sorted(((label[k], n) for k, n in counts.items()), key=lambda kv: -kv[1])
        if ranked and trials.get("_transport") == "live":
            top = ranked[0][1]
            prof["approved"] = ["See product label (not in curated set)"]
            prof["candidates"] = [(c, round(0.35 + 0.4 * (1 - n / max(top, 1)), 2),
                                   f"{n} registered trial(s) on ClinicalTrials.gov") for c, n in ranked[:5]]
            prof["moa"] = "See literature (molecule outside curated set)"
            prof["innovation"] = (f"Screen {molecule} for the least-crowded indication among {ranked[0][0]}"
                                  + (f" and {ranked[1][0]}" if len(ranked) > 1 else "") + "; validate with web evidence")
            prof["enriched_from"] = "ClinicalTrials.gov v2 (live)"
    except Exception as exc:
        log.info("profile enrichment failed for %s: %s", molecule, type(exc).__name__)
    return prof


# --------------------------- ClinicalTrials.gov v2 (live) -------------------

CTGOV = "https://clinicaltrials.gov/api/v2/studies"


@cached("ctgov", ttl=6 * 3600)
def clinical_trials(molecule: str, condition: str | None = None, max_n: int = 40) -> dict[str, Any]:
    s = get_settings()
    if s.use_live_ctgov:
        try:
            params = {
                "query.intr": molecule,
                "pageSize": max_n,
                "fields": "NCTId,BriefTitle,Condition,Phase,OverallStatus,LeadSponsorName,EnrollmentCount,StartDate,LocationCountry",
                "format": "json",
            }
            if condition:
                params["query.cond"] = condition
            r = httpx.get(CTGOV, params=params, timeout=_TIMEOUT,
                          headers={"User-Agent": "repurpora-research-prototype/1.0"})
            r.raise_for_status()
            rows = []
            for st in r.json().get("studies", []):
                p = st.get("protocolSection", {})
                ident = p.get("identificationModule", {})
                status = p.get("statusModule", {})
                design = p.get("designModule", {})
                spons = p.get("sponsorCollaboratorsModule", {})
                conds = p.get("conditionsModule", {}).get("conditions", [])
                locs = p.get("contactsLocationsModule", {}).get("locations", [])
                rows.append({
                    "nct_id": ident.get("nctId"),
                    "title": ident.get("briefTitle"),
                    "condition": ", ".join(conds[:2]),
                    "phase": "/".join(design.get("phases", []) or ["NA"]),
                    "status": status.get("overallStatus"),
                    "sponsor": spons.get("leadSponsor", {}).get("name"),
                    "enrollment": design.get("enrollmentInfo", {}).get("count"),
                    "start_year": (status.get("startDateStruct", {}).get("date") or "")[:4],
                    "country": locs[0].get("country") if locs else None,
                })
            if rows:
                return {"source": "ClinicalTrials.gov v2 (live)", "molecule": molecule, "trials": rows,
                        "_transport": "live"}
        except Exception as exc:
            log.info("ctgov live failed (%s) -> stub", type(exc).__name__)
    out = _mock_get("/trials/search", {"molecule": molecule, "condition": condition}, mock.trials)
    return out


# --------------------------- Firecrawl web search (live) --------------------

@cached("web", ttl=6 * 3600)
def web_search(query: str, k: int = 5) -> dict[str, Any]:
    s = get_settings()
    key = get_secret("FIRECRAWL_API_KEY") or s.firecrawl_api_key
    if s.use_live_web and key:
        try:
            r = httpx.post(
                "https://api.firecrawl.dev/v2/search",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"query": query, "limit": k},
                timeout=httpx.Timeout(25.0, connect=5.0),
            )
            r.raise_for_status()
            payload = r.json().get("data", {})
            items = payload.get("web", payload if isinstance(payload, list) else [])
            results = [
                {"title": it.get("title", ""), "url": it.get("url", ""),
                 "snippet": (it.get("description") or it.get("markdown") or "")[:500], "kind": "web"}
                for it in items if it.get("url")
            ]
            if results:
                return {"source": "Firecrawl search (live)", "query": query, "results": results,
                        "_transport": "live"}
        except Exception as exc:
            log.info("firecrawl failed (%s) -> mock proxy", type(exc).__name__)
    return _mock_get("/web/search", {"q": query, "k": k}, lambda q, k=5: mock.web_search(q, k))
