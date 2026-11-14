"""Synthetic data behind the mock APIs (IQVIA, EXIM, USPTO clone, trials, web proxy).

All numbers are SYNTHETIC and for demonstration only. Curated molecules carry
hand-tuned, plausible values that tell a coherent repurposing story; any other
molecule gets deterministic, seeded values so results are reproducible.
"""

from __future__ import annotations

import hashlib
import random
from typing import Any

YEAR = 2026

# ---------------------------------------------------------------------------
# Curated molecule profiles
# ---------------------------------------------------------------------------
MOLECULES: dict[str, dict[str, Any]] = {
    "metformin": {
        "approved": ["Type 2 diabetes"],
        "moa": "AMPK activation; hepatic gluconeogenesis inhibition",
        "therapy_area": "Metabolic",
        "candidates": [
            ("Polycystic ovary syndrome", 0.78, "Off-label use widespread; no paediatric-friendly ER formulation"),
            ("Gestational diabetes", 0.66, "Guideline-supported 2nd line; dosing in pregnancy under-studied"),
            ("Colorectal cancer adjuvant", 0.52, "Observational signal; RCT evidence mixed"),
            ("Healthy ageing / frailty", 0.41, "TAME-type trials ongoing; regulatory path unclear"),
        ],
        "forms": ["IR tablet", "ER tablet", "oral solution"],
        "innovation": "Once-daily extended-release paediatric oral suspension for adolescent PCOS",
    },
    "montelukast": {
        "approved": ["Asthma", "Allergic rhinitis", "Exercise-induced bronchoconstriction"],
        "moa": "Cysteinyl leukotriene receptor 1 antagonist",
        "therapy_area": "Respiratory",
        "candidates": [
            ("Post-viral cough / long-COVID airway", 0.61, "No approved therapy; leukotriene pathway implicated"),
            ("Alzheimer's disease (neuroinflammation)", 0.44, "Pre-clinical + small Phase 2 signals"),
            ("Bronchiolitis obliterans syndrome", 0.57, "Rare disease, high unmet need, small trials"),
            ("COPD with eosinophilia", 0.49, "Mixed data; subgroup hypothesis"),
        ],
        "forms": ["tablet", "chewable tablet", "oral granules"],
        "innovation": "Orally-disintegrating film for paediatric asthma with improved adherence + neuropsychiatric-risk labelling programme",
    },
    "sildenafil": {
        "approved": ["Erectile dysfunction", "Pulmonary arterial hypertension"],
        "moa": "PDE5 inhibitor",
        "therapy_area": "Cardiovascular",
        "candidates": [
            ("Raynaud's phenomenon", 0.64, "Off-label; no approved topical option"),
            ("Persistent pulmonary hypertension of the newborn", 0.58, "IV used off-label in NICU"),
            ("Heart failure with preserved EF", 0.33, "RELAX-type trials negative"),
        ],
        "forms": ["tablet", "oral suspension", "IV"],
        "innovation": "Topical sildenafil cream for Raynaud's phenomenon (505(b)(2) pathway)",
    },
    "colchicine": {
        "approved": ["Gout", "Familial Mediterranean fever"],
        "moa": "Microtubule polymerisation inhibitor; NLRP3 inflammasome dampening",
        "therapy_area": "Cardiovascular",
        "candidates": [
            ("Secondary prevention of atherosclerotic CVD", 0.82, "Low-dose 0.5 mg approved in US (2023); generics absent"),
            ("Recurrent pericarditis", 0.74, "Guideline first-line, off-label in many markets"),
            ("Post-operative atrial fibrillation", 0.47, "Mixed trial data"),
        ],
        "forms": ["tablet", "capsule"],
        "innovation": "Low-dose 0.5 mg modified-release colchicine for CV secondary prevention in India",
    },
    "budesonide": {
        "approved": ["Asthma", "Crohn's disease", "Ulcerative colitis"],
        "moa": "Glucocorticoid receptor agonist with high first-pass metabolism",
        "therapy_area": "Respiratory",
        "candidates": [
            ("Eosinophilic esophagitis", 0.81, "Orodispersible / viscous forms approved in EU/US; absent in India"),
            ("IgA nephropathy", 0.69, "Targeted-release form approved (US/EU); high cost"),
            ("Bronchopulmonary dysplasia prevention", 0.45, "Budesonide+surfactant trials ongoing"),
        ],
        "forms": ["inhaler", "nebuliser suspension", "capsule", "rectal foam"],
        "innovation": "Orodispersible budesonide tablet for eosinophilic esophagitis",
    },
    "propranolol": {
        "approved": ["Hypertension", "Angina", "Migraine prophylaxis"],
        "moa": "Non-selective beta-adrenergic antagonist",
        "therapy_area": "CNS",
        "candidates": [
            ("Infantile haemangioma", 0.79, "Paediatric oral solution approved in US/EU"),
            ("PTSD (reconsolidation blockade)", 0.42, "Small RCTs, mixed"),
            ("Angiosarcoma (adjunct)", 0.38, "Case series, rare disease"),
        ],
        "forms": ["tablet", "ER capsule", "oral solution"],
        "innovation": "Taste-masked paediatric propranolol solution for infantile haemangioma in emerging markets",
    },
    "aspirin": {
        "approved": ["Pain", "Fever", "Cardiovascular prevention"],
        "moa": "Irreversible COX-1/COX-2 inhibitor",
        "therapy_area": "Cardiovascular",
        "candidates": [
            ("Pre-eclampsia prevention", 0.76, "Guideline-recommended; chronotherapy formulation lacking"),
            ("Colorectal cancer chemoprevention (Lynch)", 0.55, "CAPP2 evidence; dose debated"),
        ],
        "forms": ["tablet", "EC tablet", "effervescent"],
        "innovation": "Bedtime-release low-dose aspirin for pre-eclampsia prevention",
    },
    "doxycycline": {
        "approved": ["Bacterial infections", "Acne", "Malaria prophylaxis"],
        "moa": "Tetracycline antibiotic; MMP inhibition at sub-antimicrobial doses",
        "therapy_area": "Anti-infective",
        "candidates": [
            ("Lymphatic filariasis (Wolbachia)", 0.63, "Neglected tropical disease, high burden in India"),
            ("Abdominal aortic aneurysm", 0.31, "N-TA3CT negative"),
            ("Rosacea (sub-antimicrobial)", 0.72, "40 mg MR approved in US"),
        ],
        "forms": ["tablet", "capsule", "MR capsule"],
        "innovation": "Sub-antimicrobial MR doxycycline for rosacea in India",
    },
}

# ---------------------------------------------------------------------------
# Therapy-area / disease market tables (synthetic IQVIA-like)
# ---------------------------------------------------------------------------
DISEASE_BURDEN_INDIA = [
    # disease, therapy_area, patients_mn, market_usd_mn, cagr_pct, competitors, generic_share
    ("Asthma", "Respiratory", 34.3, 610, 7.8, 46, 0.91),
    ("COPD", "Respiratory", 55.3, 540, 8.9, 38, 0.88),
    ("Bronchiectasis", "Respiratory", 1.9, 42, 11.4, 6, 0.62),
    ("Idiopathic pulmonary fibrosis", "Respiratory", 0.6, 58, 14.2, 4, 0.35),
    ("Allergic rhinitis", "Respiratory", 98.0, 380, 6.1, 61, 0.94),
    ("Pulmonary tuberculosis", "Respiratory", 2.8, 310, 4.3, 22, 0.97),
    ("Post-viral chronic cough", "Respiratory", 9.5, 66, 12.7, 5, 0.70),
    ("Bronchiolitis obliterans syndrome", "Respiratory", 0.05, 12, 9.8, 1, 0.20),
    ("Type 2 diabetes", "Metabolic", 101.0, 2350, 9.2, 140, 0.86),
    ("Polycystic ovary syndrome", "Metabolic", 16.0, 120, 10.5, 9, 0.80),
    ("Gestational diabetes", "Metabolic", 5.0, 48, 8.0, 7, 0.83),
    ("Atherosclerotic CVD (secondary prevention)", "Cardiovascular", 45.0, 1650, 8.4, 95, 0.90),
    ("Recurrent pericarditis", "Cardiovascular", 0.3, 14, 7.5, 2, 0.75),
    ("Raynaud's phenomenon", "Cardiovascular", 4.2, 22, 6.8, 3, 0.85),
    ("Pre-eclampsia", "Women's health", 2.1, 35, 7.2, 4, 0.95),
    ("Eosinophilic esophagitis", "Gastro", 0.4, 18, 16.5, 1, 0.10),
    ("IgA nephropathy", "Renal", 0.9, 75, 18.3, 2, 0.15),
    ("Infantile haemangioma", "Dermatology", 0.6, 11, 9.1, 2, 0.40),
    ("Lymphatic filariasis", "Anti-infective", 31.0, 40, 3.2, 5, 0.98),
    ("Rosacea", "Dermatology", 7.5, 54, 8.7, 8, 0.70),
]



def _seed(*parts: str) -> random.Random:
    h = hashlib.sha256("|".join(p.lower() for p in parts).encode()).hexdigest()
    return random.Random(int(h[:12], 16))


def norm(m: str) -> str:
    return (m or "").strip().lower()


def molecule_profile(molecule: str) -> dict[str, Any]:
    m = norm(molecule)
    if m in MOLECULES:
        return {"molecule": m, "curated": True, **MOLECULES[m]}
    r = _seed(m)
    areas = ["Respiratory", "Metabolic", "Cardiovascular", "CNS", "Oncology", "Dermatology"]
    return {
        "molecule": m,
        "curated": False,
        "approved": ["Primary indication (synthetic)"],
        "moa": "Not in curated set - synthetic profile",
        "therapy_area": r.choice(areas),
        "candidates": [
            (f"Candidate indication {i + 1} (synthetic)", round(r.uniform(0.25, 0.7), 2), "Generated")
            for i in range(3)
        ],
        "forms": ["tablet"],
        "innovation": "Requires further literature review (molecule outside curated set)",
    }


# --------------------------- IQVIA ------------------------------------------

def iqvia_market(molecule: str | None = None, therapy_area: str | None = None,
                 region: str = "India", indications: str | None = None) -> dict[str, Any]:
    region = region or "India"
    from repurpora.regions import canonical, profile

    region = canonical(region)
    rp = profile(region)
    scale, pscale, cscale = float(rp["market"]), float(rp["patients"]), float(rp["competition"])
    rows = []
    prof = molecule_profile(molecule) if molecule else None
    wanted = {c[0] for c in prof["candidates"]} | set(prof["approved"]) if prof else set()
    for d, ta, pts, mkt, cagr, comp, gshare in DISEASE_BURDEN_INDIA:
        if therapy_area and ta.lower() != therapy_area.lower():
            continue
        if prof and wanted and d not in wanted and not therapy_area:
            continue
        rows.append({
            "disease": d, "therapy_area": ta,
            "patients_mn": round(pts * pscale, 2),
            "market_usd_mn": round(mkt * scale, 1),
            "cagr_5y_pct": cagr,
            "competitors": max(1, int(round(comp * cscale))),
            "generic_share": gshare,
            "burden_to_competition": round(pts * pscale / max(1, int(round(comp * cscale))), 2),
        })
    if prof and not rows:  # molecule outside curated set: synthesize market rows for its indications
        r = _seed(prof["molecule"], region)
        names = [x.strip() for x in (indications or "").split("|") if x.strip()] or [c[0] for c in prof["candidates"]]
        for name in names[:6]:
            pts = round(r.uniform(0.2, 20) * pscale, 2)
            comp = max(1, int(round(r.randint(1, 40) * cscale)))
            rows.append({
                "disease": name, "therapy_area": prof["therapy_area"],
                "patients_mn": pts,
                "market_usd_mn": round(r.uniform(10, 400) * scale, 1),
                "cagr_5y_pct": round(r.uniform(2, 14), 1),
                "competitors": comp, "generic_share": round(r.uniform(.3, .95), 2),
                "burden_to_competition": round(pts / comp, 2),
                "synthetic_market": True,
            })
    mol_sales = None
    if prof:
        r = _seed(prof["molecule"], "sales", region)
        base = r.uniform(40, 220) * scale
        growth = r.uniform(0.02, 0.09)
        mol_sales = [
            {"year": YEAR - 4 + i, "sales_usd_mn": round(base * (1 + growth) ** i, 1),
             "volume_mn_units": round(base * 3.1 * (1 + growth * 0.8) ** i, 1)}
            for i in range(5)
        ]
    return {
        "source": "IQVIA mock API (synthetic)", "region": region,
        "therapy_dynamics": rows, "molecule_sales": mol_sales,
    }


# --------------------------- EXIM -------------------------------------------

EXPORTERS = ["China", "India", "Italy", "Spain", "USA", "Germany", "Israel"]


def exim_trade(molecule: str, country: str = "India") -> dict[str, Any]:
    r = _seed(molecule, country, "exim")
    weights = [r.uniform(0.05, 1.0) for _ in EXPORTERS]
    weights[0] *= 2.4  # China API dominance in most generics
    tot = sum(weights)
    shares = [w / tot for w in weights]
    total_t = round(r.uniform(120, 4200), 1)
    rows = sorted(
        ({"partner": p, "share": round(s, 3), "import_tonnes": round(total_t * s, 1),
          "avg_price_usd_kg": round(r.uniform(8, 140), 2)}
         for p, s in zip(EXPORTERS, shares, strict=True) if p not in {country, {"US": "USA"}.get(country)}),
        key=lambda x: -x["share"],
    )
    trend = [{"year": YEAR - 4 + i, "imports_tonnes": round(total_t * (0.82 + 0.05 * i + r.uniform(-.03, .03)), 1),
              "exports_tonnes": round(total_t * r.uniform(0.3, 1.6) * (0.9 + 0.04 * i), 1)} for i in range(5)]
    return {"source": "EXIM mock server (synthetic)", "molecule": norm(molecule), "country": country,
            "api_import_partners": rows, "trend": trend}


# --------------------------- USPTO clone ------------------------------------

ASSIGNEES = ["Innovator Pharma Inc.", "Generica Labs", "Medisynth Ltd", "Univ. Research Trust",
             "NovaForm Therapeutics", "Sunrise Biopharma", "Delta Formulations"]
PATENT_TYPES = ["Composition of matter", "Formulation", "Method of use", "Process", "Polymorph", "Dosage regimen"]


def uspto_patents(molecule: str, indication: str | None = None) -> dict[str, Any]:
    r = _seed(molecule, indication or "", "patents")
    prof = molecule_profile(molecule)
    n = r.randint(6, 11)
    rows = []
    # Approved generics: the core compound patent is long expired; a minority of
    # secondary (formulation / method-of-use) filings remain active - realistic
    # "evergreening" profile that drives a Low-Medium FTO picture.
    for i in range(n):
        ptype = "Composition of matter" if i == 0 else r.choice(PATENT_TYPES[1:])
        if i == 0:
            filed = r.randint(1978, 1998)
        elif r.random() < 0.35:
            filed = r.randint(2009, 2024)  # recent secondary filing (likely active)
        else:
            filed = r.randint(1992, 2005)  # older secondary filing (likely expired)
        expiry = filed + 20 + (r.choice([0, 0, 0, 1, 2]) if ptype != "Composition of matter" else 0)
        topic = indication or r.choice([c[0] for c in prof["candidates"]] + prof["forms"])
        rows.append({
            "patent_no": f"US-MOCK-{r.randint(7_000_000, 12_999_999)}",
            "title": f"{ptype} relating to {molecule.title()} - {topic}",
            "assignee": r.choice(ASSIGNEES),
            "type": ptype, "filing_year": filed, "expiry_year": expiry,
            "status": "Active" if expiry >= YEAR else "Expired",
            "jurisdiction": r.choice(["US", "US", "EP", "IN", "WO"]),
            "claims_scope": r.choice(["Narrow", "Moderate", "Broad"]),
        })
    rows.sort(key=lambda x: x["filing_year"])
    return {"source": "USPTO API clone (synthetic)", "molecule": norm(molecule), "patents": rows}


# --------------------------- Clinical trials stub ---------------------------

SPONSORS = ["NIH", "AIIMS New Delhi", "Mayo Clinic", "Generica Labs", "Univ. of Oxford",
            "ICMR", "Innovator Pharma Inc.", "Charité Berlin"]
PHASES = ["EARLY_PHASE1", "PHASE1", "PHASE2", "PHASE2/PHASE3", "PHASE3", "PHASE4"]
STATUSES = ["RECRUITING", "ACTIVE_NOT_RECRUITING", "COMPLETED", "NOT_YET_RECRUITING", "TERMINATED"]


def trials(molecule: str, condition: str | None = None) -> dict[str, Any]:
    r = _seed(molecule, condition or "", "trials")
    prof = molecule_profile(molecule)
    conds = [condition] if condition else [c[0] for c in prof["candidates"]] + prof["approved"][:1]
    rows = []
    for _i in range(r.randint(6, 16)):
        cond = r.choice(conds)
        rows.append({
            "nct_id": f"NCT-MOCK-{r.randint(1_000_000, 9_999_999)}",
            "title": f"{molecule.title()} in {cond}: a {r.choice(['randomised', 'open-label', 'pilot'])} study",
            "condition": cond, "phase": r.choice(PHASES), "status": r.choice(STATUSES),
            "sponsor": r.choice(SPONSORS), "enrollment": r.randint(20, 1200),
            "start_year": r.randint(2016, 2026), "country": r.choice(["US", "India", "UK", "Germany", "China"]),
        })
    return {"source": "Clinical trials API stub (synthetic)", "molecule": norm(molecule), "trials": rows}


# --------------------------- Web search proxy -------------------------------

def web_search(query: str, k: int = 5) -> dict[str, Any]:
    q = query.lower()
    hits: list[dict[str, str]] = []
    for m, prof in MOLECULES.items():
        if m in q:
            for cand, _, note in prof["candidates"]:
                hits.append({
                    "title": f"{m.title()} for {cand}: evidence review",
                    "url": f"https://example.org/mock/{m}/{cand.lower().replace(' ', '-').replace('/', '-')}",
                    "snippet": note + f". Mechanism: {prof['moa']}.",
                    "kind": "publication",
                })
            hits.append({
                "title": f"Guideline extract mentioning {m.title()}",
                "url": f"https://example.org/mock/guidelines/{m}",
                "snippet": f"Current guidelines list {m} for {', '.join(prof['approved'])}.",
                "kind": "guideline",
            })
    if not hits:
        hits.append({"title": f"Mock web result for '{query}'", "url": "https://example.org/mock/search",
                     "snippet": "Simulated web proxy result (no curated match).", "kind": "news"})
    return {"source": "Web search proxy (synthetic)", "query": query, "results": hits[:k]}
