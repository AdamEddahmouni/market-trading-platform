"""Research Export v1 contract tests (Profile A + Profile C, fixture-backed)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from market_platform_foundation.research.export_v1 import (
    EXPORT_EVIDENCE_CLASS_NON_EMPIRICAL_FIXTURE,
    EXPORT_OPERATOR_PIT_STATUS_PENDING,
    PROFILE_EVENT_MACRO,
    PROFILE_MARKET_TECHNICAL,
    build_research_export_v1,
    build_matlab_handoff_manifest,
    build_matlab_parity_reference,
    derive_export_id,
    load_matlab_handoff_manifest,
    load_research_export_v1_package,
    manifest_hash,
    matlab_parity_check,
    verify_research_export_v1_package,
    write_research_export_v1_package,
)
from market_platform_foundation.research.wave1.errors import Wave1ExportGateError
from market_platform_foundation.research.wave1.export_gate import (
    PIT_PASS_STATUS,
    assess_research_export_pit,
    require_pit_pass_for_oos,
)
from market_platform_foundation.research.export_v1_audit import run_pit_audit
from market_platform_foundation.research.export_v1_profiles import (
    build_event_macro_tables,
    build_market_technical_tables,
)


class ResearchExportV1Tests(unittest.TestCase):
    def test_profile_a_deterministic_export_id(self) -> None:
        first = build_research_export_v1(profile=PROFILE_MARKET_TECHNICAL)
        second = build_research_export_v1(profile=PROFILE_MARKET_TECHNICAL)
        self.assertEqual(first.manifest["export_id"], second.manifest["export_id"])
        self.assertEqual(first.manifest["manifest_hash"], second.manifest["manifest_hash"])
        self.assertEqual(first.manifest["export_id"], derive_export_id(first.manifest))
        self.assertEqual(first.manifest["manifest_hash"], manifest_hash(first.manifest))
        self.assertEqual(first.manifest["export_schema_version"], "1.0.0")
        self.assertEqual(first.manifest["pit_audit"]["status"], "PASS")
        self.assertEqual(first.manifest["leakage_firewall"]["status"], "PASS")
        meta = first.manifest["metadata"]
        self.assertEqual(meta["pit_status"], EXPORT_OPERATOR_PIT_STATUS_PENDING)
        self.assertEqual(meta["evidence_class"], EXPORT_EVIDENCE_CLASS_NON_EMPIRICAL_FIXTURE)
        self.assertIn("validation_dataset_manifest", first.manifest)
        self.assertIn("pit_export_binding", first.manifest)
        self.assertGreater(len(first.tables["realized_outcomes"]), 0)
        self.assertEqual(
            len(first.tables["feature_snapshots"]),
            len(first.tables["market_observations"]),
        )

    def test_profile_c_macro_vintage_and_exclusions(self) -> None:
        package = build_research_export_v1(profile=PROFILE_EVENT_MACRO)
        self.assertEqual(package.manifest["export_profile"], PROFILE_EVENT_MACRO)
        self.assertGreater(len(package.tables["information_events"]), 0)
        self.assertGreater(package.manifest["excluded_row_count"], 0)
        for feature in package.tables["feature_snapshots"]:
            self.assertNotIn("actual", feature.get("feature_values") or {})
        self.assertEqual(package.manifest["pit_audit"]["status"], "PASS")

    def test_round_trip_loader_and_matlab_parity(self) -> None:
        package = build_research_export_v1(profile=PROFILE_MARKET_TECHNICAL)
        reference = build_matlab_parity_reference(package)
        self.assertTrue(matlab_parity_check(package, reference))
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "profile_a"
            write_research_export_v1_package(out, package)
            loaded = load_research_export_v1_package(out)
            self.assertEqual(loaded.manifest["export_id"], package.manifest["export_id"])
            parity_path = out / "matlab_parity_reference.json"
            self.assertTrue(parity_path.is_file())
            stored_ref = __import__("json").loads(parity_path.read_text(encoding="utf-8"))
            self.assertTrue(matlab_parity_check(loaded, stored_ref))
            handoff_path = out / "matlab_handoff_manifest.json"
            self.assertTrue(handoff_path.is_file())
            self.assertTrue((out / "validation_dataset_manifest.json").is_file())
            handoff = load_matlab_handoff_manifest(out)
            self.assertEqual(handoff, build_matlab_handoff_manifest(package))

    def test_built_export_blocks_wave1_oos_until_operator_pit_pass(self) -> None:
        package = build_research_export_v1(profile=PROFILE_MARKET_TECHNICAL)
        vdm = package.manifest["validation_dataset_manifest"]
        assessment = assess_research_export_pit(package.manifest, validation_dataset_manifest=vdm)
        self.assertNotEqual(assessment.status, PIT_PASS_STATUS)
        self.assertIn("EXPORT_NOT_PIT_PASS", assessment.pit_codes)
        self.assertIn("NON_EMPIRICAL_FIXTURE", assessment.pit_codes)
        with self.assertRaises(Wave1ExportGateError) as ctx:
            require_pit_pass_for_oos(package.manifest, validation_dataset_manifest=vdm)
        self.assertEqual(ctx.exception.code, "W1_OOS_BLOCKED_EXPORT_NOT_PIT_PASS")

    def test_profile_c_metadata_pending(self) -> None:
        package = build_research_export_v1(profile=PROFILE_EVENT_MACRO)
        self.assertEqual(
            package.manifest["metadata"]["pit_status"],
            EXPORT_OPERATOR_PIT_STATUS_PENDING,
        )

    def test_frozen_input_regeneration(self) -> None:
        context_a, tables_a, _ = build_market_technical_tables()
        context_b, tables_b, _ = build_market_technical_tables()
        self.assertEqual(context_a["source_sha256"], context_b["source_sha256"])
        self.assertEqual(tables_a["market_observations"], tables_b["market_observations"])
        audit = run_pit_audit(
            market_observations=tables_a["market_observations"],
            feature_snapshots=tables_a["feature_snapshots"],
            realized_outcomes=tables_a["realized_outcomes"],
            instrument_rows=tables_a["instruments"],
        )
        self.assertEqual(audit["status"], "PASS")

    def test_verify_rejects_tampered_manifest(self) -> None:
        package = build_research_export_v1(profile=PROFILE_EVENT_MACRO)
        tampered = dict(package.manifest)
        tampered["export_id"] = "RESEXP-TAMPERED"
        bad = type(package)(manifest=tampered, tables=package.tables)
        with self.assertRaises(ValueError):
            verify_research_export_v1_package(bad)


if __name__ == "__main__":
    unittest.main()
