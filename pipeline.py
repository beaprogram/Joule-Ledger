"""Single-entry ETL runner for Joule Ledger.

Usage:
    python pipeline.py --refresh         # full end-to-end run
    python pipeline.py --extract annual_reports
    python pipeline.py --extract dsm_plans
    python pipeline.py --transform
    python pipeline.py --validate
"""

import argparse
import sys
import logging

from extractors.annual_reports import extract_annual_reports
from extractors.dsm_plans import extract_dsm_plans
from extractors.eccc_weather import extract_eccc_weather
from extractors.nspower_rates import extract_nspower_rates
from transforms.conform_units import conform_units
from transforms.reconcile_programs import reconcile_programs
from transforms.load_warehouse import load_warehouse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


def run_extract(source: str | None = None) -> None:
    sources = {
        "annual_reports": extract_annual_reports,
        "dsm_plans": extract_dsm_plans,
        "eccc_weather": extract_eccc_weather,
        "nspower_rates": extract_nspower_rates,
    }
    if source:
        if source not in sources:
            log.error("Unknown source %r. Choose from: %s", source, ", ".join(sources))
            sys.exit(1)
        log.info("Extracting %s …", source)
        sources[source]()
    else:
        for name, fn in sources.items():
            log.info("Extracting %s …", name)
            fn()


def run_transform() -> None:
    log.info("Conforming units …")
    conform_units()
    log.info("Reconciling programs …")
    reconcile_programs()
    log.info("Loading warehouse …")
    load_warehouse()


def run_validate() -> None:
    import sqlite3
    import pathlib

    db_path = pathlib.Path("data/warehouse.db")
    if not db_path.exists():
        log.error("warehouse.db not found — run --transform first.")
        sys.exit(1)

    con = sqlite3.connect(db_path)
    failures: list[str] = []

    checks = [
        _check_energy_metrics,
        _check_no_nulls,
        _check_program_ids,
        _check_no_exact_duplicate_facts,
        _check_active_programs_open,
    ]
    for check in checks:
        result = check(con)
        status = "PASS" if result["pass"] else "FAIL"
        log.info("[%s] %s", status, result["name"])
        if result.get("detail"):
            log.info("       %s", result["detail"])
        if not result["pass"]:
            failures.append(result["name"])

    con.close()
    if failures:
        log.error("%d check(s) failed: %s", len(failures), failures)
        sys.exit(1)
    log.info("All validation checks passed.")


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _check_energy_metrics(con) -> dict:
    row_count, year_count = con.execute(
        "SELECT COUNT(*), COUNT(DISTINCT year) FROM fact_actuals"
    ).fetchone()
    empty_metrics = con.execute(
        """
        SELECT COUNT(*)
        FROM fact_actuals
        WHERE actual_gj IS NULL
          AND actual_gwh_electric IS NULL
          AND actual_mw IS NULL
          AND actual_tonnes_co2e IS NULL
        """
    ).fetchone()[0]
    negative_metrics = con.execute(
        """
        SELECT COUNT(*)
        FROM fact_actuals
        WHERE COALESCE(actual_gj, 0) < 0
           OR COALESCE(actual_gwh_electric, 0) < 0
           OR COALESCE(actual_mw, 0) < 0
           OR COALESCE(actual_tonnes_co2e, 0) < 0
        """
    ).fetchone()[0]
    passed = row_count > 0 and empty_metrics == 0 and negative_metrics == 0
    return {
        "name": "Loaded actuals contain valid, non-negative energy metrics",
        "pass": passed,
        "detail": (
            f"{row_count} rows across {year_count} years; "
            f"{empty_metrics} rows without energy metrics; "
            f"{negative_metrics} rows with negative metrics"
        ),
    }


def _check_no_nulls(con) -> dict:
    # actual_participants and actual_spend_cad are not reported in Annual Report
    # tables, so they are legitimately NULL. Only check the core energy metric.
    measured = [("fact_actuals", "actual_gj")]
    target_rows = con.execute("SELECT COUNT(*) FROM fact_targets").fetchone()[0]
    if target_rows:
        measured.append(("fact_targets", "target_gj"))
    bad = []
    for table, col in measured:
        count = con.execute(
            f"SELECT COUNT(*) FROM {table} WHERE {col} IS NULL AND is_manually_entered = 0"
        ).fetchone()[0]
        if count:
            bad.append(f"{table}.{col}: {count} nulls")
    return {
        "name": "No unexpected nulls in fact table measured columns",
        "pass": len(bad) == 0,
        "detail": "; ".join(bad) if bad else None,
    }


def _check_program_ids(con) -> dict:
    orphans = con.execute(
        """
        SELECT COUNT(*) FROM (
            SELECT program_id FROM fact_actuals
            UNION ALL
            SELECT program_id FROM fact_targets
        ) f
        LEFT JOIN dim_program p USING (program_id)
        WHERE p.program_id IS NULL
        """
    ).fetchone()[0]
    return {
        "name": "Every fact row has a valid program_id in dim_program",
        "pass": orphans == 0,
        "detail": f"{orphans} orphaned program_ids" if orphans else None,
    }


def _check_no_exact_duplicate_facts(con) -> dict:
    duplicate_actuals = con.execute(
        """
        SELECT COUNT(*) FROM (
            SELECT
                program_id,
                year,
                actual_gj,
                actual_gwh_electric,
                actual_mw,
                actual_tonnes_co2e,
                actual_spend_cad,
                actual_participants,
                source_page,
                source_url
            FROM fact_actuals
            GROUP BY
                program_id,
                year,
                actual_gj,
                actual_gwh_electric,
                actual_mw,
                actual_tonnes_co2e,
                actual_spend_cad,
                actual_participants,
                source_page,
                source_url
            HAVING COUNT(*) > 1
        )
        """
    ).fetchone()[0]
    duplicate_targets = con.execute(
        """
        SELECT COUNT(*) FROM (
            SELECT program_id, year, plan_filing_id
            FROM fact_targets
            GROUP BY program_id, year, plan_filing_id
            HAVING COUNT(*) > 1
        )
        """
    ).fetchone()[0]
    return {
        "name": "No exact duplicate fact records exist",
        "pass": duplicate_actuals == 0 and duplicate_targets == 0,
        "detail": (
            f"{duplicate_actuals} duplicate actual groups; "
            f"{duplicate_targets} duplicate target groups"
        ),
    }


def _check_active_programs_open(con) -> dict:
    bad = con.execute(
        """
        SELECT COUNT(*) FROM dim_program
        WHERE is_active = 1 AND valid_to IS NOT NULL
        """
    ).fetchone()[0]
    return {
        "name": "Every active program has valid_to = NULL in program_mapping",
        "pass": bad == 0,
        "detail": f"{bad} active programs with closed valid_to" if bad else None,
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Joule Ledger ETL pipeline")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--refresh",
        action="store_true",
        help="Full end-to-end run (extract all → transform → validate)",
    )
    group.add_argument(
        "--extract",
        metavar="SOURCE",
        nargs="?",
        const="__all__",
        help="Extract one source (annual_reports | dsm_plans | eccc_weather | nspower_rates) or all",
    )
    group.add_argument(
        "--transform",
        action="store_true",
        help="Rebuild the warehouse from interim files",
    )
    group.add_argument(
        "--validate",
        action="store_true",
        help="Run data-quality checks",
    )
    args = parser.parse_args()

    if args.refresh:
        run_extract()
        run_transform()
        run_validate()
    elif args.extract:
        run_extract(None if args.extract == "__all__" else args.extract)
    elif args.transform:
        run_transform()
    elif args.validate:
        run_validate()


if __name__ == "__main__":
    main()
