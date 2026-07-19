# Reproducible observations from the current warehouse

These observations describe the committed SQLite data. They are not claims about performance against plan, cost-effectiveness, participant outcomes, or six-year trends.

## 1. Loaded electric savings rise across the three available years

The warehouse totals are 121.4 GWh in 2022, 131.0 GWh in 2023, and 174.4 GWh in 2024. The 2024 value is 33.1% above the 2023 value in the loaded program rows.

Reproduce:

```sql
SELECT year, ROUND(SUM(actual_gwh_electric), 1) AS electric_gwh
FROM fact_actuals
GROUP BY year
ORDER BY year;
```

This comparison does not control for program mix, revised source tables, or attribution methods.

## 2. A small set of programs contributes most loaded electric savings

Across 2022–2024, the five largest program totals in the current warehouse are Business Energy Rebates, Custom (Large Projects), Home Energy Assessment, Instant Savings / Appliance Rebates, and Small Business Energy Solutions.

Reproduce:

```sql
SELECT p.canonical_name, ROUND(SUM(a.actual_gwh_electric), 1) AS electric_gwh
FROM fact_actuals a
JOIN dim_program p USING (program_id)
WHERE a.actual_gwh_electric IS NOT NULL
GROUP BY p.canonical_name
ORDER BY electric_gwh DESC
LIMIT 5;
```

## 3. Current mapping integrity is complete for loaded facts

All 66 fact rows resolve to a program ID in `dim_program`, and none use the `__UNKNOWN__` fallback. This is a data-quality result about the loaded rows, not proof that the 28-program dictionary covers every year or future report.

Reproduce:

```sql
SELECT COUNT(*) AS unknown_rows
FROM fact_actuals
WHERE program_id = '__UNKNOWN__';
```

## Findings that are not yet supported

The current warehouse has zero plan-target rows and no populated spend or participant measures. It cannot yet support statements about:

- target beats or misses;
- cost per unit of savings;
- low-income share of spend or lifetime savings;
- participant growth; or
- trends beginning before 2022.

Those questions remain roadmap items until reviewed source data and validation are added.
