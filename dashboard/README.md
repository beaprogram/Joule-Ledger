# Dashboard status

## Current application: Streamlit

Run the implemented dashboard from the repository root:

```bash
streamlit run app.py
```

Current pages:

1. **Executive Summary** — loaded electricity and GHG actuals by year and category.
2. **Plan vs. Actual** — program actuals plus an explicit notice that plan targets are not loaded.
3. **Equity Lens** — available low-income program metadata; spend and participant views remain limited while those facts are null.
4. **Weather-Normalized Performance** — actuals alongside the documented HDD-ratio view.
5. **Methodology and Source Map** — source and transformation context.

The committed warehouse covers 2022–2024 actuals. Review the main README's status table before interpreting a chart.

## Power BI design: not yet delivered

A future Power BI version is envisioned with the same five-page structure. The DAX below is design reference only; there is no `dashboard.pbix` file in the repository and reviewers should not install an ODBC driver expecting one.

```dax
[Variance GJ] =
    SUM(fact_actuals[actual_gj]) - SUM(fact_targets[target_gj])

[Variance %] =
    DIVIDE(
        [Variance GJ],
        SUM(fact_targets[target_gj])
    )
```

These measures become meaningful only after reviewed plan-target rows are loaded.

## Screenshot checklist

See [../docs/screenshots/README.md](../docs/screenshots/README.md). Add product images only after the visible labels and values have been checked against the committed warehouse.
