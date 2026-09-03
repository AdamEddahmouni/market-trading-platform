import tempfile
import unittest
from pathlib import Path

from market_platform_foundation.assertions import (
    MANDATORY_IDS,
    build_registry,
    create_run_manifest,
    validate_result_membership,
)
from market_platform_foundation.canonical import load_json_strict


class AssertionTests(unittest.TestCase):
    def test_mandatory_set_is_exact(self):
        self.assertEqual(
            MANDATORY_IDS,
            (
                "GOV-001",
                "GOV-002",
                "GOV-003",
                "GOV-004",
                "SAFE-001",
                "SAFE-002",
                "SAFE-003-STATIC",
                "SAFE-P0-001",
                "SEC-001",
            ),
        )

    def test_mixed_run_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_result_membership(
                "RUN-A",
                [
                    {"assertion_id": key, "run_id": "RUN-B"}
                    for key in MANDATORY_IDS
                ],
            )

    def test_registry_has_one_active_key_per_mandatory_id(self):
        registry = build_registry(Path("manifests/phase0/assertion-predicates.json"))
        self.assertEqual(tuple(row["assertion_id"] for row in registry["active_keys"]), MANDATORY_IDS)
        self.assertEqual(registry["registry_version"], "1.0.0")

    def test_run_id_is_reproducible(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "first.json"
            second = Path(tmp) / "second.json"
            inputs = {
                "active_registry_sha256": "A",
                "authorization_references": [],
                "canonical_configuration_sha256": "B",
                "mandatory_set_hash": "C",
                "plan_sha256": "D",
                "selected_evidence": [],
                "specification_sha256": "E",
                "subject_manifest_hash": "F",
                "tool_versions": ["assertion-evaluator/1.0.0"],
            }
            self.assertEqual(create_run_manifest(first, inputs), create_run_manifest(second, inputs))
            self.assertEqual(load_json_strict(first)["run_id"], load_json_strict(second)["run_id"])
