import tempfile
import unittest
from pathlib import Path

from market_platform_foundation.canonical import load_json_strict, sha256_bytes
from market_platform_foundation.evidence import (
    build_preassertion_content,
    finalize_artifact,
    publish_artifacts,
)


class EvidenceTests(unittest.TestCase):
    def test_collector_produces_required_step_10_11_ids(self):
        content = build_preassertion_content(
            Path("."),
            {
                "archive_sha256": "A",
                "file_count": 1,
                "manifest_sha256": "B",
            },
            {"files": [], "third_party_distribution_count": 0},
            {"attempt_count": 7, "denied_count": 7},
        )
        authority = content["phase0.canonical_inventory"]["canonical_authority"]
        self.assertEqual(authority["status"], "PASS")
        self.assertEqual(
            authority["active_logical_id"],
            "foundation.canonical_specification.revision_3",
        )
        self.assertEqual(
            authority["active_sha256"],
            "7C6AE5FC9037CA37D44CD1A2FAACD0CB821192920C46CF001541DCD2121FEB35",
        )
        self.assertTrue(
            content["phase0.canonical_inventory"]["one_canonical_specification"]
        )
        preservation = content["phase0.revision3_donor_preservation_difference"]
        self.assertEqual(preservation["declared_result"], "PASS")
        self.assertEqual(
            preservation["donor_root_ids"],
            ["PROTO-DS340W-001", "PROTO-GRIDIQ-001"],
        )

    def test_collector_excludes_generated_environment_paths(self):
        generated = Path(".venv-phase0-collector-test")
        generated.mkdir(exist_ok=False)
        sensitive = generated / "credential.txt"
        sensitive.write_text("not inspected", encoding="utf-8")
        try:
            content = build_preassertion_content(
                Path("."),
                {"archive_sha256": "A", "file_count": 1, "manifest_sha256": "B"},
                {"files": [], "third_party_distribution_count": 0},
                {"attempt_count": 7, "denied_count": 7},
            )
            self.assertEqual(
                content["phase0.credential_audit"]["current_tree"]["prohibited_count"],
                0,
            )
        finally:
            sensitive.unlink()
            generated.rmdir()
        self.assertEqual(
            set(content),
            {
                "phase0.canonical_inventory",
                "phase0.credential_audit",
                "phase0.denied_network_install",
                "phase0.denied_network_protocol",
                "phase0.dependency_lock_report",
                "phase0.distribution_manifest",
                "phase0.entrypoint_route_report",
                "phase0.import_boundary_report",
                "phase0.local_artifact_manifest",
                "phase0.registry_snapshot",
                "phase0.repository_preservation_difference",
                "phase0.revision3_donor_preservation_difference",
            },
        )

    def test_finalized_artifact_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "artifact.json"
            finalize_artifact(path, "phase0.registry_snapshot", {"rows": []})
            with self.assertRaises(FileExistsError):
                finalize_artifact(path, "phase0.registry_snapshot", {"rows": []})

    def test_content_hash_resolves(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "artifact.json"
            digest = finalize_artifact(path, "phase0.registry_snapshot", {"rows": []})
            self.assertEqual(digest, sha256_bytes(path.read_bytes()))
            record = load_json_strict(path)
            self.assertEqual(record["content_sha256"], sha256_bytes(b'{"rows":[]}\n'))

    def test_bundle_rejects_duplicate_logical_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                publish_artifacts(
                    Path(tmp),
                    [
                        ("phase0.registry_snapshot", {"rows": []}),
                        ("phase0.registry_snapshot", {"rows": []}),
                    ],
                )
