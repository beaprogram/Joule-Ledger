"""Extract forecasted DSM Plan targets from Nova Scotia Energy Board public docket PDFs.

Sources:
    - 2020–2025 DSM Plans (PDF)
    - 2026 Extension Application filed April 2025 (PDF)
    - 2027–2031 DSM Plan filed April 2026 (PDF)

Output: data/raw/dsm_plans_{filing_id}.json  (one file per plan filing)

Each output record:
    {
        "plan_filing_id": str,          # e.g. "2020-2025", "2026-ext", "2027-2031"
        "plan_year": int,               # the year this row's target applies to
        "program_name_raw": str,
        "target_gj": float | null,
        "target_gwh_electric": float | null,
        "target_mw": float | null,
        "target_tonnes_co2e": float | null,
        "target_spend_cad": float | null,
        "target_participants": int | null,
        "is_manually_entered": bool,
        "source_page": int | null,
        "source_path": str
    }

NOTE: Roughly 6% of cells in fact_targets are entered by hand because DSM Plan
tables resist reliable PDF parsing. These are flagged via is_manually_entered = True.
"""

from __future__ import annotations

import json
import logging
import pathlib
from typing import Any

log = logging.getLogger(__name__)

RAW_DIR = pathlib.Path("data/raw")

# Local paths to DSM Plan PDFs downloaded from the NS Energy Board public docket.
# Commit PDFs alongside raw JSON for auditability.
DSM_PLAN_PDFS: dict[str, pathlib.Path] = {
    "2020-2025": RAW_DIR / "dsm_plans" / "DSM_Plan_2020-2025.pdf",
    "2026-ext": RAW_DIR / "dsm_plans" / "DSM_Plan_2026_Extension.pdf",
    "2027-2031": RAW_DIR / "dsm_plans" / "DSM_Plan_2027-2031.pdf",
}


def extract_dsm_plans() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    (RAW_DIR / "dsm_plans").mkdir(exist_ok=True)

    for filing_id, pdf_path in DSM_PLAN_PDFS.items():
        out_path = RAW_DIR / f"dsm_plans_{filing_id}.json"
        if out_path.exists():
            log.info("  dsm_plans %s — cached, skipping parse", filing_id)
            continue
        if not pdf_path.exists():
            log.warning(
                "  dsm_plans %s — PDF not found at %s; writing stub. "
                "Download from NS Energy Board public docket and place at that path.",
                filing_id,
                pdf_path,
            )
            records = _stub_records(filing_id, str(pdf_path))
        else:
            log.info("  dsm_plans %s — parsing %s", filing_id, pdf_path)
            records = _parse_pdf(filing_id, pdf_path)
        out_path.write_text(json.dumps(records, indent=2, ensure_ascii=False))
        log.info("  dsm_plans %s — %d rows written", filing_id, len(records))


def _parse_pdf(filing_id: str, pdf_path: pathlib.Path) -> list[dict[str, Any]]:
    try:
        import pdfplumber
    except ImportError:
        log.error("pdfplumber not installed — run: pip install pdfplumber")
        return _stub_records(filing_id, str(pdf_path))

    records: list[dict[str, Any]] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables()
            for table in tables:
                if not table or len(table) < 2:
                    continue
                headers = [str(c).lower().strip() if c else "" for c in table[0]]
                if not any("program" in h or "gj" in h or "target" in h for h in headers):
                    continue
                for row in table[1:]:
                    if not row or not any(row):
                        continue
                    rec = _row_to_record(filing_id, headers, row, page_num, str(pdf_path))
                    if rec:
                        records.append(rec)
    return records


def _row_to_record(
    filing_id: str,
    headers: list[str],
    cells: list[Any],
    page_num: int,
    source_path: str,
) -> dict[str, Any] | None:
    def _float(val: Any) -> float | None:
        if val is None:
            return None
        cleaned = str(val).replace(",", "").replace("$", "").strip()
        try:
            return float(cleaned)
        except ValueError:
            return None

    def _int(val: Any) -> int | None:
        if val is None:
            return None
        cleaned = str(val).replace(",", "").strip()
        try:
            return int(float(cleaned))
        except ValueError:
            return None

    col = {h: cells[i] if i < len(cells) else None for i, h in enumerate(headers)}
    name_raw = str(cells[0]).strip() if cells and cells[0] else None
    if not name_raw:
        return None

    plan_year = _infer_plan_year(filing_id, col)

    return {
        "plan_filing_id": filing_id,
        "plan_year": plan_year,
        "program_name_raw": name_raw,
        "target_gj": _float(col.get("gj", col.get("energy savings (gj)", col.get("target gj")))),
        "target_gwh_electric": _float(col.get("gwh", col.get("gwh electric"))),
        "target_mw": _float(col.get("mw", col.get("demand savings (mw)"))),
        "target_tonnes_co2e": _float(col.get("tco2e", col.get("ghg reductions"))),
        "target_spend_cad": _float(col.get("spend", col.get("budget", col.get("expenditure")))),
        "target_participants": _int(col.get("participants")),
        "is_manually_entered": False,
        "source_page": page_num,
        "source_path": source_path,
    }


def _infer_plan_year(filing_id: str, col: dict) -> int | None:
    for key in col:
        if "year" in key or "plan year" in key:
            try:
                return int(str(col[key]).strip())
            except (ValueError, TypeError):
                pass
    return None


def _stub_records(filing_id: str, source_path: str) -> list[dict[str, Any]]:
    return [
        {
            "plan_filing_id": filing_id,
            "plan_year": None,
            "program_name_raw": "__PDF_NOT_FOUND__",
            "target_gj": None,
            "target_gwh_electric": None,
            "target_mw": None,
            "target_tonnes_co2e": None,
            "target_spend_cad": None,
            "target_participants": None,
            "is_manually_entered": False,
            "source_page": None,
            "source_path": source_path,
        }
    ]
