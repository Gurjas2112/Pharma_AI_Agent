"""Step 9 - Inference contract used by the LangGraph scorer node.

* ``OpportunityFeatures``: Pydantic schema with physical ranges. Unknown values are allowed, because agents
  can't always observe everything.
* ``predict``: calibrated probability, thresholded label, local drivers and the list of imputed fields.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import joblib
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from repurpora.ml.features import CATEGORICAL, RAW_NUMERIC

ART = Path(__file__).parent / "artifacts" / "opportunity_model.joblib"


class OpportunityFeatures(BaseModel):
    market_usd_mn: float | None = Field(None, ge=0)
    cagr_pct: float | None = Field(None, ge=-50, le=100)
    competitors: float | None = Field(None, ge=0)
    patients_mn: float | None = Field(None, ge=0)
    fto_risk: float | None = Field(None, ge=0, le=10)
    years_to_last_expiry: float | None = Field(None, ge=-40, le=40)
    active_trials: float | None = Field(None, ge=0)
    phase3_trials: float | None = Field(None, ge=0)
    unmet_need: float | None = Field(None, ge=0, le=1)
    evidence_strength: float | None = Field(None, ge=0, le=1)
    import_dependency: float | None = Field(None, ge=0, le=1)
    api_suppliers: float | None = Field(None, ge=0)
    dev_cost_usd_mn: float | None = Field(None, ge=0)
    time_to_market_months: float | None = Field(None, ge=0)
    therapy_area: str | None = None
    region: str | None = None
    innovation_type: Literal["new_indication", "new_dosage_form", "new_population"] | None = None


@lru_cache(maxsize=1)
def load_bundle() -> dict[str, Any]:
    if not ART.exists():
        from repurpora.ml.train import run

        run()
    return joblib.load(ART)


def _frame(f: OpportunityFeatures) -> pd.DataFrame:
    row = f.model_dump()
    for c in CATEGORICAL:
        row[c] = (row[c] or None) and str(row[c]).strip().lower().replace("'", "")
    df = pd.DataFrame([row])[RAW_NUMERIC + CATEGORICAL]
    df[RAW_NUMERIC] = df[RAW_NUMERIC].apply(pd.to_numeric, errors="coerce").astype(float)
    df[CATEGORICAL] = df[CATEGORICAL].astype(object).where(df[CATEGORICAL].notna(), np.nan)
    return df


def predict(features: dict[str, Any] | OpportunityFeatures, n_drivers: int = 5) -> dict[str, Any]:
    f = features if isinstance(features, OpportunityFeatures) else OpportunityFeatures(**features)
    b = load_bundle()
    model, thr = b["model"], b["threshold"]
    X = _frame(f)
    p = float(model.predict_proba(X)[0, 1])
    # local explanation: replace each observed field with the training median/mode and measure the change
    drivers = {}
    for c in RAW_NUMERIC + CATEGORICAL:
        if pd.isna(X.at[0, c]):
            continue
        x2 = X.copy()
        x2.at[0, c] = b["medians"].get(c) if c in RAW_NUMERIC else b["modes"].get(c)
        drivers[c] = round(p - float(model.predict_proba(x2)[0, 1]), 4)
    top = sorted(drivers.items(), key=lambda kv: -abs(kv[1]))[:n_drivers]
    m = b["metrics"]
    return {
        "probability": round(p, 4), "label": int(p >= thr), "threshold": round(thr, 4),
        "model": m["selected_model"], "test_roc_auc": m["test"]["roc_auc"],
        "drivers": top, "imputed_fields": [c for c in RAW_NUMERIC + CATEGORICAL if pd.isna(X.at[0, c])],
        "features": f.model_dump(exclude_none=True),
    }
