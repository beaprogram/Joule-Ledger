"""Fetch Halifax heating- and cooling-degree-day data from Environment and Climate Change Canada.

Source: ECCC historical climate data API, Halifax Stanfield International Airport station.
Period: 1995–2024 (30-year baseline 1995–2024, plus 2019–2024 reporting period).
Output: data/raw/eccc_weather.json

Output record per year:
    {
        "year": int,
        "station_id": str,
        "station_name": str,
        "halifax_hdd_actual": float | null,   # heating degree days (base 18°C)
        "halifax_cdd_actual": float | null,   # cooling degree days (base 18°C)
        "source_url": str
    }

The 30-year HDD normal (hdd_30yr_normal) is derived in the transform layer
as mean(1995–2024) and stored in dim_weather.
"""

from __future__ import annotations

import json
import logging
import pathlib
from typing import Any

log = logging.getLogger(__name__)

RAW_DIR = pathlib.Path("data/raw")

# Halifax Stanfield Intl Airport
# Climate ID: 8202251  |  Numeric Station ID used in the API: 50620
STATION_ID = "50620"
CLIMATE_ID = "8202251"
STATION_NAME = "HALIFAX STANFIELD INT'L A"
BASE_YEAR = 1995
END_YEAR = 2024

# ECCC daily bulk data endpoint.
# timeframe=2 → daily.  Column names: "Heat Deg Days (°C)", "Cool Deg Days (°C)"
ECCC_API_TEMPLATE = (
    "https://climate.weather.gc.ca/climate_data/bulk_data_e.html"
    "?format=csv&stationID={station_id}&Year={year}&Month=1"
    "&Day=1&timeframe=2&submit=Download+Data"
)


def extract_eccc_weather() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RAW_DIR / "eccc_weather.json"
    if out_path.exists():
        log.info("  eccc_weather — cached, skipping fetch")
        return

    records: list[dict[str, Any]] = []
    for year in range(BASE_YEAR, END_YEAR + 1):
        url = ECCC_API_TEMPLATE.format(station_id=STATION_ID, year=year)
        log.info("  eccc_weather %d — fetching", year)
        rec = _fetch_year(year, url)
        records.append(rec)

    out_path.write_text(json.dumps(records, indent=2, ensure_ascii=False))
    log.info("  eccc_weather — %d years written", len(records))


def _fetch_year(year: int, url: str) -> dict[str, Any]:
    try:
        import io
        import requests
        import csv

        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        text = resp.text

        hdd_total = 0.0
        cdd_total = 0.0
        rows_parsed = 0

        reader = csv.DictReader(io.StringIO(text))
        for row in reader:
            hdd_val = _float_or_none(row.get("Heat Deg Days (°C)", ""))
            cdd_val = _float_or_none(row.get("Cool Deg Days (°C)", ""))
            if hdd_val is not None:
                hdd_total += hdd_val
                rows_parsed += 1
            if cdd_val is not None:
                cdd_total += cdd_val

        return {
            "year": year,
            "station_id": STATION_ID,
            "station_name": STATION_NAME,
            "halifax_hdd_actual": round(hdd_total, 1) if rows_parsed > 0 else None,
            "halifax_cdd_actual": round(cdd_total, 1) if rows_parsed > 0 else None,
            "source_url": url,
        }
    except Exception as exc:
        log.warning("  eccc_weather %d — fetch failed (%s)", year, exc)
        return {
            "year": year,
            "station_id": STATION_ID,
            "station_name": STATION_NAME,
            "halifax_hdd_actual": None,
            "halifax_cdd_actual": None,
            "source_url": url,
        }


def _float_or_none(val: str) -> float | None:
    try:
        return float(val.strip())
    except (ValueError, AttributeError):
        return None
