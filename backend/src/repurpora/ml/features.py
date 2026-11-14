"""Steps 3-4 - Data cleaning, feature engineering and the preprocessing pipeline.

Split of responsibilities (prevents train/test leakage):
* ``clean``: **stateless**, row-wise domain rules (dedupe, sentinels, unit fixes, range checks,
  category normalisation, leakage drop). Safe to run before the split.
* ``FeatureEngineer``: stateless derived features, inside the sklearn Pipeline.
* ``build_preprocessor``: **stateful** steps (imputation, winsorising, scaling, one-hot). They are
  fitted on training folds only, inside the Pipeline, so CV and test scores are honest.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

TARGET = "launched_successfully"
ID_COLS = ["project_id"]
LEAKAGE_COLS = ["actual_peak_sales_usd_mn"]
DROP_COLS = ["molecule"]  # high-cardinality ID-like; would memorise per-molecule outcomes

RAW_NUMERIC = ["market_usd_mn", "cagr_pct", "competitors", "patients_mn", "fto_risk", "years_to_last_expiry",
               "active_trials", "phase3_trials", "unmet_need", "evidence_strength", "import_dependency",
               "api_suppliers", "dev_cost_usd_mn", "time_to_market_months"]
CATEGORICAL = ["therapy_area", "region", "innovation_type"]
ENGINEERED = ["log_market", "log_patients", "log_dev_cost", "burden_per_competitor", "projected_market_5y_log",
              "ip_window_open", "phase3_share", "single_source_supply", "need_x_evidence", "market_per_cost_log"]
MODEL_NUMERIC = RAW_NUMERIC + ENGINEERED


# --------------------------------------------------------------------- cleaning --

def clean(df: pd.DataFrame) -> pd.DataFrame:
    """Domain rules a data steward would apply. Stateless, so it never sees the target distribution."""
    df = df.copy()
    if "project_id" in df:
        df = df.drop_duplicates(subset="project_id", keep="first")
    df = df.drop(columns=[c for c in LEAKAGE_COLS + DROP_COLS if c in df], errors="ignore")
    for c in CATEGORICAL:
        if c in df:
            df[c] = df[c].astype("string").str.strip().str.lower().str.replace("'", "", regex=False)
    if "competitors" in df:
        df.loc[df["competitors"] < 0, "competitors"] = np.nan                  # sentinel -> missing
    if "cagr_pct" in df:
        big = df["cagr_pct"].abs() > 100
        df.loc[big, "cagr_pct"] = df.loc[big, "cagr_pct"] / 100                # basis-point typo
    if "market_usd_mn" in df:
        huge = df["market_usd_mn"] > 50_000
        df.loc[huge, "market_usd_mn"] = df.loc[huge, "market_usd_mn"] / 1000   # USD vs USD mn
        df.loc[df["market_usd_mn"] <= 0, "market_usd_mn"] = np.nan
    for c in ("unmet_need", "evidence_strength", "import_dependency"):
        if c in df:
            df.loc[(df[c] < 0) | (df[c] > 1), c] = np.nan                       # impossible -> missing
    if "fto_risk" in df:
        df["fto_risk"] = df["fto_risk"].clip(0, 10)
    return df


# ---------------------------------------------------------- feature engineering --

class FeatureEngineer(BaseEstimator, TransformerMixin):
    """Domain-driven derived features (documented in ml/reports/model_report.md)."""

    def fit(self, X, y=None):
        return self

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        X = X.copy()
        for c in RAW_NUMERIC:
            if c not in X:
                X[c] = np.nan
        X[RAW_NUMERIC] = X[RAW_NUMERIC].apply(pd.to_numeric, errors="coerce").astype(float)
        X["log_market"] = np.log1p(X["market_usd_mn"])
        X["log_patients"] = np.log1p(X["patients_mn"])
        X["log_dev_cost"] = np.log1p(X["dev_cost_usd_mn"])
        X["burden_per_competitor"] = X["patients_mn"] / (X["competitors"] + 1)
        growth = (1 + X["cagr_pct"].clip(-30, 60) / 100) ** 5
        X["projected_market_5y_log"] = np.log1p(X["market_usd_mn"] * growth)
        X["ip_window_open"] = (X["years_to_last_expiry"] <= 0).astype(float).where(X["years_to_last_expiry"].notna())
        X["phase3_share"] = X["phase3_trials"] / (X["active_trials"] + 1)
        X["single_source_supply"] = X["import_dependency"] * (X["api_suppliers"] <= 2)
        X["need_x_evidence"] = X["unmet_need"] * X["evidence_strength"]
        X["market_per_cost_log"] = np.log1p(X["market_usd_mn"] / X["dev_cost_usd_mn"])
        return X


class Winsorizer(BaseEstimator, TransformerMixin):
    """Clip each numeric column to train-fold quantiles (robust to residual outliers)."""

    def __init__(self, lower: float = 0.01, upper: float = 0.99):
        self.lower, self.upper = lower, upper

    def fit(self, X, y=None):
        arr = np.asarray(X, dtype=float)
        self.lo_ = np.nanquantile(arr, self.lower, axis=0)
        self.hi_ = np.nanquantile(arr, self.upper, axis=0)
        return self

    def transform(self, X):
        return np.clip(np.asarray(X, dtype=float), self.lo_, self.hi_)

    def get_feature_names_out(self, input_features=None):
        return np.asarray(input_features) if input_features is not None else None


def build_preprocessor(scale: bool = True) -> Pipeline:
    numeric = Pipeline([
        ("impute", SimpleImputer(strategy="median", add_indicator=True)),
        ("winsor", Winsorizer()),
        *([("scale", StandardScaler())] if scale else []),
    ])
    categorical = Pipeline([
        ("impute", SimpleImputer(strategy="constant", fill_value="unknown")),
        ("onehot", OneHotEncoder(handle_unknown="infrequent_if_exist", min_frequency=20, sparse_output=False)),
    ])
    ct = ColumnTransformer([("num", numeric, MODEL_NUMERIC), ("cat", categorical, CATEGORICAL)],
                           verbose_feature_names_out=False)
    return Pipeline([("engineer", FeatureEngineer()), ("columns", ct)])


def split_xy(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    X = df[RAW_NUMERIC + CATEGORICAL].copy()
    for c in CATEGORICAL:
        X[c] = X[c].astype(object).where(X[c].notna(), np.nan)
    return X, df[TARGET].astype(int)
