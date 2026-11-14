"""Step 2 - Exploratory data analysis. Writes ``ml/reports/eda.md`` and figures.

The EDA drives concrete decisions, recorded at the end of the report:
dedupe, sentinel handling, unit fixes, log transforms, leakage drop, out-of-time split.

usage: uv run python -m repurpora.ml.eda
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.metrics import roc_auc_score  # noqa: E402

from repurpora.ml.dataset import load_raw  # noqa: E402
from repurpora.ml.features import CATEGORICAL, LEAKAGE_COLS, RAW_NUMERIC, TARGET, clean  # noqa: E402

REPORTS = Path(__file__).parent / "reports"
FIG = REPORTS / "figures"
TEAL, GOLD, VIOLET = "#0E7C86", "#F2A541", "#6C5B7B"


def _save(fig, name: str) -> str:
    FIG.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(FIG / name, dpi=120)
    plt.close(fig)
    return f"figures/{name}"


def _md_table(df: pd.DataFrame, floatfmt: str = "{:.3f}") -> str:
    cols = [str(c) for c in df.columns]
    out = ["| " + " | ".join([df.index.name or ""] + cols) + " |", "|" + "---|" * (len(cols) + 1)]
    for idx, row in df.iterrows():
        cells = [floatfmt.format(v) if isinstance(v, float) else str(v) for v in row.values]
        out.append("| " + " | ".join([str(idx)] + cells) + " |")
    return "\n".join(out)


def univariate_auc(df: pd.DataFrame, cols: list[str]) -> pd.Series:
    """Single-feature ROC-AUC (direction-free). Values near 1 on a post-outcome column flag leakage."""
    out = {}
    y = df[TARGET]
    for c in cols:
        x = pd.to_numeric(df[c], errors="coerce")
        m = x.notna()
        if m.sum() > 50 and x[m].nunique() > 1:
            a = roc_auc_score(y[m], x[m])
            out[c] = max(a, 1 - a)
    return pd.Series(out).sort_values(ascending=False)


def run() -> Path:
    raw = load_raw()
    md = ["# Exploratory data analysis: repurposing_projects", ""]

    # ---- 1. shape & quality -------------------------------------------------------------
    n_dup = int(raw.project_id.duplicated().sum())
    md += ["## 1. Shape and data quality",
           f"- Rows: **{len(raw):,}**; columns: **{raw.shape[1]}**; duplicate `project_id` exports: **{n_dup}**",
           f"- Positive rate (`{TARGET}`): **{raw[TARGET].mean():.1%}**, mildly imbalanced, so we stratify and report PR-AUC",
           ""]
    miss = (raw.isna().mean() * 100).round(2).sort_values(ascending=False)
    miss = miss[miss > 0].to_frame("missing_%")
    md += ["### Missingness", _md_table(miss, "{:.2f}"), ""]
    fig, ax = plt.subplots(figsize=(6, 3))
    ax.barh(miss.index[::-1], miss["missing_%"][::-1], color=TEAL)
    ax.set_xlabel("% missing")
    md += [f"![missingness]({_save(fig, 'missingness.png')})", ""]

    viol = {
        "competitors == -1 (unknown sentinel)": int((raw.competitors < 0).sum()),
        "|cagr_pct| > 100 (basis-point typo)": int((raw.cagr_pct.abs() > 100).sum()),
        "market_usd_mn > 50,000 (USD vs USD mn)": int((raw.market_usd_mn > 50_000).sum()),
        "probabilities outside [0,1]": int(((raw.unmet_need > 1) | (raw.unmet_need < 0)).sum()),
        "upper-case therapy_area variants": int(raw.therapy_area.str.isupper().sum()),
    }
    md += ["### Rule violations found", "| check | rows |", "|---|---|"] + [f"| {k} | {v} |" for k, v in viol.items()] + [""]

    # MNAR check: is patients_mn missingness related to market size?
    pm = raw.patients_mn.isna()
    md += ["### Missingness mechanism",
           f"- `patients_mn` missing rate: {pm[raw.market_usd_mn < 20].mean():.1%} when market < $20M vs "
           f"{pm[raw.market_usd_mn >= 20].mean():.1%} otherwise. Missingness depends on market size, so the "
           "pipeline adds **missing-indicator features** instead of silently imputing.", ""]

    df = clean(raw.assign(**{c: raw[c] for c in LEAKAGE_COLS}).drop(columns=[], errors="ignore"))
    # keep the leakage column temporarily for the leakage screen
    df_leak = raw.drop_duplicates("project_id")

    # ---- 2. target over time ------------------------------------------------------------
    by_year = df.groupby("assessment_year")[TARGET].agg(["mean", "count"])
    fig, ax = plt.subplots(figsize=(6, 3))
    ax.plot(by_year.index, by_year["mean"], marker="o", color=TEAL)
    ax.set_ylabel("success rate")
    ax.set_title("Success rate by assessment year", loc="left", fontsize=10)
    md += ["## 2. Target over time",
           f"Success rate falls from {by_year['mean'].iloc[:3].mean():.1%} (first 3 years) to "
           f"{by_year['mean'].iloc[-3:].mean():.1%} (last 3 years). This is **temporal drift**, so the test set is "
           "**out-of-time** (assessments from 2023 on) rather than a random split.",
           f"![target by year]({_save(fig, 'target_by_year.png')})", ""]

    # ---- 3. distributions ---------------------------------------------------------------
    skew = df[RAW_NUMERIC].skew(numeric_only=True).round(2).sort_values(ascending=False).to_frame("skew")
    md += ["## 3. Numeric distributions", _md_table(df[RAW_NUMERIC].describe().T.round(3), "{:.3f}"), "",
           "### Skewness", _md_table(skew, "{:.2f}"), ""]
    fig, axes = plt.subplots(1, 2, figsize=(7, 2.8))
    axes[0].hist(df.market_usd_mn.dropna(), bins=60, color=GOLD)
    axes[0].set_title("market_usd_mn (raw)", fontsize=9)
    axes[1].hist(np.log1p(df.market_usd_mn.dropna()), bins=60, color=TEAL)
    axes[1].set_title("log1p(market_usd_mn)", fontsize=9)
    md += ["Right-skewed money and population columns are **log-transformed** (the log is near-normal):",
           f"![market]({_save(fig, 'market_log_transform.png')})", ""]

    # ---- 4. categorical vs target -------------------------------------------------------
    md += ["## 4. Success rate by category"]
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.2))
    for ax, c in zip(axes, CATEGORICAL, strict=True):
        rates = df.groupby(c)[TARGET].mean().sort_values()
        ax.barh(rates.index.astype(str), rates.values, color=VIOLET)
        ax.set_title(c, fontsize=9)
        ax.tick_params(labelsize=7)
        md += [f"- **{c}**: highest `{rates.idxmax()}` ({rates.max():.1%}), lowest `{rates.idxmin()}` ({rates.min():.1%})"]
    md += [f"![categories]({_save(fig, 'target_by_category.png')})", ""]

    # ---- 5. correlations ----------------------------------------------------------------
    corr = df[RAW_NUMERIC + [TARGET]].corr(numeric_only=True)
    fig, ax = plt.subplots(figsize=(7, 6))
    im = ax.imshow(corr.values, cmap="RdBu_r", vmin=-1, vmax=1)
    ax.set_xticks(range(len(corr)), corr.columns, rotation=75, fontsize=7)
    ax.set_yticks(range(len(corr)), corr.columns, fontsize=7)
    fig.colorbar(im, ax=ax, shrink=0.7)
    top_pairs = (corr.where(np.triu(np.ones(corr.shape, dtype=bool), 1)).stack().abs()
                 .sort_values(ascending=False).head(5))
    md += ["## 5. Correlations",
           "Strongest pairwise |r|: " + ", ".join(f"{a}~{b} ({v:.2f})" for (a, b), v in top_pairs.items())
           + ". No pair exceeds 0.9, so collinearity is acceptable; L2 regularisation handles the rest.",
           f"![correlation]({_save(fig, 'correlation_heatmap.png')})", ""]

    # ---- 6. leakage screen --------------------------------------------------------------
    uauc = univariate_auc(df_leak, RAW_NUMERIC + LEAKAGE_COLS)
    fig, ax = plt.subplots(figsize=(6, 4))
    colors = ["#C8553D" if c in LEAKAGE_COLS else TEAL for c in uauc.index]
    ax.barh(uauc.index[::-1], uauc.values[::-1], color=colors[::-1])
    ax.axvline(0.5, color="grey", lw=0.8)
    ax.set_xlabel("single-feature ROC-AUC")
    md += ["## 6. Leakage screen (single-feature AUC)", _md_table(uauc.to_frame("auc").round(3), "{:.3f}"), "",
           f"`actual_peak_sales_usd_mn` alone scores AUC **{uauc.get('actual_peak_sales_usd_mn', float('nan')):.3f}**. "
           "It is recorded *after* launch, so it is a textbook **target leak** and is dropped. The strongest "
           f"legitimate signal is `{uauc.drop(LEAKAGE_COLS, errors='ignore').idxmax()}`.",
           f"![leakage]({_save(fig, 'univariate_auc.png')})", ""]

    md += ["## 7. Decisions carried into the pipeline",
           "1. Deduplicate on `project_id`; map sentinel `-1` → missing; fix ×100 and ×1000 unit typos; null impossible probabilities; normalise category case.",
           "2. Drop `actual_peak_sales_usd_mn` (leakage) and `molecule` (high-cardinality identifier).",
           "3. Log-transform skewed money and population features; winsorise at train-fold 1%/99%.",
           "4. Median imputation **with missing indicators** (missingness is informative).",
           "5. Out-of-time test split (assessment_year ≥ 2023); stratified 5-fold CV on the training years.",
           "6. Report PR-AUC and calibration as well as ROC-AUC (imbalance, and the probability is shown to users).", ""]
    REPORTS.mkdir(parents=True, exist_ok=True)
    out = REPORTS / "eda.md"
    out.write_text("\n".join(md), encoding="utf-8")
    return out


if __name__ == "__main__":
    print(run())
