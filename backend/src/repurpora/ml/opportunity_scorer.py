"""Repurposing Opportunity Scorer: public facade used by the LangGraph ``scorer`` node.

The full ML workflow lives in sibling modules:

| step | module | output |
|---|---|---|
| 1. data | ``dataset.py`` | ``data/raw/repurposing_projects.csv`` + ``data/DATASET_CARD.md`` |
| 2. EDA | ``eda.py`` | ``reports/eda.md`` + figures |
| 3–4. cleaning, feature engineering, preprocessing | ``features.py`` | sklearn Pipeline |
| 5–8. split, baselines, CV search, calibration, threshold, test eval | ``train.py`` | model bundle, ``metrics.json``, ``reports/model_report.md``, ``data/processed/{train,test,expected_test_predictions}.csv`` |
| 9. inference contract | ``predict.py`` | validated, calibrated predictions + drivers |

CLI:
    uv run python -m repurpora.ml.opportunity_scorer --all     # data -> EDA -> train
    uv run python -m repurpora.ml.opportunity_scorer --train
"""

from __future__ import annotations

import argparse
import json
from typing import Any

from repurpora.ml.predict import load_bundle
from repurpora.ml.predict import predict as _predict

CURRENT_YEAR = 2026


def load_model() -> dict[str, Any]:
    return load_bundle()


def train(**kw) -> dict[str, Any]:
    from repurpora.ml.train import run

    m = run(**kw)
    load_bundle.cache_clear()
    return m


def _innovation(plan: dict | None, reformulation: bool) -> str:
    angle = ((plan or {}).get("angle") or "").lower()
    if "dosage" in angle or "form" in angle or "film" in angle:
        return "new_dosage_form"
    if "population" in angle or "paediatric" in angle or "pediatric" in angle:
        return "new_population"
    return "new_dosage_form" if reformulation and not angle else "new_indication"


def features_from_results(metrics: dict[str, Any], unmet_need: float, evidence_strength: float,
                          reformulation: bool, plan: dict | None = None,
                          therapy_area: str | None = None) -> dict[str, Any]:
    """Map worker-agent metrics onto the model's input contract. Unobserved fields stay None and are imputed."""
    latest = metrics.get("latest_expiry")
    return {
        "market_usd_mn": metrics.get("best_market_usd_mn") or metrics.get("top_market_usd_mn"),
        "cagr_pct": metrics.get("best_cagr_pct") or metrics.get("molecule_sales_cagr_pct"),
        "competitors": metrics.get("best_competitors"),
        "patients_mn": metrics.get("best_patients_mn"),
        "fto_risk": metrics.get("fto_risk_score"),
        "years_to_last_expiry": (latest - CURRENT_YEAR) if isinstance(latest, (int, float)) else None,
        "active_trials": metrics.get("active_trials"),
        "phase3_trials": metrics.get("phase3_trials"),
        "unmet_need": unmet_need,
        "evidence_strength": evidence_strength,
        "import_dependency": metrics.get("top_supplier_share"),
        "api_suppliers": metrics.get("n_suppliers"),
        "therapy_area": therapy_area,
        "region": (plan or {}).get("region"),
        "innovation_type": _innovation(plan, reformulation),
    }


def predict(feat: dict[str, Any]) -> dict[str, Any]:
    return _predict(feat)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="regenerate data, run EDA, train")
    ap.add_argument("--train", action="store_true")
    ap.add_argument("--quick", action="store_true")
    a = ap.parse_args()
    if a.all:
        from repurpora.ml import dataset, eda

        dataset.build()
        print("EDA ->", eda.run())
    if a.all or a.train:
        print(json.dumps(train(quick=a.quick)["test"], indent=2))
    else:
        print(json.dumps(predict(features_from_results({"fto_risk_score": 2}, 0.7, 0.6, True)), indent=2))
