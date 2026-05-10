"""Conform all raw extract values to canonical units and write interim files.

Canonical units:
    Energy      → GJ   (gigajoules).  1 GWh = 3.6 GJ.
    Emissions   → tonnes CO2e.
    Currency    → CAD (nominal year dollars, as reported).
    Demand      → MW.
    Participants → integer count.

Input:   data/raw/annual_reports_{year}.json
         data/raw/dsm_plans_{filing_id}.json
Output:  data/interim/actuals_conformed.json
         data/interim/targets_conformed.json
"""

from __future__ import annotations

import json
import logging
import pathlib
from typing import Any

log = logging.getLogger(__name__)

RAW_DIR = pathlib.Path("data/raw")
INTERIM_DIR = pathlib.Path("data/interim")

GWH_TO_GJ = 3.6


def conform_units() -> None:
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    _conform_actuals()
    _conform_targets()


def _conform_actuals() -> None:
    all_records: list[dict[str, Any]] = []
    for path in sorted(RAW_DIR.glob("annual_reports_*.json")):
        records = json.loads(path.read_text())
        for rec in records:
            all_records.append(_conform_actual_record(rec))
    out = INTERIM_DIR / "actuals_conformed.json"
    out.write_text(json.dumps(all_records, indent=2, ensure_ascii=False))
    log.info("  conform_units — actuals: %d rows", len(all_records))


def _conform_targets() -> None:
    all_records: list[dict[str, Any]] = []
    for path in sorted(RAW_DIR.glob("dsm_plans_*.json")):
        records = json.loads(path.read_text())
        for rec in records:
            all_records.append(_conform_target_record(rec))
    out = INTERIM_DIR / "targets_conformed.json"
    out.write_text(json.dumps(all_records, indent=2, ensure_ascii=False))
    log.info("  conform_units — targets: %d rows", len(all_records))


def _conform_actual_record(rec: dict[str, Any]) -> dict[str, Any]:
    gwh = rec.get("actual_gwh_electric")
    gj = rec.get("actual_gj")

    # If only GWh is present, derive GJ; if both present, keep as-is (GJ is authoritative).
    if gj is None and gwh is not None:
        gj = round(gwh * GWH_TO_GJ, 3)

    # Carry both as_originally_reported and as_restated; default display uses as_restated.
    as_restated = rec.get("as_restated") or gj
    as_originally = rec.get("as_originally_reported") or gj

    return {
        **rec,
        "actual_gj": gj,
        "as_originally_reported": as_originally,
        "as_restated": as_restated,
    }


def _conform_target_record(rec: dict[str, Any]) -> dict[str, Any]:
    gwh = rec.get("target_gwh_electric")
    gj = rec.get("target_gj")
    if gj is None and gwh is not None:
        gj = round(gwh * GWH_TO_GJ, 3)
    return {**rec, "target_gj": gj}
