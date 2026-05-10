# ETL Design — Joule Ledger

Design rationale and tradeoff notes for the Python → SQL → Power BI pipeline.

---

## Architecture decisions

### Why SQLite?

A single `.db` file is portable, requires no server, and connects directly to Power BI via the SQLite ODBC driver. The warehouse is small (~500 KB at full load) — there is no query-performance reason to use a heavier engine. Raw files are committed to the repo so the warehouse is always regenerable from source.

### Why star schema instead of a flat table?

The four dimension tables (`dim_program`, `dim_year`, `dim_weather`, `dim_rate`) give Power BI's DAX engine clean foreign-key relationships and make it trivial to add new dimensions (e.g., an inter-provincial comparison dimension) without restructuring the fact tables.

### Why two fact tables?

`fact_actuals` and `fact_targets` have different granularities: actuals are (program, year); targets are (program, year, plan_filing). Merging them would require either NULL-padding one side or de-normalizing plan_filing_id into actuals. The variance view (`v_plan_vs_actual`) joins them at query time.

### Why pdfplumber over tabula-py?

pdfplumber handles text-layer PDFs reliably and is pure Python. tabula-py requires a Java runtime. The DSM Plan PDFs have a text layer, so OCR (e.g., pytesseract) was not needed.

### Why BeautifulSoup over Selenium for Annual Reports?

The Annual Report HTML tables are server-rendered and do not require JavaScript execution. BeautifulSoup with `lxml` is sufficient and much faster.

---

## Unit conversion

All energy values are stored in GJ (gigajoules).

| Source unit | Conversion | Factor |
|---|---|---|
| GWh (electric) | × 3.6 | 3.6 GJ/GWh |
| MWh | × 0.0036 | — |
| GJ | — | 1 (canonical) |

Emissions are stored in tonnes CO2e (as reported; no conversion applied).
Currency is stored in nominal CAD (year of expenditure; no deflation applied).

---

## Weather normalization methodology

Weather normalization is applied in `v_actuals_wx_norm` using an HDD-ratio approach:

```
actual_gj_wx_norm = actual_gj / weather_factor
weather_factor    = halifax_hdd_actual / hdd_30yr_normal
hdd_30yr_normal   = mean(HDD, 1995–2024)
```

**Scope:** Applied only to `funding_source = 'DSM-Electric'` programs. Province- and federally-funded programs (heating conversions, low-income weatherization) are passed through unchanged because their savings are not primarily weather-driven.

**Limitation acknowledged:** This HDD-ratio approach is intentionally simple. Real DSM evaluation uses regression-based methods with additional covariates (economic activity, program ramp-up, etc.). The methodology page of the dashboard states this explicitly. The purpose of the normalization here is transparency — to reveal whether an apparent GJ improvement is weather-driven — not to replace a formal evaluation.

---

## Program name reconciliation

Programs are mapped to canonical IDs via `sql/program_mapping.csv` before any SQL is written. This was the highest-effort artifact of the project.

**Problem:** 41 distinct raw name variants resolve to 28 canonical programs. Programs have been renamed, bundled, and split as federal funding created reporting carve-outs. Without reconciliation, naïve year-over-year comparisons systematically overstate apparent program volatility.

**Approach:**
1. Every raw name variant in every year's data is listed in `raw_name_variants` (pipe-delimited).
2. `program_id` is stable — it never changes even if EfficiencyOne renames the program.
3. `prior_names` preserves the historical names for traceability.
4. `valid_from` / `valid_to` bound the years a program was active.
5. Unmatched names are flagged as `__UNKNOWN__` rather than silently dropped.

**Lesson learned:** Build the mapping table before writing any SQL. Resolving renamings retroactively cost more effort than the same work done up front.

---

## Manual overrides

Approximately 6% of cells in `fact_targets` are entered by hand. DSM Plan tables use merged cells, rotated headers, and footnote references that defeat reliable PDF parsing. Each override is flagged with `is_manually_entered = 1` so consumers of the model can see exactly where automated parsing succeeded.

Manual override log:

| plan_filing_id | program_id | year | column | value entered | reason |
|---|---|---|---|---|---|
| 2020-2025 | P007 | 2022 | target_mw | 4.2 | Merged cell in source PDF; parser returned None |
| 2020-2025 | P008 | 2023 | target_participants | 1800 | Footnote reference parsed instead of value |
| 2026-ext | P010 | 2024 | target_spend_cad | 12500000 | Table spans two pages; pdfplumber split at break |

---

## Restated figures

Some Annual Reports restate prior-year actuals after evaluation results land. The model preserves both:
- `as_originally_reported` — GJ as first published
- `as_restated` — GJ after the correction

The dashboard defaults to `as_restated`, which matches how EfficiencyOne itself reports cumulative figures.

---

## Known parsing limitations

- EfficiencyOne's HTML report structure changed between 2020 and 2021. The extractor handles both layouts but a layout change in future years may require a small update.
- The ECCC API returns data month-by-month; the extractor sums to annual HDD/CDD totals.
- NS Power rate schedules are manually transcribed because there is no public API. The CSV must be updated each year.
