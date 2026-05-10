# Dashboard — Joule Ledger

## Pages

### 1. Executive Summary

Cumulative totals since 2011 (GJ saved, GHG avoided, $ saved) and progress against the current 5-year DSM Plan target. Slicers: year range, funding source.

Key visuals:
- KPI cards: cumulative lifetime GJ, lifetime $ savings, current-year GJ beat/miss
- Bar chart: annual GJ actuals with plan target overlay (2019–2024)
- Donut: share of savings by category (Residential / Commercial / Industrial / Low-Income / Other)

### 2. Plan vs. Actual

Per-program comparison of filed targets vs. delivered actuals. The primary view for auditing program-level performance.

Key visuals:
- Slope chart: target GJ vs. actual GJ, one line per program (filterable by year)
- Table: program, target GJ, actual GJ, variance GJ, variance %, $/GJ cost-effectiveness
- Highlight: programs that missed target appear in red; beats in green

Slicers: year, category, funding source, is_low_income.

### 3. Equity Lens

Dedicated view for low-income program tracking.

Key visuals:
- Stacked bar: low-income vs. non-low-income share of annual spend (2019–2024)
- Line chart: low-income participation count by year, split by funding source
- KPI: low-income share of cumulative lifetime savings (~11.2%)
- Table: program-level detail for is_low_income = 1 programs

### 4. Weather-Normalized Performance

Side-by-side view of raw actual savings and weather-normalized savings for electric programs.

Key visuals:
- Clustered bar: actual_gj vs. actual_gj_wx_norm by year
- Line: weather_factor by year (1.0 = normal year; >1 = colder than normal)
- Annotation card: methodology note — HDD-ratio to 30-year ECCC baseline (see etl_design.md)

### 5. Methodology and Source Map

Every metric on every other page traced back to its source document and page number.

Content:
- Table: metric → source document → page → extraction method → is_manually_entered count
- Notes on unit conversions (GWh → GJ, restatement handling)
- Link to `docs/data_dictionary.md` and `docs/etl_design.md`

---

## Connecting to the warehouse

The model connects via ODBC to `data/warehouse.db`. To reconnect after moving the repo:

1. Open `dashboard.pbix` in Power BI Desktop.
2. Home → Transform data → Data source settings.
3. Update the path to `data/warehouse.db`.
4. Click **Refresh**.

The SQLite ODBC driver must be installed. Download from [sqliteodbc.com](http://www.ch-werner.de/sqliteodbc/) (Windows) or via `brew install sqliteodbc` (macOS, for development only — Power BI requires Windows for full refresh).

---

## DAX measures

All measures are defined in the model layer. Key measures:

```dax
[Variance GJ] = SUM(fact_actuals[actual_gj]) - SUM(fact_targets[target_gj])

[Variance %] =
    DIVIDE(
        SUM(fact_actuals[actual_gj]) - SUM(fact_targets[target_gj]),
        SUM(fact_targets[target_gj])
    )

[Actual $/GJ] =
    DIVIDE(
        SUM(fact_actuals[actual_spend_cad]),
        SUM(fact_actuals[actual_gj])
    )

[Low-Income Share of Spend %] =
    DIVIDE(
        CALCULATE(SUM(fact_actuals[actual_spend_cad]), dim_program[is_low_income] = 1),
        SUM(fact_actuals[actual_spend_cad])
    )
```
