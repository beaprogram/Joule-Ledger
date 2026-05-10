"""Tests for extractor modules.

These tests operate on fixture data rather than making live HTTP requests.
Run with: pytest tests/test_extractors.py
"""

import json
import pathlib
import tempfile
import pytest


# ---------------------------------------------------------------------------
# annual_reports extractor
# ---------------------------------------------------------------------------

class TestAnnualReportsExtractor:
    def test_stub_records_have_required_keys(self):
        from extractors.annual_reports import _stub_records

        records = _stub_records(2024, "https://example.com/report")
        assert len(records) == 1
        rec = records[0]
        required = {
            "year", "program_name_raw", "actual_gj", "actual_gwh_electric",
            "actual_mw", "actual_tonnes_co2e", "actual_spend_cad",
            "actual_participants", "actual_lifetime_gj",
            "as_originally_reported", "as_restated", "source_page", "source_url",
        }
        assert required.issubset(rec.keys())

    def test_stub_year_matches(self):
        from extractors.annual_reports import _stub_records

        records = _stub_records(2021, "https://example.com")
        assert records[0]["year"] == 2021

    def test_floatval_parses_formatted_numbers(self):
        from extractors.annual_reports import _floatval

        assert _floatval("1,234.5") == pytest.approx(1234.5)
        assert _floatval("342.9") == pytest.approx(342.9)
        assert _floatval("172") == pytest.approx(172.0)

    def test_floatval_handles_non_numeric(self):
        from extractors.annual_reports import _floatval

        assert _floatval("N/A") is None
        assert _floatval("—") is None
        assert _floatval("M") is None
        assert _floatval("") is None

    def test_make_record_structure(self):
        from extractors.annual_reports import _make_record

        rec = _make_record(
            year=2024,
            name="Home Energy Assessment",
            actual_gwh_electric=32.0,
            actual_gj=None,
            actual_mw=None,
            actual_tonnes_co2e=18408.0,
            source_page=11,
            source_path="data/raw/annual_reports/annual_report_2024.pdf",
        )
        assert rec["year"] == 2024
        assert rec["program_name_raw"] == "Home Energy Assessment"
        assert rec["actual_gwh_electric"] == 32.0
        assert rec["actual_tonnes_co2e"] == 18408.0
        assert rec["actual_gj"] is None

    def test_is_subtotal_row_filters_correctly(self):
        from extractors.annual_reports import _is_subtotal_row

        assert _is_subtotal_row("RESIDENTIAL") is True
        assert _is_subtotal_row("BUSINESS, NON-PROFIT & INSTITUTIONAL") is True
        assert _is_subtotal_row("BUSINESS, NON-PROFIT & INSTITUTIONAL SUBTOTAL") is True
        assert _is_subtotal_row("T") is True
        # These are program names and must NOT be filtered
        assert _is_subtotal_row("Business Energy Rebates") is False
        assert _is_subtotal_row("Affordable Multifamily Housing and Non-Profits") is False
        assert _is_subtotal_row("Small Business Energy Solutions") is False
        assert _is_subtotal_row("HomeWarming") is False


# ---------------------------------------------------------------------------
# nspower_rates extractor
# ---------------------------------------------------------------------------

class TestNSPowerRatesExtractor:
    def test_stub_written_when_csv_missing(self, tmp_path, monkeypatch):
        import extractors.nspower_rates as mod

        monkeypatch.setattr(mod, "RAW_DIR", tmp_path)
        monkeypatch.setattr(mod, "MANUAL_CSV", tmp_path / "nonexistent.csv")

        mod.extract_nspower_rates()

        out = tmp_path / "nspower_rates.json"
        assert out.exists()
        records = json.loads(out.read_text())
        assert len(records) == 6  # 2019–2024
        assert all(r["residential_rate_cents_per_kwh"] is None for r in records)

    def test_reads_valid_csv(self, tmp_path, monkeypatch):
        import extractors.nspower_rates as mod

        csv_path = tmp_path / "nspower_rates_manual.csv"
        csv_path.write_text("year,residential_rate_cents_per_kwh\n2019,17.82\n2020,18.10\n")

        monkeypatch.setattr(mod, "RAW_DIR", tmp_path)
        monkeypatch.setattr(mod, "MANUAL_CSV", csv_path)

        mod.extract_nspower_rates()

        records = json.loads((tmp_path / "nspower_rates.json").read_text())
        assert len(records) == 2
        assert records[0]["year"] == 2019
        assert records[0]["residential_rate_cents_per_kwh"] == pytest.approx(17.82)


# ---------------------------------------------------------------------------
# eccc_weather extractor (unit tests only, no network)
# ---------------------------------------------------------------------------

class TestECCCWeatherExtractor:
    def test_float_or_none_valid(self):
        from extractors.eccc_weather import _float_or_none

        assert _float_or_none("3.14") == pytest.approx(3.14)
        assert _float_or_none("  100.0  ") == pytest.approx(100.0)

    def test_float_or_none_invalid(self):
        from extractors.eccc_weather import _float_or_none

        assert _float_or_none("M") is None
        assert _float_or_none("") is None
        assert _float_or_none(None) is None

    def test_cached_file_skipped(self, tmp_path, monkeypatch):
        import extractors.eccc_weather as mod

        monkeypatch.setattr(mod, "RAW_DIR", tmp_path)
        out = tmp_path / "eccc_weather.json"
        out.write_text("[]")

        # Should return immediately without any network call
        mod.extract_eccc_weather()
        assert out.read_text() == "[]"  # not overwritten
