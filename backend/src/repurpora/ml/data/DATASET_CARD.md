# Dataset card: repurposing_projects (synthetic, v1)

| Field | Value |
|---|---|
| Rows | 6090 (90 duplicate exports) · positive rate 64.7% · years 2012–2025 |
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
