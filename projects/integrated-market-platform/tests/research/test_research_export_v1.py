"""Research Export v1 contract tests (Profile A + Profile C, fixture-backed)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from market_platform_foundation.research.export_v1 import (
    EXPORT_EVIDENCE_CLASS_EXTERNAL_RESEARCH_DATA,
    EXPORT_EVIDENCE_CLASS_NON_EMPIRICAL_FIXTURE,
    EXPORT_OPERATOR_PIT_STATUS_PASS,
    EXPORT_OPERATOR_PIT_STATUS_PENDING,
    PROFILE_EVENT_MACRO,
    PROFILE_MARKET_TECHNICAL,
    ResearchExportV1Package,
    build_research_export_v1,
    build_matlab_handoff_manifest,
    build_matlab_parity_reference,
    derive_export_id,
    load_matlab_handoff_manifest,
    load_research_export_v1_package,
    manifest_hash,
    matlab_parity_check,
    require_unmixed_evidence_class,
    verify_matlab_handoff_manifest,
    verify_research_export_v1_package,
    write_research_export_v1_package,
)
from market_platform_foundation.research.wave1.errors import Wave1ExportGateError
from market_platform_foundation.research.wave1.export_gate import (
    PIT_PASS_STATUS,
    assess_research_export_pit,
    oos_evaluation_authorized,
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
        self.assertNotEqual(meta["pit_status"], EXPORT_OPERATOR_PIT_STATUS_PASS)
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

    def test_verify_requires_operator_pit_status(self) -> None:
        package = build_research_export_v1(profile=PROFILE_MARKET_TECHNICAL)
        meta = dict(package.manifest["metadata"])
        meta.pop("pit_status")
        rebound = _rebind_manifest({**package.manifest, "metadata": meta})
        bad = ResearchExportV1Package(manifest=rebound, tables=package.tables)
        with self.assertRaises(ValueError) as ctx:
            verify_research_export_v1_package(bad)
        self.assertEqual(str(ctx.exception), "OPERATOR_PIT_STATUS_REQUIRED")

    def test_external_research_data_cannot_mix_with_canonical_fixture(self) -> None:
        package = build_research_export_v1(profile=PROFILE_MARKET_TECHNICAL)
        meta = dict(package.manifest["metadata"])
        meta["evidence_class"] = EXPORT_EVIDENCE_CLASS_EXTERNAL_RESEARCH_DATA
        rebound = _rebind_manifest({**package.manifest, "metadata": meta})
        mixed = ResearchExportV1Package(manifest=rebound, tables=package.tables)
        with self.assertRaises(ValueError) as ctx:
            verify_research_export_v1_package(mixed)
        self.assertEqual(str(ctx.exception), "MIXED_EXTERNAL_RESEARCH_DATA")
        with self.assertRaises(ValueError) as mix_ctx:
            require_unmixed_evidence_class(rebound, package.tables)
        self.assertEqual(str(mix_ctx.exception), "MIXED_EXTERNAL_RESEARCH_DATA")

    def test_row_level_external_research_data_mixes_with_fixture_class(self) -> None:
        package = build_research_export_v1(profile=PROFILE_EVENT_MACRO)
        tables = {
            name: [dict(row) for row in rows] for name, rows in package.tables.items()
        }
        features = tables["feature_snapshots"]
        features[0]["evidence_class"] = EXPORT_EVIDENCE_CLASS_EXTERNAL_RESEARCH_DATA
        with self.assertRaises(ValueError) as ctx:
            require_unmixed_evidence_class(package.manifest, tables)
        self.assertEqual(str(ctx.exception), "MIXED_EXTERNAL_RESEARCH_DATA")

    def test_matlab_handoff_keeps_pending_and_rejects_external_mix(self) -> None:
        package = build_research_export_v1(profile=PROFILE_MARKET_TECHNICAL)
        handoff = build_matlab_handoff_manifest(package)
        verify_matlab_handoff_manifest(handoff)
        self.assertEqual(
            handoff["metadata"]["pit_status"],
            EXPORT_OPERATOR_PIT_STATUS_PENDING,
        )
        mixed = dict(handoff)
        mixed["metadata"] = {
            **dict(handoff["metadata"]),
            "evidence_class": EXPORT_EVIDENCE_CLASS_EXTERNAL_RESEARCH_DATA,
        }
        mixed["export_profile"] = PROFILE_MARKET_TECHNICAL
        with self.assertRaises(ValueError) as ctx:
            verify_matlab_handoff_manifest(mixed)
        self.assertEqual(str(ctx.exception), "MIXED_EXTERNAL_RESEARCH_DATA")

    def test_external_research_data_blocks_wave1_oos_even_if_pit_pass(self) -> None:
        package = build_research_export_v1(profile=PROFILE_MARKET_TECHNICAL)
        vdm = package.manifest["validation_dataset_manifest"]
        assessment = assess_research_export_pit(package.manifest, validation_dataset_manifest=vdm)
        self.assertFalse(oos_evaluation_authorized(assessment))
        stub = {
            "metadata": {
                "evidence_class": EXPORT_EVIDENCE_CLASS_EXTERNAL_RESEARCH_DATA,
                "pit_status": EXPORT_OPERATOR_PIT_STATUS_PASS,
            },
            "validation_dataset_manifest": vdm,
        }
        with self.assertRaises(Wave1ExportGateError) as ctx:
            require_pit_pass_for_oos(stub, validation_dataset_manifest=vdm)
        self.assertEqual(ctx.exception.code, "W1_OOS_BLOCKED_EXTERNAL_RESEARCH_DATA")
        self.assertFalse(
            oos_evaluation_authorized(
                assess_research_export_pit(stub, validation_dataset_manifest=vdm)
            )
        )


def _rebind_manifest(manifest: dict) -> dict:
    body = dict(manifest)
    body.pop("export_id", None)
    body.pop("manifest_hash", None)
    body["export_id"] = derive_export_id(body)
    body["manifest_hash"] = manifest_hash(body)
    return body


if __name__ == "__main__":
    unittest.main()
