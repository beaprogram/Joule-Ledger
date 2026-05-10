"""Load Nova Scotia Power historical residential rate schedule from manual CSV.

Source: NS Power public rate filings (manually transcribed).
Input:  data/raw/nspower_rates_manual.csv
Output: data/raw/nspower_rates.json

The CSV must have columns: year, residential_rate_cents_per_kwh
This source is manual-CSV only; no API fetch is performed.
"""

from __future__ import annotations

import csv
import json
import logging
import pathlib
from typing import Any

log = logging.getLogger(__name__)

RAW_DIR = pathlib.Path("data/raw")
MANUAL_CSV = RAW_DIR / "nspower_rates_manual.csv"


def extract_nspower_rates() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RAW_DIR / "nspower_rates.json"

    if not MANUAL_CSV.exists():
        log.warning(
            "  nspower_rates — %s not found; writing stub. "
            "Create the CSV with columns: year, residential_rate_cents_per_kwh",
            MANUAL_CSV,
        )
        _write_stub(out_path)
        return

    records: list[dict[str, Any]] = []
    with MANUAL_CSV.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            try:
                records.append(
                    {
                        "year": int(row["year"].strip()),
                        "residential_rate_cents_per_kwh": float(
                            row["residential_rate_cents_per_kwh"].strip()
                        ),
                    }
                )
            except (KeyError, ValueError) as exc:
                log.warning("  nspower_rates — skipping malformed row %r: %s", row, exc)

    out_path.write_text(json.dumps(records, indent=2, ensure_ascii=False))
    log.info("  nspower_rates — %d year rows written", len(records))


def _write_stub(out_path: pathlib.Path) -> None:
    stub = [
        {"year": y, "residential_rate_cents_per_kwh": None}
        for y in range(2019, 2025)
    ]
    out_path.write_text(json.dumps(stub, indent=2, ensure_ascii=False))
