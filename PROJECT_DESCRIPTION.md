# Joule Ledger

*A six-year audit of Efficiency Nova Scotia's plan vs. performance.*

A Power BI dashboard built on EfficiencyOne's public reporting, with a documented Python → SQL → Power BI pipeline.

*Project report*

---

## Executive Summary

**Joule Ledger** is a self-serve Power BI model that compares EfficiencyOne's **forecasted DSM Plan targets** against **reported actuals** across six reporting years (2019–2024). The model is backed by a fully reproducible Python and SQL pipeline that ingests public Annual Reports, DSM Plan filings from the Nova Scotia Energy Board docket, ECCC weather data, and Nova Scotia Power historical rates.

The data product unifies forecast and actual streams that have never been visualized together publicly. It applies weather normalization to electric savings using a heating-degree-day ratio against a 30-year normal, surfaces a dedicated equity view for low-income programs, and reconciles program names that have changed across the period through a hand-maintained mapping table.

The repository contains the full pipeline, a SQLite warehouse, the `.pbix` model, a data dictionary covering every table and column, a refresh runbook with five validation checks, and a short findings document. The pipeline runs end-to-end in approximately three minutes on a laptop. All reported figures reconcile to public headline values within ±2%.

---

## 1. Background and Motivation

EfficiencyOne is the non-profit administrator of Efficiency Nova Scotia. Its electricity efficiency programs are funded through the Demand-Side Management (DSM) process and regulated by the Nova Scotia Energy Board. Its non-electric programs are funded by the Province of Nova Scotia and the Government of Canada. Performance is reported publicly in two streams:

- **DSM Plan filings** — multi-year forward-looking documents filed with the regulator, containing forecasted savings, demand reductions, GHG impacts, participant counts, and program budgets.
- **Annual Reports** — backward-looking documents publishing actual delivered results.

Together these documents contain rich, structured information about Nova Scotia's efficiency portfolio, but the data is locked inside narrative PDFs and HTML pages. Before this project, no single source allowed an analyst to ask:

- *Which programs delivered above plan in a given year, and which fell short?*
- *How has the share of portfolio spend going to low-income households evolved?*
- *After adjusting for a colder-than-normal winter, did electricity savings genuinely grow year-over-year?*

The motivation was to build the data plumbing to answer those questions in seconds, and to document the work so that another analyst could refresh and extend it without rediscovering the source material.

---

## 2. Objectives and Outcomes

| Objective | Outcome |
|---|---|
| Compare filed targets against delivered actuals at the program level | Delivered. Variance page renders for all programs across six years. |
| Apply weather normalization to electric savings | Delivered. HDD-ratio normalization implemented as a SQL view; documented on the dashboard methodology page. |
| Surface portfolio equity through a dedicated low-income view | Delivered. Equity page tracks low-income share of spend, savings, and participation. |
| Establish a refresh process runnable in under 30 minutes | Delivered. End-to-end pipeline runs in approximately 3 minutes; the runbook adds manual review steps that bring total analyst time to roughly 20 minutes per refresh. |
| Surface non-obvious findings | Delivered. Three findings documented in `docs/findings.md` and summarized in §8 below. |

---

## 3. Scope

### Delivered

- Annual Reports covering reporting years 2019 through 2024.
- DSM Plan filings covering the same period, including the 2026 DSM Plan extension application filed April 2025 and the 2027–2031 DSM Plan filed April 2026.
- Halifax-area heating- and cooling-degree-day data from Environment and Climate Change Canada, used as the weather normalization basis.
- Program-level metrics: energy savings (GWh, GJ), demand savings (MW), GHG reductions (tonnes CO₂e), participant counts, program expenditure, and lifetime savings where reported.
- A program-name reconciliation table covering every renaming, merge, and split observed across the six-year period.

### Excluded

- Project-level (customer-level) data. Public reporting is at the program rollup and the project does not attempt to disaggregate further.
- Forecasting beyond what the most recent filed plan already projects.
- Financial reconciliation against audited statements.
- Comparison to other provincial efficiency administrators. (Captured in §11 as a future extension.)

---

## 4. Data Sources

| Source | Format | Period covered | Use |
|---|---|---|---|
| EfficiencyOne Annual Reports | HTML and PDF | 2019–2024 | Actual delivered savings, spend, participants by program |
| DSM Plan filings (NS Energy Board public docket) | PDF | 2020–2025 plans, 2026 extension, 2027–2031 plan | Forecasted targets by program |
| ECCC historical climate data, Halifax stations | CSV via API | 1995–2024 (30-year baseline plus reporting period) | Heating- and cooling-degree-day normalization |
| Nova Scotia Power historical residential rate schedules | Public filings | 2019–2024 | Optional context for $-savings derivations |

All sources are public. No authentication, scraping of restricted content, or personally identifiable information is involved.

---

## 5. Methodology and Architecture

The pipeline follows a standard ELT-style flow with four stages:

```
SOURCES              INGEST (Python)       WAREHOUSE (SQLite)    SERVING (Power BI)
──────────────────   ──────────────────    ──────────────────    ──────────────────────
Annual Reports    →  pdfplumber        →   fact_actuals      →   1. Plan vs. Actual
  (HTML + PDF)        BeautifulSoup                               variance page
                                       →   fact_targets      →   2. Program portfolio
DSM Plan filings  →  pdfplumber +
                     manual map        →   dim_program       →   3. Equity page
ECCC weather      →  requests/API      →   dim_year
                                       →   dim_weather       →   4. Weather-normalized
NS Power rates    →  manual CSV        →   dim_rate              savings page
                                       →   v_actuals_wx_norm →   5. Methodology + source map
```

### Layers

1. **Raw ingestion (Python).** Each source has a dedicated extractor module that lands data in `data/raw/` as JSON or CSV, preserving everything including footnotes and source page numbers. Raw files are committed to the repo for auditability.
2. **Cleaning and conformance (Python + SQL).** Programs are mapped to canonical names via a hand-maintained `program_mapping.csv`. Units are converted to a single base (GJ for energy, tonnes for emissions, CAD for currency). Unknowns are flagged rather than silently dropped.
3. **Warehouse (SQLite).** A small star schema with two fact tables and four dimensions, materialized as a single `.db` file for portability.
4. **Serving (Power BI).** A direct connection to the SQLite warehouse via ODBC. All measures are defined in DAX in the model layer so visuals stay simple.

---

## 6. Data Model

A star schema centered on two fact tables sharing four dimensions:

- **`fact_targets`** — granularity: one row per (program, year, plan_filing). Measures: target_gj, target_gwh_electric, target_mw, target_tonnes_co2e, target_spend_cad, target_participants. 142 rows.
- **`fact_actuals`** — granularity: one row per (program, year). Measures: same as targets, plus actual_lifetime_gj where reported. 138 rows.
- **`dim_program`** — canonical program_id, current and prior names, category (Residential / Commercial / Industrial / Low-Income / Other), funding_source (DSM-Electric / Province / Federal), is_low_income flag. 28 canonical programs covering 41 historical name variants.
- **`dim_year`** — year, plan_period, plan_filing_id. 6 rows.
- **`dim_weather`** — year, halifax_hdd_actual, halifax_cdd_actual, hdd_30yr_normal, weather_factor. 6 rows in the reporting period; 30 rows in the baseline window.
- **`dim_rate`** — year, residential_rate_cents_per_kwh.

A SQL view `v_actuals_weather_normalized` divides electric savings by the weather factor to express results in normal-year terms.

---

## 7. Deliverables

All items below are present in the repository:

1. `pipeline.py` — single-entry-point ETL runnable with `python pipeline.py --refresh`.
2. `warehouse.db` — populated SQLite warehouse, regenerable from raw inputs.
3. `dashboard/dashboard.pbix` — Power BI model with five report pages.
4. `docs/data_dictionary.md` — table-by-table, column-by-column reference.
5. `docs/control_procedures.md` — refresh runbook with five validation checks and failure handling.
6. `docs/etl_design.md` — design rationale and tradeoff notes.
7. `docs/findings.md` — three findings the dashboard surfaces, summarized below.
8. **Two-minute walkthrough video** demonstrating the dashboard, linked from the README.

---

## 8. Key Findings

The dashboard surfaces three findings worth highlighting. Detail and supporting visuals are in `docs/findings.md`.

### 8.1 Electric programs beat their 2024 target across both energy and demand

In 2024, EfficiencyOne reported **172.8 GWh of electricity savings against a filed target of 156.56 GWh**, a beat of approximately 10.4%. **Demand savings reached 30.7 MW against a target of 26.42 MW**, a beat of approximately 16.2%. Demand response programs contributed an additional 8.1 MW of available capacity. Total electric program investment was approximately $67.1 million, and an additional $79.1 million from Natural Resources Canada was distributed through the Canada Greener Homes Grant and Oil to Heat Pump Affordability programs. The variance page makes the program-by-program contribution to the overall beat immediately visible.

### 8.2 Low-income programs are a structurally significant share of cumulative impact

Cumulatively since 2011, EfficiencyOne reports **$5.6 billion in lifetime energy savings, of which $628 million has accrued to low-income homeowners and renters** — roughly 11.2% of the total. The equity page traces how that share has evolved year over year, and shows how spending on dedicated low-income programs has grown alongside the introduction of federal funding streams. The dashboard separates DSM-funded electric low-income work from Province- and federally-funded programs to make the funding-source breakdown explicit.

### 8.3 Program taxonomy drift materially affects long-term trend analysis

Across six reporting years the project identified **41 distinct program name variants resolving to 28 canonical programs**. Programs have been renamed, bundled together, or split out as new federal funding streams created reporting carve-outs. Without the reconciliation table, naïve year-over-year comparisons systematically overstate the apparent volatility of individual programs. The methodology page documents every mapping decision and preserves the original names for traceability.

---

## 9. Validation Results

The repository's `--validate` command runs five checks. Current state:

| Check | Threshold | Result |
|---|---|---|
| Total `actual_gj` per year reconciles to public headline | ±2% | Pass for all six years (max deviation 0.7% in 2021). |
| No nulls in measured columns of fact tables | zero | Pass. Two known unreported cells are explicitly populated with `NULL` and excluded from sum aggregations. |
| Every `fact` row has a valid `program_id` in `dim_program` | 100% | Pass. |
| Row counts per source per year are non-decreasing on refresh | strict | Pass on most recent refresh. |
| Every program active in the latest year has `valid_to = NULL` in `program_mapping.csv` | strict | Pass. |

---

## 10. Lessons Learned

A few notes worth recording for anyone extending the work:

- **Treat extraction as manual-assist, not full automation.** Roughly 6% of cells in `fact_targets` are entered by hand because the underlying DSM Plan tables resist reliable PDF parsing. This is flagged via an `is_manually_entered` column rather than hidden, so any consumer of the model can see exactly where automated parsing succeeded.
- **Build the program mapping table before writing any SQL.** Resolving renamings retroactively cost more effort than the same work would have cost up front. The `program_mapping.csv` is a first-class artifact of the project, not an afterthought.
- **Capture both originally-reported and restated figures.** Some Annual Reports restate prior-year actuals after evaluation results land. The model preserves both with `as_originally_reported` and `as_restated` columns and defaults to the restated value, which matches how EfficiencyOne itself reports cumulative figures.
- **Weather normalization is a transparency feature, not a precision claim.** The HDD-ratio approach is intentionally simple and disclosed on the methodology page. It reveals weather-driven variance without claiming the precision of a regression-based evaluation.

---

## 11. Future Extensions

These are explicitly outside the delivered scope but documented for anyone picking up the work:

- Comparison to other provincial efficiency administrators (Efficiency Manitoba, Énergir, Save On Energy) using their published reporting.
- A simple participant-cost model that estimates payback period for representative homeowners by program.
- Integration with federal Canada Greener Homes Grant data, given EfficiencyOne is a co-delivery partner.
- A natural-language Q&A layer over the warehouse using the Anthropic API.

---

## 12. Disclaimer

This is a personal portfolio project. It is not affiliated with, endorsed by, or representative of EfficiencyOne or Efficiency Nova Scotia. All source data is public. Any findings, errors, or interpretations are the author's own.
