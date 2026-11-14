"""Repurposing Opportunity Scorer - a supervised ML model that complements the
rule-based GO / NO-GO gate.

Pipeline (run ``python -m repurpora.ml.opportunity_scorer --train``):
 1. Generate a synthetic but structured dataset of historical repurposing
    projects with pandas (market, competition, IP, clinical & supply features).
    The label ("reached a successful product launch") follows a latent
    logistic function of those features + noise + interactions, i.e. it is
    learnable but not trivially separable.
 2. Clean / validate (clip ranges, impute), stratified train/test split.
 3. Compare Logistic Regression, Random Forest and Gradient Boosting with
    5-fold stratified CV (ROC-AUC), pick the best, then report hold-out
    ROC-AUC, PR-AUC, F1, Brier score and a calibration table; check
    over-fitting via the train-vs-test AUC gap.
 4. Persist the model + metrics + permutation feature importances.

The synthetic data is clearly labelled as such; with real historical portfolio
data the same pipeline applies unchanged.
"""

from __future__ import annotations

import argparse
import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, f1_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

log = logging.getLogger(__name__)
HERE = Path(__file__).parent
ART = HERE / "artifacts"
DATA = HERE / "data" / "synthetic_opportunities.csv"

FEATURES = [
    "market_usd_mn",       # addressable market for the new indication
    "cagr_pct",            # 5y growth
    "competitors",         # number of marketed competitors
    "patients_mn",         # disease burden
    "fto_risk",            # 0..10 patent risk
    "active_trials",       # competing active trials
    "unmet_need",          # 0..1 analyst / literature derived
    "import_dependency",   # 0..1 top supplier share for API
    "evidence_strength",   # 0..1 strength of clinical evidence for new use
    "reformulation",       # 1 if dosage-form innovation (505(b)(2)-like)
]


def generate(n: int = 4000, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({
        "market_usd_mn": rng.lognormal(mean=4.2, sigma=1.1, size=n),
        "cagr_pct": rng.normal(7, 4, n),
        "competitors": rng.poisson(14, n),
        "patients_mn": rng.lognormal(0.5, 1.4, n),
        "fto_risk": rng.integers(0, 11, n).astype(float),
        "active_trials": rng.poisson(9, n),
        "unmet_need": rng.beta(2, 2, n),
        "import_dependency": rng.beta(3, 2.5, n),
        "evidence_strength": rng.beta(2, 3, n),
        "reformulation": rng.integers(0, 2, n),
    })
    z = (
        0.55 * np.log1p(df.market_usd_mn) / 2
        + 0.08 * df.cagr_pct
        - 0.06 * df.competitors
        + 0.25 * np.log1p(df.patients_mn)
        - 0.22 * df.fto_risk
        - 0.05 * df.active_trials
        + 2.2 * df.unmet_need
        - 0.9 * df.import_dependency
        + 2.6 * df.evidence_strength
        + 0.5 * df.reformulation
        + 1.2 * df.unmet_need * df.evidence_strength  # interaction
        - 1.4
    )
    p = 1 / (1 + np.exp(-z))
    df["success"] = (rng.random(n) < p).astype(int)
    # inject realistic data-quality issues, cleaned in `clean()`
    miss = rng.random(n) < 0.03
    df.loc[miss, "cagr_pct"] = np.nan
    df.loc[rng.random(n) < 0.01, "competitors"] = -1
    return df


def clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["competitors"] = df["competitors"].clip(lower=0)
    df["fto_risk"] = df["fto_risk"].clip(0, 10)
    for c in ["unmet_need", "import_dependency", "evidence_strength"]:
        df[c] = df[c].clip(0, 1)
    df["cagr_pct"] = df["cagr_pct"].clip(-20, 40)
    return df


CANDIDATES = {
    "logreg": lambda: LogisticRegression(max_iter=2000, C=1.0),
    "random_forest": lambda: RandomForestClassifier(n_estimators=300, max_depth=8, min_samples_leaf=5,
                                                    random_state=0, n_jobs=-1),
    "grad_boost": lambda: GradientBoostingClassifier(n_estimators=250, max_depth=3, learning_rate=0.05,
                                                     subsample=0.8, random_state=0),
}


def _pipe(est) -> Pipeline:
    return Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler()), ("model", est)])


def train(n: int = 4000) -> dict[str, Any]:
    ART.mkdir(parents=True, exist_ok=True)
    DATA.parent.mkdir(parents=True, exist_ok=True)
    raw = generate(n)
    raw.to_csv(DATA, index=False)
    df = clean(raw)
    X, y = df[FEATURES], df["success"]
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, stratify=y, random_state=42)
    cv = StratifiedKFold(5, shuffle=True, random_state=0)
    cv_scores = {}
    for name, mk in CANDIDATES.items():
        s = cross_val_score(_pipe(mk()), Xtr, ytr, cv=cv, scoring="roc_auc")
        cv_scores[name] = {"mean": round(float(s.mean()), 4), "std": round(float(s.std()), 4)}
    best = max(cv_scores, key=lambda k: cv_scores[k]["mean"])
    model = _pipe(CANDIDATES[best]()).fit(Xtr, ytr)
    p_te = model.predict_proba(Xte)[:, 1]
    p_tr = model.predict_proba(Xtr)[:, 1]
    frac_pos, mean_pred = calibration_curve(yte, p_te, n_bins=8)
    imp = permutation_importance(model, Xte, yte, scoring="roc_auc", n_repeats=8, random_state=0)
    importances = sorted(zip(FEATURES, imp.importances_mean.round(4).tolist(), strict=True), key=lambda x: -x[1])
    metrics = {
        "dataset": {"rows": int(len(df)), "positive_rate": round(float(y.mean()), 3), "synthetic": True},
        "cv_roc_auc": cv_scores,
        "selected_model": best,
        "test": {
            "roc_auc": round(float(roc_auc_score(yte, p_te)), 4),
            "pr_auc": round(float(average_precision_score(yte, p_te)), 4),
            "f1@0.5": round(float(f1_score(yte, p_te >= 0.5)), 4),
            "brier": round(float(brier_score_loss(yte, p_te)), 4),
        },
        "overfit_gap_auc": round(float(roc_auc_score(ytr, p_tr) - roc_auc_score(yte, p_te)), 4),
        "calibration": [{"pred": round(float(a), 3), "obs": round(float(b), 3)} for a, b in zip(mean_pred, frac_pos, strict=True)],
        "feature_importance": [{"feature": f, "importance": v} for f, v in importances],
    }
    joblib.dump({"model": model, "features": FEATURES, "metrics": metrics}, ART / "opportunity_model.joblib")
    (ART / "metrics.json").write_text(json.dumps(metrics, indent=2))
    load_model.cache_clear()
    return metrics


@lru_cache(maxsize=1)
def load_model() -> dict[str, Any]:
    path = ART / "opportunity_model.joblib"
    if not path.exists():
        train()
    return joblib.load(path)


def features_from_results(metrics: dict[str, Any], unmet_need: float, evidence_strength: float,
                          reformulation: bool) -> dict[str, float]:
    """Map worker metrics -> model feature vector (with neutral defaults)."""
    return {
        "market_usd_mn": float(metrics.get("best_market_usd_mn") or metrics.get("top_market_usd_mn") or 60),
        "cagr_pct": float(metrics.get("best_cagr_pct") or metrics.get("molecule_sales_cagr_pct") or 6),
        "competitors": float(metrics.get("best_competitors") or 12),
        "patients_mn": float(metrics.get("best_patients_mn") or 1.0),
        "fto_risk": float(metrics.get("fto_risk_score") if metrics.get("fto_risk_score") is not None else 5),
        "active_trials": float(metrics.get("active_trials") or 8),
        "unmet_need": float(unmet_need),
        "import_dependency": float(metrics.get("top_supplier_share") or 0.5),
        "evidence_strength": float(evidence_strength),
        "reformulation": 1.0 if reformulation else 0.0,
    }


@lru_cache(maxsize=1)
def _baseline_median() -> pd.Series:
    return clean(generate(600, seed=1))[FEATURES].median()


def predict(feat: dict[str, float]) -> dict[str, Any]:
    bundle = load_model()
    model = bundle["model"]
    X = pd.DataFrame([feat])[bundle["features"]]
    p = float(model.predict_proba(X)[0, 1])
    # local explanation: one-at-a-time sensitivity vs dataset median
    med = _baseline_median()
    contrib = {}
    for f in bundle["features"]:
        x2 = X.copy()
        x2[f] = med[f]
        contrib[f] = round(p - float(model.predict_proba(x2)[0, 1]), 4)
    top = sorted(contrib.items(), key=lambda kv: -abs(kv[1]))[:5]
    return {"probability": round(p, 4), "model": bundle["metrics"]["selected_model"],
            "test_roc_auc": bundle["metrics"]["test"]["roc_auc"], "drivers": top, "features": feat}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", action="store_true")
    ap.add_argument("--rows", type=int, default=4000)
    a = ap.parse_args()
    if a.train:
        print(json.dumps(train(a.rows), indent=2))
    else:
        print(json.dumps(predict(features_from_results({}, 0.7, 0.6, True)), indent=2))
