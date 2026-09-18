"""Frozen Historical Baseline Pack v1 (Lane C)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.historical_research_harness.baseline_pack import (  # noqa: E402
    HISTORICAL_BASELINE_PACK_V1,
    build_frozen_baseline_pack_experiment_definition,
    compute_experiment_definition_hash,
    experiment_definition_hash,
    freeze_baseline_pack_definition_to_disk,
    run_frozen_historical_baseline_pack_v1,
    verify_frozen_experiment_definition,
)
from market_platform_foundation.intelligence.historical_research_harness.strategies import (  # noqa: E402
    BASELINE_STRATEGY_MOMENTUM_5M_SIGN_V1,
    BASELINE_STRATEGY_NO_TRADE_V1,
    predict_direction,
)
from market_platform_foundation.market_data.historical_development import (  # noqa: E402
    FixtureHistoricalMarketDataProvider,
    build_historical_rth_dataset,
)
from market_platform_foundation.market_data.historical_development.provider import (  # noqa: E402
    load_fixture_rows_from_json,
)
from market_platform_foundation.paper.calibration.dual_corpus.contamination_auditor import (  # noqa: E402
    CONTAMINATION_STATUS_PASS,
)

MULTI_SESSION_FIXTURE = (
    ROOT / "tests/fixtures/historical_development/aapl_2026-09-11_2026-09-15_rth_multi_session.json"
)


class HistoricalBaselinePackV1Tests(unittest.TestCase):
    def test_experiment_definition_hash_stable(self) -> None:
        dataset_identity = {
            "dataset_id": "fixture-dataset",
            "dataset_fingerprint": "fp-abc",
            "fixture_path": "tests/fixtures/historical_development/sample.json",
        }
        first = build_frozen_baseline_pack_experiment_definition(
            repository_root=ROOT,
            dataset_identity=dataset_identity,
            code_sha="deadbeef",
        )
        second = build_frozen_baseline_pack_experiment_definition(
            repository_root=ROOT,
            dataset_identity=dataset_identity,
            code_sha="deadbeef",
        )
        first["created_timestamp_ns"] = second["created_timestamp_ns"] = 1
        first_hash = compute_experiment_definition_hash(first)
        second_hash = compute_experiment_definition_hash(second)
        self.assertEqual(first_hash, second_hash)
        first["experiment_definition_hash"] = first_hash
        self.assertTrue(verify_frozen_experiment_definition(first)["ok"])

    def test_tampered_frozen_definition_refused(self) -> None:
        dataset_identity = {
            "dataset_id": "fixture-dataset",
            "dataset_fingerprint": "fp-abc",
            "fixture_path": "tests/fixtures/historical_development/sample.json",
        }
        frozen = build_frozen_baseline_pack_experiment_definition(
            repository_root=ROOT,
            dataset_identity=dataset_identity,
            code_sha="deadbeef",
        )
        frozen["baseline_strategies"][0]["description"] = "tampered after freeze"
        result = verify_frozen_experiment_definition(frozen)
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason_code"], "EXPERIMENT_DEFINITION_HASH_MISMATCH")

        provider = FixtureHistoricalMarketDataProvider(load_fixture_rows_from_json(MULTI_SESSION_FIXTURE))
        with tempfile.TemporaryDirectory() as tmp:
            build = build_historical_rth_dataset(
                repository_root=ROOT,
                provider=provider,
                instrument="AAPL",
                start_date="2026-09-11",
                end_date="2026-09-15",
                artifact_root=Path(tmp) / "corpus",
                fixture_only=True,
            )
            self.assertTrue(build.ok)
            pack = run_frozen_historical_baseline_pack_v1(
                repository_root=ROOT,
                build=build,
                frozen_definition=frozen,
                artifact_root=Path(tmp) / "pack",
            )
            self.assertFalse(pack.ok)
            self.assertEqual(pack.reason_code, "EXPERIMENT_DEFINITION_HASH_MISMATCH")

    def test_baseline_predictors_no_trade_and_momentum(self) -> None:
        features = {"values": {"momentum_5m": 0.02}}
        self.assertEqual(predict_direction(BASELINE_STRATEGY_NO_TRADE_V1, features), 0)
        self.assertEqual(predict_direction(BASELINE_STRATEGY_MOMENTUM_5M_SIGN_V1, features), 1)

    def test_frozen_pack_run_and_contamination_pass(self) -> None:
        provider = FixtureHistoricalMarketDataProvider(load_fixture_rows_from_json(MULTI_SESSION_FIXTURE))
        with tempfile.TemporaryDirectory() as tmp:
            corpus_root = Path(tmp) / "corpus"
            pack_root = Path(tmp) / "pack"
            build = build_historical_rth_dataset(
                repository_root=ROOT,
                provider=provider,
                instrument="AAPL",
                start_date="2026-09-11",
                end_date="2026-09-15",
                artifact_root=corpus_root,
                fixture_only=True,
            )
            self.assertTrue(build.ok)
            dataset_identity = {
                "dataset_id": str(build.manifest.get("dataset_id") or build.run_id),
                "dataset_fingerprint": str(
                    build.manifest.get("dataset_fingerprint") or build.normalized_fingerprint
                ),
                "fixture_path": str(MULTI_SESSION_FIXTURE.relative_to(ROOT)),
            }
            frozen_path, frozen = freeze_baseline_pack_definition_to_disk(
                repository_root=ROOT,
                dataset_identity=dataset_identity,
                artifact_root=pack_root,
            )
            self.assertTrue(frozen_path.is_file())
            self.assertEqual(frozen["evidence_label"], HISTORICAL_BASELINE_PACK_V1)
            result = run_frozen_historical_baseline_pack_v1(
                repository_root=ROOT,
                build=build,
                frozen_definition=frozen,
                artifact_root=pack_root,
            )
            self.assertTrue(result.ok, msg=result.reason_code)
            self.assertEqual(len(result.body["baseline_results"]), 4)
            audit = result.body["contamination_audit"]
            self.assertEqual(audit["CONTAMINATION_STATUS"], CONTAMINATION_STATUS_PASS)
            self.assertTrue(result.body["reproducibility"]["deterministic_rerun_first_baseline_match"])
            manifest_path = result.artifact_dir / "baseline_pack_run_manifest.json"
            self.assertTrue(manifest_path.is_file())
            loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(loaded["evidence_label"], HISTORICAL_BASELINE_PACK_V1)


if __name__ == "__main__":
    unittest.main()
