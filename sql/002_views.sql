-- Joule Ledger derived views
-- Applied after fact tables are populated.

-- ============================================================
-- v_actuals_wx_norm  (weather-normalized electric savings)
-- ============================================================
-- Divides actual GJ by the weather_factor to express electric savings
-- in normal-year terms.  Non-electric programs are passed through unchanged.
-- The HDD-ratio approach is intentionally simple (see docs/etl_design.md).

CREATE VIEW IF NOT EXISTS v_actuals_wx_norm AS
SELECT
    a.id,
    a.program_id,
    a.year,
    p.canonical_name,
    p.category,
    p.funding_source,
    p.is_low_income,
    a.actual_gj,
    a.actual_gwh_electric,
    a.actual_mw,
    a.actual_tonnes_co2e,
    a.actual_spend_cad,
    a.actual_participants,
    w.weather_factor,
    w.halifax_hdd_actual,
    w.hdd_30yr_normal,
    CASE
        WHEN p.funding_source = 'DSM-Electric' AND w.weather_factor IS NOT NULL AND w.weather_factor > 0
            THEN ROUND(a.actual_gj / w.weather_factor, 3)
        ELSE a.actual_gj
    END AS actual_gj_wx_norm,
    CASE
        WHEN p.funding_source = 'DSM-Electric' AND w.weather_factor IS NOT NULL AND w.weather_factor > 0
            THEN ROUND(a.actual_gwh_electric / w.weather_factor, 4)
        ELSE a.actual_gwh_electric
    END AS actual_gwh_electric_wx_norm
FROM fact_actuals a
JOIN dim_program p ON a.program_id = p.program_id
LEFT JOIN dim_weather w ON a.year = w.year;

-- ============================================================
-- v_plan_vs_actual  (variance view used by Plan vs. Actual page)
-- ============================================================

CREATE VIEW IF NOT EXISTS v_plan_vs_actual AS
SELECT
    a.program_id,
    a.year,
    p.canonical_name,
    p.category,
    p.funding_source,
    p.is_low_income,
    t.plan_filing_id,
    -- Energy
    a.actual_gj,
    t.target_gj,
    ROUND(a.actual_gj - t.target_gj, 3)                    AS variance_gj,
    ROUND((a.actual_gj - t.target_gj) / NULLIF(t.target_gj, 0) * 100, 2) AS variance_pct,
    -- Demand
    a.actual_mw,
    t.target_mw,
    ROUND(a.actual_mw - t.target_mw, 3)                    AS variance_mw,
    -- Spend
    a.actual_spend_cad,
    t.target_spend_cad,
    ROUND(a.actual_spend_cad - t.target_spend_cad, 2)      AS variance_spend_cad,
    -- Cost effectiveness (actual $/GJ)
    ROUND(a.actual_spend_cad / NULLIF(a.actual_gj, 0), 2)  AS actual_cad_per_gj,
    -- Participants
    a.actual_participants,
    t.target_participants
FROM fact_actuals a
JOIN dim_program p ON a.program_id = p.program_id
LEFT JOIN fact_targets t
    ON a.program_id = t.program_id
    AND a.year = t.year;

-- ============================================================
-- v_equity  (low-income program summary by year)
-- ============================================================

CREATE VIEW IF NOT EXISTS v_equity AS
SELECT
    a.year,
    p.funding_source,
    SUM(a.actual_gj)            AS actual_gj_low_income,
    SUM(a.actual_spend_cad)     AS actual_spend_low_income,
    SUM(a.actual_participants)  AS actual_participants_low_income
FROM fact_actuals a
JOIN dim_program p ON a.program_id = p.program_id
WHERE p.is_low_income = 1
GROUP BY a.year, p.funding_source;

-- ============================================================
-- v_portfolio_totals  (executive summary totals by year)
-- ============================================================

CREATE VIEW IF NOT EXISTS v_portfolio_totals AS
SELECT
    a.year,
    SUM(a.actual_gj)            AS total_actual_gj,
    SUM(a.actual_gwh_electric)  AS total_actual_gwh_electric,
    SUM(a.actual_mw)            AS total_actual_mw,
    SUM(a.actual_tonnes_co2e)   AS total_actual_tonnes_co2e,
    SUM(a.actual_spend_cad)     AS total_actual_spend_cad,
    SUM(a.actual_participants)  AS total_actual_participants,
    SUM(t.target_gj)            AS total_target_gj,
    SUM(t.target_spend_cad)     AS total_target_spend_cad
FROM fact_actuals a
JOIN dim_program p ON a.program_id = p.program_id
LEFT JOIN fact_targets t
    ON a.program_id = t.program_id AND a.year = t.year
GROUP BY a.year;
