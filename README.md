# Joule Ledger

*A six-year audit of Efficiency Nova Scotia's plan vs. performance.*

A Power BI dashboard comparing **forecasted DSM Plan targets** against **reported actuals** across six years of EfficiencyOne's public reporting (2019–2024), with weather-normalized electric savings and a dedicated equity lens for low-income programs.

**Status:** Complete · Six reporting years loaded · All five validation checks passing · Pipeline runs end-to-end in ~3 minutes.

---

## What this is

EfficiencyOne files multi-year DSM Plans with the Nova Scotia Energy Board containing forecasted savings by program, then publishes Annual Reports with the actuals. The two streams are never visualized together publicly. **Joule Ledger** bridges that gap. The model lets an analyst answer questions like "which programs beat plan, by how much, after weather normalization" in a few clicks instead of re-reading PDFs.

For the full project report, see [PROJECT_DESCRIPTION.md](PROJECT_DESCRIPTION.md).

---

## Highlights

- **Six reporting years loaded** (2019 through 2024) from public Annual Reports and DSM Plan filings.
- **41 program name variants reconciled** to 28 canonical programs through a hand-maintained mapping table.
- **Weather-normalized electric savings** using a Halifax HDD ratio against a 30-year ECCC baseline.
- **All public headline figures reconcile within ±2%** (max deviation 0.7% in 2021).
- **End-to-end pipeline** runs in approximately 3 minutes; analyst refresh time, including manual review steps, is roughly 20 minutes.

---

## Sample findings surfaced by the dashboard

- **2024 electric programs beat plan on both axes.** Electricity savings reached 172.8 GWh against a filed target of 156.56 GWh (+10.4%); demand savings reached 30.7 MW against 26.42 MW (+16.2%).
- **Low-income share of cumulative impact.** Of the $5.6 billion in lifetime savings since 2011, $628 million (~11.2%) has accrued to low-income homeowners and renters.
- **Program taxonomy drift matters.** Naïve year-over-year comparisons that ignore renamings overstate apparent program volatility; the reconciliation table corrects for this.

Detail and supporting visuals are in [docs/findings.md](docs/findings.md).

---

## The dashboard

Five Power BI pages:

1. **Executive summary** — cumulative GJ saved, GHG avoided, $ saved since 2011, and progress against the current 5-year plan.
2. **Plan vs. Actual** — per-program slope chart of forecast vs. delivered, with variance % and $/GJ cost-effectiveness.
3. **Equity lens** — low-income program participation, $-savings for low-income households, share-of-spend over time.
4. **Weather-normalized performance** — actual savings vs. HDD-adjusted savings, with methodology notes.
5. **Methodology and source map** — every metric traced to its source document and page.

A two-minute walkthrough is linked at the top of [dashboard/README.md](dashboard/README.md).

---

## Architecture

```
SOURCES              INGEST (Python)       WAREHOUSE (SQLite)    SERVING (Power BI)
──────────────────   ──────────────────    ──────────────────    ──────────────────
Annual Reports    →  pdfplumber        →   fact_actuals      →   Plan vs. Actual
                     BeautifulSoup
DSM Plan filings  →  pdfplumber        →   fact_targets      →   Equity lens
                     manual map
ECCC weather      →  requests/API      →   dim_program       →   Weather-normalized
                                           dim_year
NS Power rates    →  manual CSV        →   dim_weather       →   Executive summary
                                           dim_rate
                                           v_actuals_wx_norm →   Methodology/sources
```

---

## Repository structure

```
.
├── README.md                   # this file
├── PROJECT_DESCRIPTION.md      # full project report
├── pipeline.py                 # single-entry ETL runner
├── requirements.txt            # Python dependencies
├── pyproject.toml
│
├── extractors/                 # one module per source
│   ├── annual_reports.py
│   ├── dsm_plans.py
│   ├── eccc_weather.py
│   └── nspower_rates.py
│
├── transforms/                 # cleaning, conformance, name mapping
│   ├── conform_units.py
│   ├── reconcile_programs.py
│   └── load_warehouse.py
│
├── sql/                        # schema and views
│   ├── 001_schema.sql
│   ├── 002_views.sql
│   └── program_mapping.csv     # canonical program names, hand-maintained
│
├── data/
│   ├── raw/                    # immutable raw extracts (committed for auditability)
│   ├── interim/
│   └── warehouse.db            # SQLite warehouse (regenerable)
│
├── dashboard/
│   ├── dashboard.pbix          # Power BI model
│   └── README.md               # walkthrough video link, page descriptions
│
├── docs/
│   ├── data_dictionary.md      # every table, every column
│   ├── control_procedures.md   # refresh runbook + validation checks
│   ├── etl_design.md           # design rationale
│   └── findings.md             # three non-obvious findings
│
└── tests/
    ├── test_extractors.py
    └── test_reconciliation.py
```

---

## Prerequisites

- Python **3.11+**
- Power BI Desktop (Windows) — free download from Microsoft
- SQLite ODBC driver (for the Power BI ↔ SQLite connection)
- ~500 MB free disk

No cloud accounts, no API keys, no paid software.

---

## Quickstart

```bash
# 1. Clone and enter the repo
git clone https://github.com/<your-handle>/joule-ledger.git
cd joule-ledger

# 2. Set up a virtual environment
python -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the full pipeline (raw PDFs → warehouse.db)
python pipeline.py --refresh

# 5. Run validation checks
python pipeline.py --validate

# 6. Open the dashboard
#    Open dashboard/dashboard.pbix in Power BI Desktop and click Refresh.
```

Expected runtime end-to-end: **approximately 3 minutes** on a typical laptop.

---

## Running just one stage

```bash
python pipeline.py --extract annual_reports   # re-pull and parse Annual Reports only
python pipeline.py --extract dsm_plans        # DSM Plan filings only
python pipeline.py --transform                # rebuild the warehouse from interim files
python pipeline.py --validate                 # run data-quality checks
```

---

## Validation

The `--validate` command runs five checks. Current results:

| Check | Threshold | Result |
|---|---|---|
| Total `actual_gj` per year reconciles to public headline | ±2% | **Pass.** Max deviation 0.7% (2021). |
| No nulls in measured columns of fact tables | zero | **Pass.** |
| Every fact row has a valid `program_id` in `dim_program` | 100% | **Pass.** |
| Row counts per source per year are non-decreasing on refresh | strict | **Pass.** |
| Every active program has `valid_to = NULL` in `program_mapping.csv` | strict | **Pass.** |

A failure prints the offending rows and exits non-zero, suitable for CI.

---

## Documentation

- [docs/data_dictionary.md](docs/data_dictionary.md) — every table, every column. Source, type, definition, allowed values, example.
- [docs/control_procedures.md](docs/control_procedures.md) — step-by-step refresh runbook, validation checks, and failure handling.
- [docs/etl_design.md](docs/etl_design.md) — design rationale and tradeoffs.
- [docs/findings.md](docs/findings.md) — three findings the dashboard surfaces.

---

## Known limitations

- **Granularity is program-level only.** Public reporting does not disaggregate to project or customer level, and this project does not attempt to.
- **Approximately 6% of `fact_targets` cells are entered by hand.** Where automated parsing of DSM Plan tables fails, values are entered by hand and flagged with `is_manually_entered = TRUE`. The full list is in [docs/etl_design.md](docs/etl_design.md).
- **Weather normalization is intentionally simple.** It uses an HDD ratio to a 30-year normal. Real DSM evaluations use more sophisticated regression-based methods; this is acknowledged on the dashboard methodology page.
- **Restated figures.** Where a later report restates an earlier number, both `as_originally_reported` and `as_restated` are captured. The dashboard defaults to restated values.

---

## Roadmap

- [ ] Inter-provincial comparison (Efficiency Manitoba, Save On Energy, Énergir)
- [ ] Participant-side payback model for representative households
- [ ] Federal Canada Greener Homes Grant integration
- [ ] Natural-language Q&A layer over the warehouse

See [PROJECT_DESCRIPTION.md](PROJECT_DESCRIPTION.md) §11 for context.

---

## Disclaimer

This is a personal portfolio project. It is not affiliated with, endorsed by, or representative of EfficiencyOne or Efficiency Nova Scotia. All source data is public. Any findings, errors, or interpretations are the author's own.

---

## Acknowledgments

- EfficiencyOne for publishing Annual Reports back to 2019.
- The Nova Scotia Energy Board for maintaining a public docket of DSM Plan filings.
- Environment and Climate Change Canada for the historical climate data API.

---

## License

MIT. See [LICENSE](LICENSE).
