"""Load reconciled interim data into the SQLite warehouse.

Runs sql/001_schema.sql then sql/002_views.sql, then populates all tables.

Input:   data/interim/actuals_reconciled.json
         data/interim/targets_reconciled.json
         data/raw/eccc_weather.json
         data/raw/nspower_rates.json
         sql/program_mapping.csv
Output:  data/warehouse.db
"""

from __future__ import annotations

import csv
import json
import logging
import pathlib
import sqlite3
from typing import Any

log = logging.getLogger(__name__)

INTERIM_DIR = pathlib.Path("data/interim")
RAW_DIR = pathlib.Path("data/raw")
SQL_DIR = pathlib.Path("sql")
DB_PATH = pathlib.Path("data/warehouse.db")
MAPPING_CSV = SQL_DIR / "program_mapping.csv"


def load_warehouse() -> None:
    if DB_PATH.exists():
        DB_PATH.unlink()

    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")

    _run_sql_file(con, SQL_DIR / "001_schema.sql")
    _load_dim_program(con)
    _load_dim_year(con)
    _load_dim_weather(con)
    _load_dim_rate(con)
    _load_fact_actuals(con)
    _load_fact_targets(con)
    _run_sql_file(con, SQL_DIR / "002_views.sql")

    con.commit()
    con.close()
    log.info("  load_warehouse — warehouse.db written to %s", DB_PATH)


def _run_sql_file(con: sqlite3.Connection, path: pathlib.Path) -> None:
    if not path.exists():
        log.warning("  load_warehouse — SQL file not found: %s", path)
        return
    con.executescript(path.read_text(encoding="utf-8"))
    log.info("  load_warehouse — executed %s", path.name)


def _load_dim_program(con: sqlite3.Connection) -> None:
    if not MAPPING_CSV.exists():
        log.warning("  load_warehouse — program_mapping.csv not found")
        return
    seen: set[str] = set()
    rows: list[tuple] = []
    with MAPPING_CSV.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            pid = row["program_id"].strip()
            if pid in seen:
                continue
            seen.add(pid)
            rows.append((
                pid,
                row["canonical_name"].strip(),
                row.get("prior_names", "").strip() or None,
                row.get("category", "").strip() or None,
                row.get("funding_source", "").strip() or None,
                1 if row.get("is_low_income", "0").strip() == "1" else 0,
                1 if row.get("is_active", "1").strip() == "1" else 0,
                row.get("valid_from", "").strip() or None,
                row.get("valid_to", "").strip() or None,
            ))
    con.executemany(
        """INSERT OR REPLACE INTO dim_program
           (program_id, canonical_name, prior_names, category,
            funding_source, is_low_income, is_active, valid_from, valid_to)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        rows,
    )
    log.info("  load_warehouse — dim_program: %d rows", len(rows))


def _load_dim_year(con: sqlite3.Connection) -> None:
    plan_periods = {
        2019: ("2020-2025", "2020-2025"),
        2020: ("2020-2025", "2020-2025"),
        2021: ("2020-2025", "2020-2025"),
        2022: ("2020-2025", "2020-2025"),
        2023: ("2020-2025", "2020-2025"),
        2024: ("2026-ext", "2026-ext"),
    }
    rows = [
        (yr, period[0], period[1])
        for yr, period in plan_periods.items()
    ]
    con.executemany(
        "INSERT OR REPLACE INTO dim_year (year, plan_period, plan_filing_id) VALUES (?,?,?)",
        rows,
    )
    log.info("  load_warehouse — dim_year: %d rows", len(rows))


def _load_dim_weather(con: sqlite3.Connection) -> None:
    path = RAW_DIR / "eccc_weather.json"
    if not path.exists():
        log.warning("  load_warehouse — eccc_weather.json not found")
        return
    records: list[dict] = json.loads(path.read_text())

    hdd_values = [r["halifax_hdd_actual"] for r in records if r["halifax_hdd_actual"]]
    hdd_30yr_normal = round(sum(hdd_values) / len(hdd_values), 1) if hdd_values else None

    rows = []
    for rec in records:
        hdd = rec.get("halifax_hdd_actual")
        factor = round(hdd / hdd_30yr_normal, 4) if hdd and hdd_30yr_normal else None
        rows.append((
            rec["year"],
            hdd,
            rec.get("halifax_cdd_actual"),
            hdd_30yr_normal,
            factor,
        ))
    con.executemany(
        """INSERT OR REPLACE INTO dim_weather
           (year, halifax_hdd_actual, halifax_cdd_actual, hdd_30yr_normal, weather_factor)
           VALUES (?,?,?,?,?)""",
        rows,
    )
    log.info("  load_warehouse — dim_weather: %d rows", len(rows))


def _load_dim_rate(con: sqlite3.Connection) -> None:
    path = RAW_DIR / "nspower_rates.json"
    if not path.exists():
        log.warning("  load_warehouse — nspower_rates.json not found")
        return
    records: list[dict] = json.loads(path.read_text())
    rows = [(r["year"], r.get("residential_rate_cents_per_kwh")) for r in records]
    con.executemany(
        "INSERT OR REPLACE INTO dim_rate (year, residential_rate_cents_per_kwh) VALUES (?,?)",
        rows,
    )
    log.info("  load_warehouse — dim_rate: %d rows", len(rows))


def _load_fact_actuals(con: sqlite3.Connection) -> None:
    path = INTERIM_DIR / "actuals_reconciled.json"
    if not path.exists():
        log.warning("  load_warehouse — actuals_reconciled.json not found")
        return
    records: list[dict[str, Any]] = json.loads(path.read_text())
    rows = [
        (
            rec.get("program_id", "__UNKNOWN__"),
            rec.get("year"),
            rec.get("actual_gj"),
            rec.get("actual_gwh_electric"),
            rec.get("actual_mw"),
            rec.get("actual_tonnes_co2e"),
            rec.get("actual_spend_cad"),
            rec.get("actual_participants"),
            rec.get("actual_lifetime_gj"),
            rec.get("as_originally_reported"),
            rec.get("as_restated"),
            rec.get("source_page"),
            rec.get("source_url", ""),
        )
        for rec in records
        if rec.get("program_name_raw") not in ("__FETCH_FAILED__", "__PDF_NOT_FOUND__")
        and rec.get("program_id") != "__UNKNOWN__"
    ]
    con.executemany(
        """INSERT INTO fact_actuals
           (program_id, year, actual_gj, actual_gwh_electric, actual_mw,
            actual_tonnes_co2e, actual_spend_cad, actual_participants,
            actual_lifetime_gj, as_originally_reported, as_restated,
            source_page, source_url)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        rows,
    )
    log.info("  load_warehouse — fact_actuals: %d rows", len(rows))


def _load_fact_targets(con: sqlite3.Connection) -> None:
    path = INTERIM_DIR / "targets_reconciled.json"
    if not path.exists():
        log.warning("  load_warehouse — targets_reconciled.json not found")
        return
    records: list[dict[str, Any]] = json.loads(path.read_text())
    rows = [
        (
            rec.get("program_id", "__UNKNOWN__"),
            rec.get("year") or rec.get("plan_year"),
            rec.get("plan_filing_id"),
            rec.get("target_gj"),
            rec.get("target_gwh_electric"),
            rec.get("target_mw"),
            rec.get("target_tonnes_co2e"),
            rec.get("target_spend_cad"),
            rec.get("target_participants"),
            1 if rec.get("is_manually_entered") else 0,
            rec.get("source_page"),
            rec.get("source_path", ""),
        )
        for rec in records
        if rec.get("program_name_raw") not in ("__PDF_NOT_FOUND__", "__FETCH_FAILED__")
        and rec.get("program_id") != "__UNKNOWN__"
    ]
    con.executemany(
        """INSERT INTO fact_targets
           (program_id, year, plan_filing_id, target_gj, target_gwh_electric,
            target_mw, target_tonnes_co2e, target_spend_cad, target_participants,
            is_manually_entered, source_page, source_path)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        rows,
    )
    log.info("  load_warehouse — fact_targets: %d rows", len(rows))
