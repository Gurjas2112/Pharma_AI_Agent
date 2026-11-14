"""ML workflow tests: data contract, cleaning, split integrity, golden expected outputs, model quality."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from repurpora.ml.dataset import load_raw
from repurpora.ml.features import CATEGORICAL, LEAKAGE_COLS, RAW_NUMERIC, TARGET, build_preprocessor, clean, split_xy
from repurpora.ml.predict import load_bundle, predict

ML = Path(__file__).parents[1] / "src" / "repurpora" / "ml"
PROCESSED = ML / "data" / "processed"


@pytest.fixture(scope="module")
def bundle():
    return load_bundle()


@pytest.fixture(scope="module")
def raw():
    return load_raw()


# ----------------------------------------------------------------- data contract --

def test_raw_schema_and_leakage_column_present(raw):
    for c in RAW_NUMERIC + CATEGORICAL + [TARGET, "project_id", "assessment_year"] + LEAKAGE_COLS:
        assert c in raw.columns, c
    assert set(raw[TARGET].unique()) <= {0, 1}


def test_clean_applies_domain_rules(raw):
    df = clean(raw)
    assert df.project_id.is_unique
    assert not set(LEAKAGE_COLS) & set(df.columns), "leakage column must be dropped"
    assert "molecule" not in df.columns
    assert (df.competitors.dropna() >= 0).all()
    assert df.cagr_pct.dropna().abs().max() <= 100
    assert df.market_usd_mn.dropna().max() < 50_000
    assert df.unmet_need.dropna().between(0, 1).all()
    assert (df.therapy_area.dropna() == df.therapy_area.dropna().str.lower()).all()


# -------------------------------------------------------------- split integrity --

def test_out_of_time_split_has_no_overlap(bundle):
    train = pd.read_csv(PROCESSED / "train.csv")
    test = pd.read_csv(PROCESSED / "test.csv")
    assert not set(train.project_id) & set(test.project_id)
    assert train.assessment_year.max() < test.assessment_year.min()
    assert len(train) == bundle["metrics"]["split"]["train_rows"]


def test_preprocessor_handles_unknown_category_and_all_missing_row():
    df = clean(load_raw()).head(400)
    X, _ = split_xy(df)
    pre = build_preprocessor().fit(X)
    odd = pd.DataFrame([{c: np.nan for c in RAW_NUMERIC} | {"therapy_area": "ophthalmology", "region": "mars",
                                                             "innovation_type": None}])
    out = pre.transform(odd[X.columns])
    assert np.isfinite(out).all()


# ------------------------------------------------------- golden expected outputs --

def test_model_reproduces_expected_test_predictions(bundle):
    """Regression guard: the shipped model must reproduce the recorded test-set outputs."""
    test = pd.read_csv(PROCESSED / "test.csv")
    expected = pd.read_csv(PROCESSED / "expected_test_predictions.csv")
    X, y = split_xy(test)
    p = bundle["model"].predict_proba(X)[:, 1]
    assert (expected.project_id.values == test.project_id.values).all()
    np.testing.assert_allclose(p, expected.p_success.values, atol=1e-5)
    assert ((p >= bundle["threshold"]).astype(int) == expected.y_pred.values).all()


# ------------------------------------------------------------------ model quality --

def test_model_beats_both_baselines(bundle):
    m = bundle["metrics"]
    t, rule = m["test"], m["baselines_test"]["business_rule_gate"]
    assert t["roc_auc"] > rule["roc_auc"] + 0.1
    assert t["mcc"] > rule["mcc"] and t["mcc"] > m["baselines_test"]["dummy_prior"]["mcc"]
    assert t["cost"] < rule["cost"] < m["baselines_test"]["dummy_prior"]["cost"]


def test_model_is_calibrated_and_not_overfit(bundle):
    m = bundle["metrics"]
    assert m["test"]["ece"] < 0.1
    assert abs(m["overfit_gap_auc"]) < 0.05
    assert m["test"]["roc_auc_95ci"][0] > 0.7


# ----------------------------------------------------------------- inference contract --

def test_predict_contract_validates_ranges():
    with pytest.raises(ValidationError):
        predict({"fto_risk": 14})
    with pytest.raises(ValidationError):
        predict({"innovation_type": "teleportation"})


def test_predict_reports_imputed_fields_and_drivers():
    out = predict({"market_usd_mn": 120, "fto_risk": 2, "unmet_need": 0.8, "evidence_strength": 0.7,
                   "therapy_area": "Respiratory", "region": "India", "innovation_type": "new_dosage_form"})
    assert 0 <= out["probability"] <= 1 and out["label"] in (0, 1)
    assert "dev_cost_usd_mn" in out["imputed_fields"]
    assert out["drivers"] and all(isinstance(d[1], float) for d in out["drivers"])


def test_predict_is_monotonic_in_key_drivers():
    base = {"market_usd_mn": 120, "fto_risk": 2, "unmet_need": 0.6, "evidence_strength": 0.5, "region": "India"}
    hi = predict({**base, "evidence_strength": 0.9, "unmet_need": 0.9})["probability"]
    lo = predict({**base, "evidence_strength": 0.1, "unmet_need": 0.1})["probability"]
    risky = predict({**base, "fto_risk": 10})["probability"]
    assert hi > predict(base)["probability"] > lo
    assert risky < predict(base)["probability"]
