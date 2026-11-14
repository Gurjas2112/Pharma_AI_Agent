"""Step 1 - Data acquisition: the historical repurposing-projects dataset.

Real portfolio outcome data is confidential, so we generate a SYNTHETIC dataset that
behaves like a real export from a portfolio-management system, including the problems a
real export has:

* mixed numeric / categorical / identifier / date columns
* missing values (MCAR and value-dependent), unit typos and impossible values
* duplicate records (re-exported projects)
* a **leakage column** (`actual_peak_sales_usd_mn`) that is only known *after* the outcome
* class imbalance and time drift (later years are slightly harder)

The label `launched_successfully` comes from a documented latent model: non-linear effects,
interactions, category effects and noise. It is learnable but not trivially separable.

Outputs: ``ml/data/raw/repurposing_projects.csv`` and ``ml/data/DATASET_CARD.md``.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
RAW = HERE / "data" / "raw" / "repurposing_projects.csv"
CARD = HERE / "data" / "DATASET_CARD.md"

THERAPY_AREAS = ["Respiratory", "Metabolic", "Cardiovascular", "CNS", "Oncology", "Dermatology", "Gastro",
                 "Renal", "Anti-infective", "Women's health"]
TA_EFFECT = {"Respiratory": 0.15, "Metabolic": 0.2, "Cardiovascular": 0.1, "CNS": -0.25, "Oncology": -0.6,
             "Dermatology": 0.25, "Gastro": 0.05, "Renal": -0.1, "Anti-infective": 0.0, "Women's health": 0.1}
REGIONS = ["India", "US", "EU", "UK", "China", "Japan", "Brazil", "Southeast Asia"]
REGION_EFFECT = {"India": 0.2, "US": -0.15, "EU": -0.1, "UK": -0.05, "China": 0.0, "Japan": -0.2, "Brazil": 0.1,
                 "Southeast Asia": 0.15}
INNOVATION = ["new_indication", "new_dosage_form", "new_population"]
INNOV_EFFECT = {"new_indication": -0.35, "new_dosage_form": 0.45, "new_population": 0.1}
MOLECULES = ["metformin", "montelukast", "sildenafil", "colchicine", "budesonide", "propranolol", "aspirin",
             "doxycycline", "atorvastatin", "amlodipine", "omeprazole", "levetiracetam", "hydroxychloroquine",
             "ivermectin", "tacrolimus", "naltrexone", "minocycline", "losartan", "baclofen", "ketamine"]


def generate(n: int = 6000, seed: int = 2026) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    year = rng.integers(2012, 2026, n)
    ta = rng.choice(THERAPY_AREAS, n)
    region = rng.choice(REGIONS, n, p=[0.3, 0.18, 0.15, 0.05, 0.1, 0.06, 0.06, 0.1])
    innov = rng.choice(INNOVATION, n, p=[0.45, 0.35, 0.2])

    market = rng.lognormal(4.0, 1.2, n)                         # USD mn, heavy right tail
    cagr = rng.normal(7, 4.5, n)
    competitors = rng.poisson(np.where(market > 150, 22, 10))   # big markets attract competitors
    patients = rng.lognormal(0.3, 1.5, n)
    fto = np.clip(rng.normal(np.where(innov == "new_dosage_form", 3.5, 5.0), 2.4, n), 0, 10).round()
    years_to_expiry = np.round(rng.normal(np.where(fto > 6, 6, -1), 4, n))
    active_trials = rng.poisson(8 + 0.05 * patients, n)
    phase3 = rng.binomial(active_trials, 0.22)
    unmet = rng.beta(2, 2, n)
    evidence = rng.beta(2, 3, n)
    import_dep = rng.beta(3, 2.5, n)
    suppliers = rng.integers(1, 12, n)
    dev_cost = rng.lognormal(np.where(innov == "new_indication", 3.6, 2.6), 0.5, n)
    ttm = np.round(rng.normal(np.where(innov == "new_indication", 60, 30), 9, n))

    z = (
        0.45 * np.log1p(market) / 2
        + 0.07 * np.clip(cagr, -10, 30)
        - 0.045 * competitors
        + 0.22 * np.log1p(patients)
        - 0.30 * np.maximum(fto - 5, 0)                     # risk only bites above medium FTO (non-linear)
        - 0.06 * np.clip(years_to_expiry, 0, 15)
        - 0.04 * active_trials + 0.08 * phase3
        + 1.9 * unmet + 2.4 * evidence
        + 1.4 * unmet * evidence                            # interaction
        - 0.8 * import_dep * (suppliers <= 2)               # single-source supply risk
        - 0.25 * np.log1p(dev_cost)
        + np.vectorize(TA_EFFECT.get)(ta) + np.vectorize(REGION_EFFECT.get)(region)
        + np.vectorize(INNOV_EFFECT.get)(innov)
        - 0.04 * (year - 2012)                              # temporal drift: later projects slightly harder
        - 0.9
    )
    p = 1 / (1 + np.exp(-z))
    y = (rng.random(n) < p).astype(int)

    df = pd.DataFrame({
        "project_id": [f"PRJ-{i:05d}" for i in range(n)],
        "assessment_year": year,
        "molecule": rng.choice(MOLECULES, n),
        "therapy_area": ta, "region": region, "innovation_type": innov,
        "market_usd_mn": market.round(2), "cagr_pct": cagr.round(2), "competitors": competitors,
        "patients_mn": patients.round(3), "fto_risk": fto, "years_to_last_expiry": years_to_expiry,
        "active_trials": active_trials, "phase3_trials": phase3,
        "unmet_need": unmet.round(3), "evidence_strength": evidence.round(3),
        "import_dependency": import_dep.round(3), "api_suppliers": suppliers,
        "dev_cost_usd_mn": dev_cost.round(2), "time_to_market_months": ttm,
        "launched_successfully": y,
    })
    # LEAKAGE column: only observable after launch (must never be used as a feature)
    df["actual_peak_sales_usd_mn"] = np.where(y == 1, (market * rng.uniform(0.05, 0.3, n)).round(2), 0.0)

    # ---- realistic data-quality problems ------------------------------------------------
    def holes(col, frac):
        df.loc[rng.random(n) < frac, col] = np.nan
    holes("cagr_pct", 0.05)
    holes("fto_risk", 0.04)
    holes("phase3_trials", 0.08)
    holes("dev_cost_usd_mn", 0.10)
    holes("time_to_market_months", 0.07)
    # value-dependent missingness: small markets often lack patient estimates (MNAR-ish)
    df.loc[(df.market_usd_mn < 20) & (rng.random(n) < 0.25), "patients_mn"] = np.nan
    df.loc[rng.random(n) < 0.01, "competitors"] = -1                        # sentinel for "unknown"
    df.loc[rng.random(n) < 0.006, "cagr_pct"] *= 100                        # % typed as basis points
    df.loc[rng.random(n) < 0.004, "market_usd_mn"] *= 1000                  # USD instead of USD mn
    df.loc[rng.random(n) < 0.004, "unmet_need"] = 1.7                       # out of [0, 1]
    df["therapy_area"] = df["therapy_area"].where(rng.random(n) > 0.03, df["therapy_area"].str.upper())
    dups = df.sample(frac=0.015, random_state=seed)                         # re-exported records
    return pd.concat([df, dups], ignore_index=True).sample(frac=1, random_state=seed).reset_index(drop=True)


CARD_TEXT = """# Dataset card: repurposing_projects (synthetic, v1)

| Field | Value |
|---|---|
| Rows | {rows} ({dups} duplicate exports) · positive rate {pos:.1%} · years {ymin}–{ymax} |
| Unit of observation | One repurposing project assessment (molecule × indication / dosage form / population × region) |
| Target | `launched_successfully`: product reached market and met its year-2 sales plan |
| Generation | `repurpora.ml.dataset.generate(seed=2026)`: documented latent logistic model with non-linear, interaction, category and temporal-drift effects plus noise |

## Columns
| column | type | notes |
|---|---|---|
| project_id | id | not a feature |
| assessment_year | int | used for the **out-of-time** test split (≥ 2023) |
| molecule | categorical | high-cardinality, excluded to avoid memorising molecule-level outcomes |
| therapy_area, region, innovation_type | categorical | case inconsistencies present |
| market_usd_mn, patients_mn, dev_cost_usd_mn | numeric, right-skewed | log-transformed; unit-error outliers (×1000) |
| cagr_pct | numeric | 5% missing; some values typed ×100 |
| competitors | count | `-1` sentinel means unknown |
| fto_risk | 0–10 | 4% missing |
| years_to_last_expiry | int | negative means patents already expired |
| active_trials, phase3_trials | counts | phase3 8% missing |
| unmet_need, evidence_strength, import_dependency | 0–1 | rare out-of-range values |
| api_suppliers | count | |
| time_to_market_months | numeric | 7% missing |
| **actual_peak_sales_usd_mn** | numeric | **LEAKAGE**: observed only after launch. Dropped before modelling. |

## Known issues (handled in `features.clean`)
Duplicates, sentinels, unit typos, out-of-range probabilities, inconsistent category casing, MNAR missingness in `patients_mn`.

## Intended use and limits
For demonstrating and validating the modelling workflow. Its probabilities are illustrative until the model is retrained on
real portfolio history with the same pipeline.
"""


def build(n: int = 6000, seed: int = 2026) -> pd.DataFrame:
    df = generate(n, seed)
    RAW.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(RAW, index=False)
    CARD.write_text(CARD_TEXT.format(rows=len(df), dups=int(df.project_id.duplicated().sum()),
                                     pos=df.launched_successfully.mean(), ymin=df.assessment_year.min(),
                                     ymax=df.assessment_year.max()), encoding="utf-8")
    return df


def load_raw() -> pd.DataFrame:
    if not RAW.exists():
        build()
    return pd.read_csv(RAW)


if __name__ == "__main__":
    d = build()
    print(d.shape, d.launched_successfully.mean().round(3))
