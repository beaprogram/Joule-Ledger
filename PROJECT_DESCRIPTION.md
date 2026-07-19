# Joule Ledger — Project Description

## Purpose

Joule Ledger explores how a reproducible data pipeline can turn public EfficiencyOne annual-report tables into an auditable analytical model. The project focuses on source traceability, program-name reconciliation, explicit limitations, and refreshable visual analysis.

## Delivered scope

The current repository delivers:

- program-level actuals extracted for 2022–2024;
- 66 source-linked fact rows mapped to 28 canonical program definitions;
- ECCC weather context and a documented HDD-ratio normalization view;
- a SQLite star schema with source page/path fields;
- a five-page Streamlit/Plotly application;
- pytest coverage for parsing and reconciliation helpers;
- SQL-backed validation for energy values, required fields, foreign keys, fact grain, and active-program dates.

The committed warehouse does not contain 2019–2021 actuals, DSM plan target rows, spending, or participant data. No Power BI `.pbix` file is included.

## Data flow

1. Extractors read public annual reports, weather data, and a manually maintained rate CSV into versioned JSON.
2. Transform modules conform units and resolve source program names to stable program IDs.
3. The loader rebuilds a SQLite star schema and derived analytical views.
4. Validation checks fail the process when implemented integrity rules are violated.
5. Streamlit queries the warehouse for interactive exploration.

## Design decisions

- **SQLite keeps the portfolio reproducible.** The committed database is small and can be rebuilt from versioned inputs.
- **Raw names are preserved.** Canonical program IDs support comparison without discarding source terminology.
- **Weather normalization is deliberately limited.** The HDD-ratio view is an explanatory feature, not a substitute for a formal impact evaluation.
- **Missing data is visible.** The dashboard states when target, spend, or participant data is unavailable instead of fabricating comparisons.
- **Evidence precedes claims.** A source file, warehouse row, test, or validation query must support every result described as current.

## Known limitations

- Only 2022–2024 program actuals are loaded.
- `fact_targets` is empty, so the project cannot yet calculate plan variance.
- Spend and participant measures are null in the current actuals.
- The annual-report PDF parser is tailored to observed layouts and needs source review when documents change.
- The simple weather adjustment does not control for program mix, measure life, or non-weather drivers.
- A Power BI presentation is designed in documentation but not delivered as a file.

## Completion criteria for plan-vs-actual claims

The project should not describe itself as a plan-versus-actual audit until it has:

1. versioned DSM plan source files or reviewed extracts;
2. non-zero, source-linked `fact_targets` rows;
3. explicit handling for overlapping plan filings;
4. target-to-actual reconciliation tests;
5. dashboard views backed by those rows; and
6. reviewed screenshots or a public demo showing the results.

## Next milestones

1. Complete 2019–2021 actual extraction.
2. Load DSM plan target tables.
3. Add a versioned headline-reference table and genuine reconciliation checks.
4. Review dashboard labels and findings against the expanded warehouse.
5. Publish product screenshots and a stable demo.

## Disclaimer

Joule Ledger is an independent portfolio project using public information. It is not affiliated with or endorsed by EfficiencyOne or Efficiency Nova Scotia.
