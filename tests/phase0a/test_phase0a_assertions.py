"""Phase 0A assertion evaluator tests."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class Phase0AAssertionTests(unittest.TestCase):
    def test_registry_mandatory_set(self) -> None:
        from market_platform_foundation.phase0a_assertions import build_registry, MANDATORY_IDS

        registry = build_registry(ROOT / "manifests/phase0a/assertion-predicates.json")
        self.assertEqual(registry["mandatory_ids"], list(MANDATORY_IDS))

    def test_blocked_aggregate(self) -> None:
        from market_platform_foundation.canonical import write_canonical_json
        from market_platform_foundation.phase0a_assertions import (
            aggregate_status,
            build_registry,
            create_run_manifest,
            evaluate_run,
        )

        registry = build_registry(ROOT / "manifests/phase0a/assertion-predicates.json")
        staging = ROOT / "tests/phase0a/.staging-manifest.json"
        run_id = create_run_manifest(
            staging,
            {
                "active_keys": registry["active_keys"],
                "assertion_observations": {
                    "DF-001": {"status": "BLOCKED", "reason_codes": ["DF001_NO_LOCAL_BYTES"]},
                    "DF-002": {"status": "BLOCKED", "reason_codes": ["DF001_BLOCKED_PREREQUISITE"]},
                },
                "evaluated_at": "2026-08-15T04:10:00.000000000Z",
                "registry_hash": "TEST",
                "selected_evidence": [],
                "subject_manifest_hash": "TESTSUBJECT",
                "tool_versions": ["test"],
            },
        )
        out = ROOT / "tests/phase0a/.out"
        out.mkdir(exist_ok=True)
        staging.replace(out / "assertion-run-manifest.json")
        results = evaluate_run(out / "assertion-run-manifest.json", out)
        self.assertEqual(aggregate_status(results), "BLOCKED")
        statuses = {r["assertion_id"]: r["status"] for r in results}
        self.assertEqual(statuses["DF-001"], "BLOCKED")
        self.assertEqual(statuses["DF-002"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
