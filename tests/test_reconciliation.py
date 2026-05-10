"""Tests for program reconciliation and unit conformance.

Run with: pytest tests/test_reconciliation.py
"""

import csv
import json
import pathlib
import pytest


# ---------------------------------------------------------------------------
# conform_units
# ---------------------------------------------------------------------------

class TestConformUnits:
    def test_gwh_to_gj_conversion(self):
        from transforms.conform_units import _conform_actual_record, GWH_TO_GJ

        rec = {
            "year": 2023,
            "program_name_raw": "Heat Pump Program",
            "actual_gj": None,
            "actual_gwh_electric": 10.0,
            "actual_mw": None,
            "actual_tonnes_co2e": None,
            "actual_spend_cad": None,
            "actual_participants": None,
            "actual_lifetime_gj": None,
            "as_originally_reported": None,
            "as_restated": None,
            "source_page": None,
            "source_url": "",
        }
        result = _conform_actual_record(rec)
        assert result["actual_gj"] == pytest.approx(10.0 * GWH_TO_GJ)

    def test_existing_gj_not_overwritten(self):
        from transforms.conform_units import _conform_actual_record

        rec = {
            "year": 2023,
            "program_name_raw": "Test",
            "actual_gj": 42.0,
            "actual_gwh_electric": 5.0,
            "actual_mw": None,
            "actual_tonnes_co2e": None,
            "actual_spend_cad": None,
            "actual_participants": None,
            "actual_lifetime_gj": None,
            "as_originally_reported": None,
            "as_restated": None,
            "source_page": None,
            "source_url": "",
        }
        result = _conform_actual_record(rec)
        # GJ already present — should not be overwritten
        assert result["actual_gj"] == 42.0

    def test_as_restated_defaults_to_actual_gj(self):
        from transforms.conform_units import _conform_actual_record

        rec = {
            "year": 2022,
            "program_name_raw": "Test",
            "actual_gj": 100.0,
            "actual_gwh_electric": None,
            "actual_mw": None,
            "actual_tonnes_co2e": None,
            "actual_spend_cad": None,
            "actual_participants": None,
            "actual_lifetime_gj": None,
            "as_originally_reported": None,
            "as_restated": None,
            "source_page": None,
            "source_url": "",
        }
        result = _conform_actual_record(rec)
        assert result["as_restated"] == 100.0
        assert result["as_originally_reported"] == 100.0

    def test_target_gwh_to_gj(self):
        from transforms.conform_units import _conform_target_record, GWH_TO_GJ

        rec = {
            "plan_filing_id": "2020-2025",
            "plan_year": 2022,
            "program_name_raw": "Efficient Products",
            "target_gj": None,
            "target_gwh_electric": 20.0,
            "target_mw": None,
            "target_tonnes_co2e": None,
            "target_spend_cad": None,
            "target_participants": None,
            "is_manually_entered": False,
            "source_page": None,
            "source_path": "",
        }
        result = _conform_target_record(rec)
        assert result["target_gj"] == pytest.approx(20.0 * GWH_TO_GJ)


# ---------------------------------------------------------------------------
# reconcile_programs
# ---------------------------------------------------------------------------

class TestReconcilePrograms:
    @pytest.fixture
    def mapping_csv(self, tmp_path) -> pathlib.Path:
        p = tmp_path / "program_mapping.csv"
        rows = [
            {
                "program_id": "P001",
                "canonical_name": "Home Energy Assessment",
                "raw_name_variants": "Home Energy Assessment|Home Energy Assessments|Residential Energy Assessment",
                "prior_names": "",
                "category": "Residential",
                "funding_source": "DSM-Electric",
                "is_low_income": "0",
                "is_active": "1",
                "valid_from": "2019",
                "valid_to": "",
            },
            {
                "program_id": "P009",
                "canonical_name": "Low-Income Efficiency",
                "raw_name_variants": "Low-Income Efficiency|Low Income Program|Efficiency NS Low-Income",
                "prior_names": "Low Income Program",
                "category": "Low-Income",
                "funding_source": "DSM-Electric",
                "is_low_income": "1",
                "is_active": "1",
                "valid_from": "2019",
                "valid_to": "",
            },
        ]
        with p.open("w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        return p

    def test_known_name_resolves(self, mapping_csv, monkeypatch):
        import transforms.reconcile_programs as mod

        monkeypatch.setattr(mod, "MAPPING_CSV", mapping_csv)
        mapping = mod._load_mapping()

        assert "home energy assessment" in mapping
        assert mapping["home energy assessment"]["program_id"] == "P001"

    def test_variant_name_resolves(self, mapping_csv, monkeypatch):
        import transforms.reconcile_programs as mod

        monkeypatch.setattr(mod, "MAPPING_CSV", mapping_csv)
        mapping = mod._load_mapping()

        assert "residential energy assessment" in mapping
        assert mapping["residential energy assessment"]["program_id"] == "P001"

    def test_low_income_flag(self, mapping_csv, monkeypatch):
        import transforms.reconcile_programs as mod

        monkeypatch.setattr(mod, "MAPPING_CSV", mapping_csv)
        mapping = mod._load_mapping()

        assert mapping["low income program"]["is_low_income"] is True
        assert mapping["home energy assessment"]["is_low_income"] is False

    def test_unknown_name_flagged(self, mapping_csv, tmp_path, monkeypatch):
        import transforms.reconcile_programs as mod

        monkeypatch.setattr(mod, "MAPPING_CSV", mapping_csv)
        monkeypatch.setattr(mod, "INTERIM_DIR", tmp_path)

        records = [
            {"program_name_raw": "Completely Unknown Program XYZ", "year": 2022}
        ]
        (tmp_path / "test_input.json").write_text(json.dumps(records))

        mapping = mod._load_mapping()
        mod._reconcile("test_input.json", "test_output.json", mapping)

        out = json.loads((tmp_path / "test_output.json").read_text())
        assert out[0]["program_id"] == "__UNKNOWN__"

    def test_reconcile_roundtrip(self, mapping_csv, tmp_path, monkeypatch):
        import transforms.reconcile_programs as mod

        monkeypatch.setattr(mod, "MAPPING_CSV", mapping_csv)
        monkeypatch.setattr(mod, "INTERIM_DIR", tmp_path)

        records = [
            {"program_name_raw": "Low Income Program", "year": 2019, "actual_gj": 500.0},
            {"program_name_raw": "Home Energy Assessments", "year": 2020, "actual_gj": 120.0},
        ]
        (tmp_path / "in.json").write_text(json.dumps(records))

        mapping = mod._load_mapping()
        mod._reconcile("in.json", "out.json", mapping)

        out = json.loads((tmp_path / "out.json").read_text())
        assert out[0]["program_id"] == "P009"
        assert out[0]["is_low_income"] is True
        assert out[1]["program_id"] == "P001"
        assert out[1]["canonical_name"] == "Home Energy Assessment"


# ---------------------------------------------------------------------------
# program_mapping.csv integrity
# ---------------------------------------------------------------------------

class TestProgramMappingIntegrity:
    MAPPING = pathlib.Path("sql/program_mapping.csv")

    def test_mapping_exists(self):
        assert self.MAPPING.exists(), "sql/program_mapping.csv must exist"

    def test_required_columns_present(self):
        with self.MAPPING.open(newline="") as fh:
            reader = csv.DictReader(fh)
            cols = reader.fieldnames or []
        required = {"program_id", "canonical_name", "raw_name_variants", "is_low_income", "is_active"}
        assert required.issubset(set(cols))

    def test_no_duplicate_program_ids(self):
        ids = []
        with self.MAPPING.open(newline="") as fh:
            for row in csv.DictReader(fh):
                ids.append(row["program_id"].strip())
        assert len(ids) == len(set(ids)), "Duplicate program_ids found in program_mapping.csv"

    def test_active_programs_have_null_valid_to(self):
        problems = []
        with self.MAPPING.open(newline="") as fh:
            for row in csv.DictReader(fh):
                if row.get("is_active", "").strip() == "1" and row.get("valid_to", "").strip():
                    problems.append(row["program_id"])
        assert not problems, f"Active programs with non-null valid_to: {problems}"

    def test_is_low_income_is_binary(self):
        problems = []
        with self.MAPPING.open(newline="") as fh:
            for row in csv.DictReader(fh):
                if row.get("is_low_income", "").strip() not in ("0", "1"):
                    problems.append(row["program_id"])
        assert not problems, f"Non-binary is_low_income values: {problems}"
