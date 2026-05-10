"""Map raw program names to canonical program IDs via program_mapping.csv.

Unknowns are flagged rather than silently dropped.

Input:   data/interim/actuals_conformed.json
         data/interim/targets_conformed.json
         sql/program_mapping.csv
Output:  data/interim/actuals_reconciled.json
         data/interim/targets_reconciled.json
"""

from __future__ import annotations

import csv
import json
import logging
import pathlib
from typing import Any

log = logging.getLogger(__name__)

INTERIM_DIR = pathlib.Path("data/interim")
MAPPING_CSV = pathlib.Path("sql/program_mapping.csv")


def reconcile_programs() -> None:
    mapping = _load_mapping()
    _reconcile("actuals_conformed.json", "actuals_reconciled.json", mapping)
    _reconcile("targets_conformed.json", "targets_reconciled.json", mapping)


def _normalize(name: str) -> str:
    """Normalise apostrophes and whitespace for fuzzy-key matching."""
    # Replace curly/typographic apostrophes with straight ASCII apostrophe
    return name.replace("’", "'").replace("‘", "'").strip().lower()


def _load_mapping() -> dict[str, dict[str, Any]]:
    """Return {raw_name_lower: {program_id, canonical_name, ...}}."""
    if not MAPPING_CSV.exists():
        log.error("program_mapping.csv not found at %s", MAPPING_CSV)
        return {}
    mapping: dict[str, dict[str, Any]] = {}
    with MAPPING_CSV.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            raw_names = row.get("raw_name_variants", "").split("|")
            for raw in raw_names:
                key = _normalize(raw)
                if key:
                    mapping[key] = {
                        "program_id": row["program_id"].strip(),
                        "canonical_name": row["canonical_name"].strip(),
                        "category": row.get("category", "").strip(),
                        "funding_source": row.get("funding_source", "").strip(),
                        "is_low_income": row.get("is_low_income", "0").strip() == "1",
                        "is_active": row.get("is_active", "1").strip() == "1",
                        "valid_from": row.get("valid_from", "").strip() or None,
                        "valid_to": row.get("valid_to", "").strip() or None,
                    }
    log.info("  reconcile_programs — loaded %d name variants", len(mapping))
    return mapping


def _reconcile(
    in_filename: str, out_filename: str, mapping: dict[str, dict[str, Any]]
) -> None:
    in_path = INTERIM_DIR / in_filename
    if not in_path.exists():
        log.warning("  reconcile_programs — %s not found, skipping", in_path)
        return

    records = json.loads(in_path.read_text())
    unmatched: set[str] = set()
    out_records: list[dict[str, Any]] = []

    for rec in records:
        raw = rec.get("program_name_raw", "")
        key = _normalize(raw)
        match = mapping.get(key)
        if match:
            out_records.append({**rec, **match})
        else:
            unmatched.add(raw)
            out_records.append({
                **rec,
                "program_id": "__UNKNOWN__",
                "canonical_name": raw,
                "category": None,
                "funding_source": None,
                "is_low_income": False,
                "is_active": None,
                "valid_from": None,
                "valid_to": None,
            })

    if unmatched:
        log.warning(
            "  reconcile_programs — %d unmatched program names in %s: %s",
            len(unmatched),
            in_filename,
            sorted(unmatched),
        )

    (INTERIM_DIR / out_filename).write_text(
        json.dumps(out_records, indent=2, ensure_ascii=False)
    )
    log.info(
        "  reconcile_programs — %s: %d rows, %d unmatched",
        out_filename,
        len(out_records),
        len(unmatched),
    )
