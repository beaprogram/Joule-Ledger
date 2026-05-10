-- Joule Ledger warehouse schema
-- Star schema: two fact tables, four dimension tables.
-- All energy in GJ, emissions in tonnes CO2e, currency in CAD.

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ============================================================
-- DIMENSIONS
-- ============================================================

CREATE TABLE IF NOT EXISTS dim_program (
    program_id          TEXT PRIMARY KEY,
    canonical_name      TEXT NOT NULL,
    prior_names         TEXT,           -- pipe-delimited list of historical names
    category            TEXT,           -- Residential | Commercial | Industrial | Low-Income | Other
    funding_source      TEXT,           -- DSM-Electric | Province | Federal
    is_low_income       INTEGER NOT NULL DEFAULT 0,  -- 1 = dedicated low-income program
    is_active           INTEGER NOT NULL DEFAULT 1,
    valid_from          TEXT,           -- first reporting year (ISO date or year string)
    valid_to            TEXT            -- NULL = still active
);

CREATE TABLE IF NOT EXISTS dim_year (
    year            INTEGER PRIMARY KEY,
    plan_period     TEXT,   -- e.g. "2020-2025"
    plan_filing_id  TEXT    -- e.g. "2020-2025", "2026-ext", "2027-2031"
);

CREATE TABLE IF NOT EXISTS dim_weather (
    year                INTEGER PRIMARY KEY,
    halifax_hdd_actual  REAL,   -- actual heating degree days (base 18°C)
    halifax_cdd_actual  REAL,   -- actual cooling degree days (base 18°C)
    hdd_30yr_normal     REAL,   -- 30-year HDD mean (1995–2024 baseline)
    weather_factor      REAL    -- halifax_hdd_actual / hdd_30yr_normal
);

CREATE TABLE IF NOT EXISTS dim_rate (
    year                            INTEGER PRIMARY KEY,
    residential_rate_cents_per_kwh  REAL
);

-- ============================================================
-- FACT TABLES
-- ============================================================

-- Granularity: one row per (program, year).
-- Measures represent delivered actuals from Annual Reports.
CREATE TABLE IF NOT EXISTS fact_actuals (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    program_id              TEXT NOT NULL REFERENCES dim_program(program_id),
    year                    INTEGER NOT NULL REFERENCES dim_year(year),
    actual_gj               REAL,
    actual_gwh_electric     REAL,
    actual_mw               REAL,
    actual_tonnes_co2e      REAL,
    actual_spend_cad        REAL,
    actual_participants     INTEGER,
    actual_lifetime_gj      REAL,       -- reported where available
    as_originally_reported  REAL,       -- GJ as first published
    as_restated             REAL,       -- GJ as corrected in a later report
    is_manually_entered     INTEGER NOT NULL DEFAULT 0,
    source_page             INTEGER,
    source_url              TEXT
);

-- Granularity: one row per (program, year, plan_filing).
-- A program may have targets from multiple overlapping plan filings.
CREATE TABLE IF NOT EXISTS fact_targets (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    program_id          TEXT NOT NULL REFERENCES dim_program(program_id),
    year                INTEGER NOT NULL REFERENCES dim_year(year),
    plan_filing_id      TEXT NOT NULL,
    target_gj           REAL,
    target_gwh_electric REAL,
    target_mw           REAL,
    target_tonnes_co2e  REAL,
    target_spend_cad    REAL,
    target_participants INTEGER,
    is_manually_entered INTEGER NOT NULL DEFAULT 0,
    source_page         INTEGER,
    source_path         TEXT
);

-- ============================================================
-- INDEXES
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_fact_actuals_program_year ON fact_actuals(program_id, year);
CREATE INDEX IF NOT EXISTS idx_fact_targets_program_year ON fact_targets(program_id, year);
CREATE INDEX IF NOT EXISTS idx_fact_targets_filing       ON fact_targets(plan_filing_id);
