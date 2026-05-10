"""Extract actual savings data from EfficiencyOne Annual Reports.

Sources:
    PDFs downloaded from the EfficiencyOne website (2022–2024 available directly;
    2019–2021 must be placed manually — see NOTE below).

PDF layout (consistent across 2022–2024):
    Electric programs table  → Program | GWh | GHG (tonnes)
    Non-electric table       → Program | GJ  | GHG (tonnes)
    Portfolio totals row     → Total GWh, Total MW demand savings

Output: data/raw/annual_reports_{year}.json  (one file per year)

NOTE: 2019–2021 Annual Report PDFs must be manually placed at:
    data/raw/annual_reports/annual_report_2019.pdf
    data/raw/annual_reports/annual_report_2020.pdf
    data/raw/annual_reports/annual_report_2021.pdf
"""

from __future__ import annotations

import json
import logging
import pathlib
import re
from typing import Any

log = logging.getLogger(__name__)

RAW_DIR = pathlib.Path("data/raw")
PDF_DIR = RAW_DIR / "annual_reports"

# Direct PDF links for the years that are publicly available.
PDF_URLS: dict[int, str] = {
    2022: (
        "https://ens-efficiency-one-prod-offload-647701102377-ca-central-1"
        ".s3.ca-central-1.amazonaws.com/wp-content/uploads/2023/08/24120402"
        "/EfficiencyOne-2022-Annual-Report.pdf"
    ),
    2023: (
        "https://ens-efficiency-one-prod-offload-647701102377-ca-central-1"
        ".s3.ca-central-1.amazonaws.com/wp-content/uploads/2024/05/01153926"
        "/2023-Annual-Report.pdf"
    ),
    2024: (
        "https://ens-efficiency-one-prod-offload-647701102377-ca-central-1"
        ".s3.ca-central-1.amazonaws.com/wp-content/uploads/2025/04/23161459"
        "/2024-EfficiencyOne-Annual-Report.pdf"
    ),
}

# Years that need manual PDF placement
MANUAL_YEARS = {2019, 2020, 2021}

ALL_YEARS = sorted(MANUAL_YEARS | set(PDF_URLS))


def extract_annual_reports() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PDF_DIR.mkdir(parents=True, exist_ok=True)

    for year in ALL_YEARS:
        out_path = RAW_DIR / f"annual_reports_{year}.json"
        if out_path.exists():
            log.info("  annual_reports %d — cached, skipping", year)
            continue

        pdf_path = PDF_DIR / f"annual_report_{year}.pdf"

        if not pdf_path.exists():
            if year in PDF_URLS:
                _download_pdf(year, PDF_URLS[year], pdf_path)
            else:
                log.warning(
                    "  annual_reports %d — PDF not found at %s. "
                    "Download and place it there manually.",
                    year, pdf_path,
                )
                records = _stub_records(year, str(pdf_path))
                out_path.write_text(json.dumps(records, indent=2, ensure_ascii=False))
                continue

        log.info("  annual_reports %d — parsing %s", year, pdf_path.name)
        records = _parse_pdf(year, pdf_path)
        out_path.write_text(json.dumps(records, indent=2, ensure_ascii=False))
        log.info("  annual_reports %d — %d program rows written", year, len(records))


def _download_pdf(year: int, url: str, dest: pathlib.Path) -> None:
    try:
        import requests
        log.info("  annual_reports %d — downloading PDF", year)
        resp = requests.get(url, timeout=120, stream=True)
        resp.raise_for_status()
        dest.write_bytes(resp.content)
        log.info("  annual_reports %d — PDF saved (%d KB)", year, dest.stat().st_size // 1024)
    except Exception as exc:
        log.error("  annual_reports %d — download failed: %s", year, exc)


def _parse_pdf(year: int, pdf_path: pathlib.Path) -> list[dict[str, Any]]:
    try:
        import pdfplumber
    except ImportError:
        log.error("pdfplumber not installed — run: pip install pdfplumber")
        return _stub_records(year, str(pdf_path))

    records: list[dict[str, Any]] = []
    portfolio_gwh: float | None = None
    portfolio_mw: float | None = None

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables()
            for table in tables:
                if not table or len(table) < 2:
                    continue

                header = [str(c or "").replace("\n", " ").strip().upper() for c in table[0]]

                # ── Electric savings table ───────────────────────────────────
                # Header pattern: [sector/program, "ELECTRICAL SAVINGS (GWH)", "GHG SAVINGS (TONNES)"]
                if _is_electric_table(header):
                    for row in table[1:]:
                        name = _cell(row, 0)
                        if not name or _is_subtotal_row(name):
                            # Check if this is the portfolio total row
                            gwh_val = _floatval(_cell(row, 1))
                            if gwh_val and gwh_val > 50:  # portfolio totals are large
                                portfolio_gwh = gwh_val
                            continue
                        gwh = _floatval(_cell(row, 1))
                        ghg = _floatval(_cell(row, 2))
                        if gwh is not None:
                            records.append(_make_record(
                                year=year,
                                name=name,
                                actual_gwh_electric=gwh,
                                actual_gj=None,   # derived in conform_units
                                actual_mw=None,
                                actual_tonnes_co2e=ghg,
                                source_page=page_num,
                                source_path=str(pdf_path),
                            ))

                # ── Non-electric savings table ────────────────────────────────
                # Header pattern: [program, "ENERGY SAVINGS (GJ)", "GHG SAVINGS (TONNES)"]
                # Note: 2023 has a 5-col layout with blank cols between GJ and GHG.
                elif _is_nonelectric_table(header):
                    for row in table[1:]:
                        name = _cell(row, 0)
                        if not name or _is_subtotal_row(name):
                            continue
                        # find the two numeric columns regardless of blank spacers
                        num_cols = _find_numeric_cols(row)
                        gj = _floatval(_cell(row, num_cols[0])) if len(num_cols) >= 1 else None
                        ghg = _floatval(_cell(row, num_cols[1])) if len(num_cols) >= 2 else None
                        if gj is not None:
                            records.append(_make_record(
                                year=year,
                                name=name,
                                actual_gwh_electric=None,
                                actual_gj=gj,
                                actual_mw=None,
                                actual_tonnes_co2e=ghg,
                                source_page=page_num,
                                source_path=str(pdf_path),
                            ))

                # ── Portfolio totals row (demand savings MW) ──────────────────
                for row in table:
                    row_text = " ".join(str(c or "") for c in row).upper()
                    if "TOTAL DEMAND" in row_text or "DEMAND SAVINGS" in row_text:
                        for cell in row:
                            v = _floatval(str(cell or ""))
                            if v is not None and 5 <= v <= 200:
                                portfolio_mw = v
                    if "TOTAL SAVINGS" in row_text and "GWH" not in row_text:
                        for cell in row:
                            v = _floatval(str(cell or ""))
                            if v is not None and 50 <= v <= 1000:
                                portfolio_gwh = portfolio_gwh or v

    # Attach portfolio MW to the first electric record for the year
    # (used by the v_portfolio_totals view)
    if portfolio_mw and records:
        records[0]["_portfolio_mw"] = portfolio_mw
    if portfolio_gwh and records:
        records[0]["_portfolio_gwh"] = portfolio_gwh

    return records


# ── Helpers ─────────────────────────────────────────────────────────────────

# Exact sector header strings that appear as the first cell of a table row and
# should be skipped — they are category labels, not program names.
_SECTOR_HEADERS = frozenset({
    "RESIDENTIAL",
    "INDUSTRIAL",
    "COMMERCIAL",
    "OTHER",
    "OTHER PROGRAMS",
    "SAVINGS FROM OTHER PROGRAMS",
    "NON-ELECTRIC SAVINGS FROM PROGRAMS",
    # multi-line variants normalised with single spaces:
    "BUSINESS, NON-PROFIT & INSTITUTIONAL",
    "BUSINESS, NON-PROFIT & INSTITUTIONAL SUBTOTAL",
})


def _is_electric_table(header: list[str]) -> bool:
    # 2023 PDF has "EL ECTRICAL" (split across text runs) so check for GWH only
    joined = " ".join(header)
    return "GWH" in joined


def _is_nonelectric_table(header: list[str]) -> bool:
    joined = " ".join(header)
    return ("ENERGY" in joined or "NON-ELECTRIC" in joined) and "GJ" in joined and "GWH" not in joined


def _is_subtotal_row(name: str) -> bool:
    n = name.strip().upper()
    if len(n) <= 2:                     # single-char remnants ("T", "S")
        return True
    if n in _SECTOR_HEADERS:
        return True
    if "SUBTOTAL" in n:
        return True
    if n.startswith("TOTAL "):
        return True
    return False


def _cell(row: list, idx: int) -> str:
    try:
        return str(row[idx] or "").replace("\n", " ").strip()
    except IndexError:
        return ""


def _floatval(s: str) -> float | None:
    cleaned = re.sub(r"[,$\s]", "", s)
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return None


def _find_numeric_cols(row: list) -> list[int]:
    """Return indices (after col 0) of cells that parse as numbers."""
    return [i for i in range(1, len(row)) if _floatval(_cell(row, i)) is not None]


def _find_gj_col(row: list) -> int | None:
    cols = _find_numeric_cols(row)
    return cols[0] if cols else None

def _make_record(
    year: int,
    name: str,
    actual_gwh_electric: float | None,
    actual_gj: float | None,
    actual_mw: float | None,
    actual_tonnes_co2e: float | None,
    source_page: int,
    source_path: str,
) -> dict[str, Any]:
    return {
        "year": year,
        "program_name_raw": name,
        "actual_gj": actual_gj,
        "actual_gwh_electric": actual_gwh_electric,
        "actual_mw": actual_mw,
        "actual_tonnes_co2e": actual_tonnes_co2e,
        "actual_spend_cad": None,
        "actual_participants": None,
        "actual_lifetime_gj": None,
        "as_originally_reported": None,
        "as_restated": None,
        "source_page": source_page,
        "source_url": source_path,
    }

def _stub_records(year: int, source: str) -> list[dict[str, Any]]:
    return [{
        "year": year,
        "program_name_raw": "__PDF_NOT_FOUND__",
        "actual_gj": None,
        "actual_gwh_electric": None,
        "actual_mw": None,
        "actual_tonnes_co2e": None,
        "actual_spend_cad": None,
        "actual_participants": None,
        "actual_lifetime_gj": None,
        "as_originally_reported": None,
        "as_restated": None,
        "source_page": None,
        "source_url": source,
    }]
