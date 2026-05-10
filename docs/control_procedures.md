# Control Procedures — Joule Ledger

Refresh runbook, validation checks, and failure handling.

---

## Refresh runbook

Expected total analyst time: **~20 minutes** (pipeline ~3 min + manual review steps).

### Step 1 — Prerequisites check (~1 min)

- [ ] Python 3.11+ is active (`python --version`)
- [ ] Virtual environment is activated (`.venv/bin/activate`)
- [ ] Dependencies are installed (`pip install -r requirements.txt`)
- [ ] DSM Plan PDFs are present in `data/raw/dsm_plans/`
- [ ] `data/raw/nspower_rates_manual.csv` exists and is current

### Step 2 — Run the pipeline (~3 min)

```bash
python pipeline.py --refresh
```

This runs extract → transform → validate in sequence. Watch for `[FAIL]` lines in log output.

### Step 3 — Review unmatched programs (~5 min)

After `--refresh`, check log output for lines containing `unmatched program names`. Any `__UNKNOWN__` program_ids must be resolved by:

1. Adding a new row to `sql/program_mapping.csv` with the correct `program_id`, `canonical_name`, and `raw_name_variants`
2. Re-running `python pipeline.py --transform`

### Step 4 — Review manually-entered flags (~5 min)

Open `data/interim/targets_reconciled.json` and filter for `"is_manually_entered": true`. Verify the hand-entered values match the source PDF. Document any changes in `docs/etl_design.md` under "Manual overrides".

### Step 5 — Run validation checks (~1 min)

```bash
python pipeline.py --validate
```

All five checks must pass. See [Validation checks](#validation-checks) below.

### Step 6 — Open dashboard and click Refresh (~5 min)

Open `dashboard/dashboard.pbix` in Power BI Desktop and click **Refresh**. Spot-check:
- Executive Summary totals match current Annual Report headline
- Plan vs. Actual variance for 2024 electric programs shows +10.4% GJ beat
- Equity page low-income share is ~11.2% of cumulative lifetime savings

---

## Validation checks

Run with `python pipeline.py --validate`. Failure prints the offending rows and exits non-zero (suitable for CI).

| # | Check | Threshold | Current result |
|---|---|---|---|
| 1 | Total `actual_gj` per year reconciles to public headline | ±2% | Pass. Max deviation 0.7% (2021) |
| 2 | No nulls in measured columns of fact tables (excluding `is_manually_entered = 1` rows) | zero | Pass |
| 3 | Every `fact` row has a valid `program_id` in `dim_program` | 100% | Pass |
| 4 | Row counts per source per year are non-decreasing on refresh | strict | Pass on most recent refresh |
| 5 | Every active program has `valid_to = NULL` in `program_mapping.csv` | strict | Pass |

---

## Failure handling

### Check 1 fails (headline reconciliation)

1. Identify the year with deviation > 2%.
2. Re-read the corresponding Annual Report and compare total GJ at the program-rollup level.
3. Common causes: unit conversion error (GWh vs GJ), restated figure not captured, new program not in mapping.
4. Fix in source data or `program_mapping.csv` and re-run `--transform --validate`.

### Check 2 fails (nulls in measured columns)

1. Run `SELECT * FROM fact_actuals WHERE actual_gj IS NULL AND is_manually_entered = 0` in SQLite.
2. If the null is genuinely unreported, set `is_manually_entered = 1` and populate with NULL explicitly.
3. If it's a parse failure, fix in the extractor and re-run `--refresh`.

### Check 3 fails (orphaned program_ids)

1. The reconciler will have already logged the unmatched names.
2. Add entries to `sql/program_mapping.csv` and re-run `--transform`.

### Check 4 fails (row counts decreased)

1. Inspect which source/year lost rows.
2. Check if the raw JSON file was accidentally overwritten or truncated.
3. Restore from git (`git checkout data/raw/...`) and re-run `--extract`.

### Check 5 fails (active program has closed valid_to)

1. Open `sql/program_mapping.csv` and find the row.
2. If the program is still active, clear `valid_to`.
3. If the program genuinely ended, set `is_active = 0` and ensure `fact_actuals` has no rows for years after `valid_to`.
