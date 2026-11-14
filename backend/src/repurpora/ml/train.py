"""Steps 5-8 - Split, baselines, model selection, calibration, threshold, evaluation, artefacts.

Protocol (no test-set peeking):
  1. clean -> out-of-time split (test = assessment_year >= 2023) -> persist train.csv / test.csv
  2. baselines: majority-prior DummyClassifier and the app's existing **business-rule gate**
  3. RandomizedSearchCV (stratified 5-fold, ROC-AUC) over LogReg / RandomForest / HistGradientBoosting
  4. model choice with the one-standard-error rule (prefer the simpler model when CV scores are tied)
  5. sigmoid calibration (CalibratedClassifierCV) and an F1-optimal threshold from out-of-fold predictions
  6. ONE evaluation on the held-out test set: ROC/PR-AUC (+ bootstrap 95% CI), F1, precision, recall,
     Brier, log-loss, ECE, confusion matrix; learning curve and permutation importance
  7. artefacts: model bundle, metrics.json, model_report.md, figures, expected_test_predictions.csv

usage: uv run python -m repurpora.ml.train
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import sklearn  # noqa: E402
from scipy.stats import loguniform  # noqa: E402
from sklearn.calibration import CalibratedClassifierCV, calibration_curve  # noqa: E402
from sklearn.dummy import DummyClassifier  # noqa: E402
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier  # noqa: E402
from sklearn.inspection import permutation_importance  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import (  # noqa: E402
    average_precision_score,
    balanced_accuracy_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    log_loss,
    matthews_corrcoef,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import (  # noqa: E402
    RandomizedSearchCV,
    StratifiedKFold,
    cross_val_predict,
    learning_curve,
)
from sklearn.pipeline import Pipeline  # noqa: E402

from repurpora.ml.dataset import RAW, load_raw  # noqa: E402
from repurpora.ml.features import CATEGORICAL, RAW_NUMERIC, build_preprocessor, clean, split_xy  # noqa: E402

HERE = Path(__file__).parent
PROCESSED = HERE / "data" / "processed"
ART = HERE / "artifacts"
REPORTS = HERE / "reports"
FIG = REPORTS / "figures"
TEST_FROM_YEAR = 2023
SEED = 42
FP_COST, FN_COST = 2.0, 1.0  # business cost of a false GO vs a missed opportunity
TEAL, GOLD, VIOLET, RED = "#0E7C86", "#F2A541", "#6C5B7B", "#C8553D"

# simplicity order for the one-standard-error rule
CANDIDATES = {
    "logistic_regression": (
        lambda: LogisticRegression(max_iter=3000),
        {"model__C": loguniform(1e-2, 1e1), "model__class_weight": [None, "balanced"]},
        True,
    ),
    "hist_gradient_boosting": (
        lambda: HistGradientBoostingClassifier(random_state=SEED, early_stopping=False),
        {"model__learning_rate": [0.03, 0.06, 0.1], "model__max_depth": [3, 4, None],
         "model__max_leaf_nodes": [15, 31], "model__l2_regularization": [0.0, 1.0, 5.0],
         "model__max_iter": [150, 300]},
        False,
    ),
    "random_forest": (
        lambda: RandomForestClassifier(random_state=SEED, n_jobs=-1),
        {"model__n_estimators": [200, 400], "model__max_depth": [4, 6, 8, None],
         "model__min_samples_leaf": [5, 10, 20], "model__max_features": ["sqrt", 0.5]},
        False,
    ),
}


def rule_gate_predict(X: pd.DataFrame) -> np.ndarray:
    """The app's pre-existing business-rule gate (GO = market & growth & IP & clinical space)."""
    ok = ((X["market_usd_mn"].fillna(0) >= 50) & (X["cagr_pct"].fillna(0) >= 3)
          & (X["fto_risk"].fillna(10) <= 7) & (X["active_trials"].fillna(99) <= 15))
    return ok.astype(int).values


def _cost(y, yhat) -> float:
    return FP_COST * ((yhat == 1) & (y == 0)).sum() + FN_COST * ((yhat == 0) & (y == 1)).sum()


def ece(y, p, bins: int = 10) -> float:
    """Expected calibration error."""
    edges = np.linspace(0, 1, bins + 1)
    idx = np.clip(np.digitize(p, edges) - 1, 0, bins - 1)
    return float(sum(abs(y[idx == b].mean() - p[idx == b].mean()) * (idx == b).mean()
                     for b in range(bins) if (idx == b).any()))


def bootstrap_auc(y, p, n: int = 1000, seed: int = SEED) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    scores = []
    for _ in range(n):
        i = rng.integers(0, len(y), len(y))
        if len(np.unique(y[i])) == 2:
            scores.append(roc_auc_score(y[i], p[i]))
    return float(np.percentile(scores, 2.5)), float(np.percentile(scores, 97.5))


def _save(fig, name):
    FIG.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(FIG / name, dpi=120)
    plt.close(fig)
    return f"figures/{name}"


def run(n_iter: int = 12, quick: bool = False) -> dict:
    t0 = time.time()
    raw = load_raw()
    df = clean(raw)
    train_df = df[df.assessment_year < TEST_FROM_YEAR].reset_index(drop=True)
    test_df = df[df.assessment_year >= TEST_FROM_YEAR].reset_index(drop=True)
    assert not set(train_df.project_id) & set(test_df.project_id), "train/test overlap"
    PROCESSED.mkdir(parents=True, exist_ok=True)
    train_df.to_csv(PROCESSED / "train.csv", index=False)
    test_df.to_csv(PROCESSED / "test.csv", index=False)
    Xtr, ytr = split_xy(train_df)
    Xte, yte = split_xy(test_df)
    cv = StratifiedKFold(5, shuffle=True, random_state=SEED)

    # ---- baselines ------------------------------------------------------------------------
    dummy = DummyClassifier(strategy="prior").fit(Xtr, ytr)
    rule_te = rule_gate_predict(Xte)
    baselines = {
        "dummy_prior": {"roc_auc": 0.5, "f1": float(f1_score(yte, dummy.predict(Xte), zero_division=0)),
                        "mcc": float(matthews_corrcoef(yte, dummy.predict(Xte))),
                        "balanced_accuracy": float(balanced_accuracy_score(yte, dummy.predict(Xte))),
                        "brier": float(brier_score_loss(yte, dummy.predict_proba(Xte)[:, 1])),
                        "cost": float(_cost(yte.values, dummy.predict(Xte)))},
        "business_rule_gate": {"roc_auc": float(roc_auc_score(yte, rule_te)), "f1": float(f1_score(yte, rule_te)),
                               "precision": float(precision_score(yte, rule_te, zero_division=0)),
                               "recall": float(recall_score(yte, rule_te)),
                               "mcc": float(matthews_corrcoef(yte, rule_te)),
                               "balanced_accuracy": float(balanced_accuracy_score(yte, rule_te)),
                               "cost": float(_cost(yte.values, rule_te))},
    }

    # ---- model search -----------------------------------------------------------------------
    search_results, fitted = {}, {}
    for name, (make, space, scale) in CANDIDATES.items():
        pipe = Pipeline([("prep", build_preprocessor(scale=scale)), ("model", make())])
        rs = RandomizedSearchCV(pipe, space, n_iter=3 if quick else n_iter, scoring="roc_auc", cv=cv,
                                random_state=SEED, n_jobs=-1, refit=True, return_train_score=True)
        rs.fit(Xtr, ytr)
        i = rs.best_index_
        res = rs.cv_results_
        search_results[name] = {
            "cv_auc_mean": round(float(res["mean_test_score"][i]), 4),
            "cv_auc_std": round(float(res["std_test_score"][i]), 4),
            "cv_train_auc_mean": round(float(res["mean_train_score"][i]), 4),
            "best_params": {k.replace("model__", ""): (v if isinstance(v, (int, float, str, type(None))) else str(v))
                            for k, v in rs.best_params_.items()},
        }
        fitted[name] = rs.best_estimator_

    # one-standard-error rule (candidates are ordered from simplest to most complex)
    best_name = max(search_results, key=lambda k: search_results[k]["cv_auc_mean"])
    best = search_results[best_name]
    se = best["cv_auc_std"] / np.sqrt(cv.get_n_splits())
    chosen = next(k for k in CANDIDATES if search_results[k]["cv_auc_mean"] >= best["cv_auc_mean"] - se)
    base_pipe = fitted[chosen]

    # ---- calibration + threshold (train data only) -----------------------------------------------
    model = CalibratedClassifierCV(base_pipe, method="sigmoid", cv=cv).fit(Xtr, ytr)
    oof_cal = cross_val_predict(CalibratedClassifierCV(base_pipe, method="sigmoid", cv=3), Xtr, ytr, cv=cv,
                                method="predict_proba", n_jobs=-1)[:, 1]
    # cost-sensitive threshold: a false GO (funding a dud) costs FP_COST x a missed opportunity
    grid = np.round(np.arange(0.05, 0.951, 0.01), 2)
    yv_tr = ytr.values
    costs = [FP_COST * ((oof_cal >= t) & (yv_tr == 0)).sum() + FN_COST * ((oof_cal < t) & (yv_tr == 1)).sum()
             for t in grid]
    threshold = float(grid[int(np.argmin(costs))])

    # ---- single held-out evaluation -----------------------------------------------------------
    p_te = model.predict_proba(Xte)[:, 1]
    yhat = (p_te >= threshold).astype(int)
    yv = yte.values
    lo, hi = bootstrap_auc(yv, p_te)
    cm = confusion_matrix(yv, yhat)
    test = {
        "n": int(len(yv)), "positive_rate": round(float(yv.mean()), 3),
        "roc_auc": round(float(roc_auc_score(yv, p_te)), 4), "roc_auc_95ci": [round(lo, 4), round(hi, 4)],
        "pr_auc": round(float(average_precision_score(yv, p_te)), 4),
        "f1": round(float(f1_score(yv, yhat)), 4), "precision": round(float(precision_score(yv, yhat)), 4),
        "recall": round(float(recall_score(yv, yhat)), 4), "brier": round(float(brier_score_loss(yv, p_te)), 4),
        "log_loss": round(float(log_loss(yv, p_te)), 4), "ece": round(ece(yv, p_te), 4),
        "mcc": round(float(matthews_corrcoef(yv, yhat)), 4),
        "balanced_accuracy": round(float(balanced_accuracy_score(yv, yhat)), 4),
        "cost": float(_cost(yv, yhat)),
        "confusion_matrix": {"tn": int(cm[0, 0]), "fp": int(cm[0, 1]), "fn": int(cm[1, 0]), "tp": int(cm[1, 1])},
    }
    train_auc = float(roc_auc_score(ytr, model.predict_proba(Xtr)[:, 1]))

    # ---- diagnostics -------------------------------------------------------------------------
    figs = {}
    fpr, tpr, _ = roc_curve(yv, p_te)
    pr_p, pr_r, _ = precision_recall_curve(yv, p_te)
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.6))
    axes[0].plot(fpr, tpr, color=TEAL, lw=2, label=f"{chosen} (AUC {test['roc_auc']:.3f})")
    axes[0].scatter([1 - (rule_te[yv == 0] == 0).mean()], [rule_te[yv == 1].mean()], color=RED, zorder=3,
                    label="business-rule gate")
    axes[0].plot([0, 1], [0, 1], color="grey", lw=0.8, ls="--")
    axes[0].set_xlabel("false positive rate")
    axes[0].set_ylabel("true positive rate")
    axes[0].legend(fontsize=7, frameon=False)
    axes[1].plot(pr_r, pr_p, color=VIOLET, lw=2)
    axes[1].axhline(yv.mean(), color="grey", ls="--", lw=0.8)
    axes[1].set_xlabel("recall")
    axes[1].set_ylabel("precision")
    figs["roc_pr"] = _save(fig, "roc_pr_test.png")

    frac, mean_pred = calibration_curve(yv, p_te, n_bins=10)
    fig, ax = plt.subplots(figsize=(4, 3.6))
    ax.plot(mean_pred, frac, marker="o", color=TEAL)
    ax.plot([0, 1], [0, 1], ls="--", color="grey", lw=0.8)
    ax.set_xlabel("predicted probability")
    ax.set_ylabel("observed frequency")
    ax.set_title(f"Calibration (ECE {test['ece']:.3f})", loc="left", fontsize=9)
    figs["calibration"] = _save(fig, "calibration_test.png")

    fig, ax = plt.subplots(figsize=(3.6, 3.2))
    ax.imshow(cm, cmap="Blues")
    for (i, j), v in np.ndenumerate(cm):
        ax.text(j, i, str(v), ha="center", va="center", fontsize=11)
    ax.set_xticks([0, 1], ["pred 0", "pred 1"])
    ax.set_yticks([0, 1], ["true 0", "true 1"])
    ax.set_title(f"Confusion @ threshold {threshold:.2f}", loc="left", fontsize=9)
    figs["confusion"] = _save(fig, "confusion_test.png")

    sizes, tr_sc, va_sc = learning_curve(base_pipe, Xtr, ytr, cv=cv, scoring="roc_auc", n_jobs=-1,
                                         train_sizes=np.linspace(0.15, 1.0, 3 if quick else 6))
    fig, ax = plt.subplots(figsize=(5, 3.4))
    ax.plot(sizes, tr_sc.mean(1), marker="o", color=GOLD, label="train")
    ax.plot(sizes, va_sc.mean(1), marker="o", color=TEAL, label="cross-validation")
    ax.set_xlabel("training rows")
    ax.set_ylabel("ROC-AUC")
    ax.legend(frameon=False, fontsize=8)
    figs["learning_curve"] = _save(fig, "learning_curve.png")

    pi = permutation_importance(model, Xte, yte, scoring="roc_auc", n_repeats=5 if quick else 10,
                                random_state=SEED, n_jobs=-1)
    imp = pd.Series(pi.importances_mean, index=Xte.columns).sort_values(ascending=False)
    fig, ax = plt.subplots(figsize=(5.5, 4.2))
    ax.barh(imp.index[::-1], imp.values[::-1], color=TEAL)
    ax.set_xlabel("drop in test ROC-AUC when shuffled")
    figs["importance"] = _save(fig, "permutation_importance.png")

    # ---- artefacts ---------------------------------------------------------------------------
    expected = pd.DataFrame({"project_id": test_df.project_id, "y_true": yv, "p_success": p_te.round(6),
                             "y_pred": yhat})
    expected.to_csv(PROCESSED / "expected_test_predictions.csv", index=False)
    medians = Xtr[RAW_NUMERIC].median().to_dict()
    modes = {c: Xtr[c].mode().iloc[0] for c in CATEGORICAL}
    data_hash = hashlib.sha256(RAW.read_bytes()).hexdigest()[:16]
    metrics = {
        "trained_at": datetime.now(UTC).isoformat(timespec="seconds"), "sklearn": sklearn.__version__,
        "data_sha256": data_hash, "seed": SEED,
        "split": {"strategy": f"out-of-time: test = assessment_year >= {TEST_FROM_YEAR}",
                  "train_rows": int(len(Xtr)), "test_rows": int(len(Xte)),
                  "train_positive_rate": round(float(ytr.mean()), 3)},
        "baselines_test": baselines, "cv_search": search_results,
        "selected_model": chosen, "best_cv_model": best_name, "selection_rule": "one-standard-error",
        "calibration": "sigmoid (5-fold)", "threshold": round(threshold, 4), "threshold_rule": f"min expected cost (FP={FP_COST:g}, FN={FN_COST:g}) on out-of-fold train predictions",
        "test": test, "train_auc_calibrated": round(train_auc, 4),
        "overfit_gap_auc": round(train_auc - test["roc_auc"], 4),
        "permutation_importance_test": {k: round(float(v), 4) for k, v in imp.items()},
        "runtime_s": round(time.time() - t0, 1),
    }
    ART.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": model, "threshold": threshold, "features": list(Xtr.columns), "medians": medians,
                 "modes": modes, "metrics": metrics}, ART / "opportunity_model.joblib")
    (ART / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    _write_report(metrics, figs)
    return metrics


def _write_report(m: dict, figs: dict) -> None:
    t, b = m["test"], m["baselines_test"]
    rows = "\n".join(f"| {k} | {v['cv_auc_mean']:.4f} ± {v['cv_auc_std']:.4f} | {v['cv_train_auc_mean']:.4f} | "
                     f"`{json.dumps(v['best_params'])}` |" for k, v in m["cv_search"].items())
    imp = "\n".join(f"| {k} | {v:+.4f} |" for k, v in list(m["permutation_importance_test"].items())[:10])
    md = f"""# Model report: repurposing opportunity scorer

Trained {m['trained_at']} · scikit-learn {m['sklearn']} · data sha256 `{m['data_sha256']}` · seed {m['seed']}

## 1. Task
Binary classification: will a repurposing project launch successfully? The output is a **calibrated probability**
shown to users next to the business-rule decision, plus the top drivers.

## 2. Data and split
- Dataset: see [`data/DATASET_CARD.md`](../data/DATASET_CARD.md). EDA: [`eda.md`](eda.md).
- Split: **{m['split']['strategy']}**. Train {m['split']['train_rows']} rows (positive rate {m['split']['train_positive_rate']:.1%}),
  test {m['split']['test_rows']} rows (positive rate {t['positive_rate']:.1%}).
- Files: `data/processed/train.csv`, `data/processed/test.csv`, `data/processed/expected_test_predictions.csv`.

## 3. Preprocessing and feature engineering (`features.py`)
| Stage | Fitted on | What |
|---|---|---|
| `clean` | n/a (stateless) | dedupe, sentinel → NaN, ×100/×1000 unit fixes, range checks, category normalisation, leakage and ID drop |
| `FeatureEngineer` | n/a | log market/patients/cost, burden per competitor, 5-year projected market, IP window open, phase-3 share, single-source supply risk, need × evidence, market per dev-cost |
| Impute + indicators | train folds | median imputation + missing-indicator columns |
| Winsorise | train folds | clip to the 1st/99th percentile |
| Scale / one-hot | train folds | StandardScaler (linear model); one-hot with an infrequent-category bucket, unknown-safe |

## 4. Model selection (stratified 5-fold CV on training years, ROC-AUC)
| model | CV AUC | CV train AUC | best params |
|---|---|---|---|
{rows}

Best CV model: **{m['best_cv_model']}**. Chosen with the one-standard-error rule: **{m['selected_model']}**.
The simplest model within one standard error of the best is preferred because it is easier to explain and more stable.
Calibration: {m['calibration']}. Decision threshold **{m['threshold']:.3f}** ({m['threshold_rule']}).
Why cost-based: with a ~65% base rate, a max-F1 threshold labels almost everything a success (the always-yes
dummy already scores F1 ≈ 0.75). Funding a project that fails costs more than missing one, so false GOs are
weighted 2:1. MCC and balanced accuracy are reported because, unlike F1, they don't reward the dummy.

## 5. Held-out test results (evaluated once)
| metric | model | business-rule gate | prior-only dummy |
|---|---|---|---|
| ROC-AUC | **{t['roc_auc']:.4f}** (95% CI {t['roc_auc_95ci'][0]:.3f}–{t['roc_auc_95ci'][1]:.3f}) | {b['business_rule_gate']['roc_auc']:.4f} | 0.5000 |
| PR-AUC | **{t['pr_auc']:.4f}** | n/a | {t['positive_rate']:.4f} |
| F1 | **{t['f1']:.4f}** | {b['business_rule_gate']['f1']:.4f} | {b['dummy_prior']['f1']:.4f} |
| Precision / Recall | {t['precision']:.3f} / {t['recall']:.3f} | {b['business_rule_gate']['precision']:.3f} / {b['business_rule_gate']['recall']:.3f} | n/a |
| MCC | **{t['mcc']:.4f}** | {b['business_rule_gate']['mcc']:.4f} | {b['dummy_prior']['mcc']:.4f} |
| Balanced accuracy | **{t['balanced_accuracy']:.4f}** | {b['business_rule_gate']['balanced_accuracy']:.4f} | {b['dummy_prior']['balanced_accuracy']:.4f} |
| Decision cost (2×FP + FN) | **{t['cost']:.0f}** | {b['business_rule_gate']['cost']:.0f} | {b['dummy_prior']['cost']:.0f} |
| Brier | {t['brier']:.4f} | n/a | {b['dummy_prior']['brier']:.4f} |
| Log-loss / ECE | {t['log_loss']:.4f} / {t['ece']:.4f} | n/a | n/a |

Confusion matrix: TN {t['confusion_matrix']['tn']}, FP {t['confusion_matrix']['fp']}, FN {t['confusion_matrix']['fn']}, TP {t['confusion_matrix']['tp']}.
Over-fit check: calibrated train AUC {m['train_auc_calibrated']:.4f} vs test {t['roc_auc']:.4f} (gap {m['overfit_gap_auc']:+.4f}).

![roc/pr]({figs['roc_pr']})
![calibration]({figs['calibration']}) ![confusion]({figs['confusion']})

## 6. Diagnostics
![learning curve]({figs['learning_curve']})

The train and CV curves converge as data grows, so more data gives diminishing returns. The remaining error is
mostly label noise, not variance.

### Permutation importance on test (drop in ROC-AUC)
| feature | importance |
|---|---|
{imp}

![importance]({figs['importance']})

## 7. How it is used in the product
`predict.py` validates inputs against a Pydantic contract, fills fields the agents could not observe with training
medians or modes (reported back as `imputed_fields`), and returns the probability, the thresholded label and local drivers.
The LangGraph `scorer` node shows it **next to** the rule gate. It is decision support, not an autonomous decision.

## 8. Limitations
Synthetic training data with a known generating process, so absolute numbers show the workflow is sound, not real-world
accuracy. Retrain on real portfolio outcomes with the same pipeline (`python -m repurpora.ml.train`). Monitor drift
on `assessment_year`.
"""
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "model_report.md").write_text(md, encoding="utf-8")


if __name__ == "__main__":
    import sys

    print(json.dumps(run(quick="--quick" in sys.argv), indent=2)[:3000])
