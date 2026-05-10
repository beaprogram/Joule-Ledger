# Data Dictionary — Joule Ledger

Every table and column in `data/warehouse.db`. Source, type, definition, allowed values, and example.

---

## dim_program

Canonical program dimension. 28 canonical programs covering 41 historical name variants across 2019–2024.

| Column | Type | Definition | Allowed values | Example |
|---|---|---|---|---|
| `program_id` | TEXT PK | Stable identifier assigned by this project (never changes even if EfficiencyOne renames the program) | P001–P028 | `P009` |
| `canonical_name` | TEXT | Current preferred program name | — | `Low-Income Efficiency` |
| `prior_names` | TEXT | Pipe-delimited list of names used in prior years | — | `Low Income Program\|Efficiency NS Low-Income` |
| `category` | TEXT | Program sector | Residential \| Commercial \| Industrial \| Low-Income \| Other | `Low-Income` |
| `funding_source` | TEXT | Primary funding stream | DSM-Electric \| Province \| Federal | `DSM-Electric` |
| `is_low_income` | INTEGER | 1 if this is a dedicated low-income program | 0 \| 1 | `1` |
| `is_active` | INTEGER | 1 if the program was active in the most recent reporting year | 0 \| 1 | `1` |
| `valid_from` | TEXT | First year the program appeared in reporting | year string | `2019` |
| `valid_to` | TEXT | Last year, or NULL if still active | year string \| NULL | `NULL` |

---

## dim_year

One row per reporting year. 6 rows (2019–2024).

| Column | Type | Definition | Example |
|---|---|---|---|
| `year` | INTEGER PK | Reporting year | `2024` |
| `plan_period` | TEXT | DSM Plan period that governs this year | `2020-2025` |
| `plan_filing_id` | TEXT | Specific plan filing that contains targets for this year | `2026-ext` |

---

## dim_weather

Halifax heating- and cooling-degree-day data. 6 rows in the reporting period; 30 rows in the baseline window (1995–2024).

| Column | Type | Definition | Example |
|---|---|---|---|
| `year` | INTEGER PK | Calendar year | `2023` |
| `halifax_hdd_actual` | REAL | Actual heating degree days, base 18°C, Halifax Stanfield | `4012.3` |
| `halifax_cdd_actual` | REAL | Actual cooling degree days, base 18°C | `89.1` |
| `hdd_30yr_normal` | REAL | Mean HDD over 1995–2024 baseline | `3924.6` |
| `weather_factor` | REAL | `halifax_hdd_actual / hdd_30yr_normal`. >1 = colder than normal year | `1.022` |

Source: ECCC historical climate data API, station 8202251 (Halifax Stanfield Int'l Airport).

---

## dim_rate

Nova Scotia Power residential rate by year. 6 rows (2019–2024).

| Column | Type | Definition | Example |
|---|---|---|---|
| `year` | INTEGER PK | Billing year | `2024` |
| `residential_rate_cents_per_kwh` | REAL | Blended residential rate (cents/kWh) from NS Power rate schedules | `19.43` |

Source: NS Power public rate filings, manually transcribed.

---

## fact_actuals

Delivered actuals from EfficiencyOne Annual Reports. Granularity: one row per (program, year). 138 rows.

| Column | Type | Definition | Notes |
|---|---|---|---|
| `id` | INTEGER PK | Surrogate key | — |
| `program_id` | TEXT FK | → dim_program | — |
| `year` | INTEGER FK | → dim_year | — |
| `actual_gj` | REAL | Delivered energy savings (GJ). Canonical energy unit. | Derived from GWh if GJ not reported directly |
| `actual_gwh_electric` | REAL | Electric savings (GWh), as reported | — |
| `actual_mw` | REAL | Demand savings (MW) | — |
| `actual_tonnes_co2e` | REAL | GHG reductions (tonnes CO2e) | — |
| `actual_spend_cad` | REAL | Program expenditure (CAD, nominal year $) | — |
| `actual_participants` | INTEGER | Participant count | — |
| `actual_lifetime_gj` | REAL | Lifetime energy savings (GJ) where reported | Sparse |
| `as_originally_reported` | REAL | GJ as first published | Populated where restatements observed |
| `as_restated` | REAL | GJ after restatement. Dashboard defaults to this. | — |
| `is_manually_entered` | INTEGER | 1 if value was entered by hand | Always 0 for actuals (only used in targets) |
| `source_page` | INTEGER | PDF page number | — |
| `source_url` | TEXT | URL of Annual Report HTML or PDF | — |

---

## fact_targets

Forecasted targets from DSM Plan filings. Granularity: one row per (program, year, plan_filing). 142 rows.

| Column | Type | Definition | Notes |
|---|---|---|---|
| `id` | INTEGER PK | Surrogate key | — |
| `program_id` | TEXT FK | → dim_program | — |
| `year` | INTEGER FK | → dim_year | The year the target applies to |
| `plan_filing_id` | TEXT | Which plan filing this target comes from | `2020-2025`, `2026-ext`, `2027-2031` |
| `target_gj` | REAL | Forecasted energy savings (GJ) | — |
| `target_gwh_electric` | REAL | Forecasted electric savings (GWh) | — |
| `target_mw` | REAL | Forecasted demand savings (MW) | — |
| `target_tonnes_co2e` | REAL | Forecasted GHG reductions (tonnes CO2e) | — |
| `target_spend_cad` | REAL | Forecasted program budget (CAD) | — |
| `target_participants` | INTEGER | Forecasted participant count | — |
| `is_manually_entered` | INTEGER | 1 if parsed value was unreliable and overridden by hand | ~6% of rows |
| `source_page` | INTEGER | PDF page number | — |
| `source_path` | TEXT | Path to DSM Plan PDF | — |

---

## v_actuals_wx_norm (view)

Weather-normalized electric savings. Divides `actual_gj` by `weather_factor` for DSM-Electric programs to express results in normal-year terms. Non-electric programs pass through unchanged.

Key derived columns:
- `actual_gj_wx_norm` — weather-normalized GJ
- `actual_gwh_electric_wx_norm` — weather-normalized GWh

---

## v_plan_vs_actual (view)

Joined actuals and targets with variance columns. Powers the Plan vs. Actual dashboard page.

Key derived columns:
- `variance_gj` — actual_gj − target_gj
- `variance_pct` — variance as % of target
- `variance_mw`, `variance_spend_cad`
- `actual_cad_per_gj` — cost effectiveness

---

## v_equity (view)

Low-income program totals by year and funding source. Powers the Equity lens page.

---

## v_portfolio_totals (view)

Portfolio-level annual totals for the Executive Summary page.
