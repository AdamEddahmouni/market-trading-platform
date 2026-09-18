"""Historical research harness v1 (HISTORICAL_DEVELOPMENT only)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.historical_research_harness import (  # noqa: E402
    ChronologicalSplitPolicy,
    HistoricalResearchHoldoutConsumptionError,
    HistoricalResearchRunConfig,
    HistoricalResearchSplitName,
    SIMULATOR_RESEARCH_RESULT_KIND,
    assert_chronological_order,
    assert_split_consumable_for_training_or_selection,
    assign_chronological_splits,
    config_fingerprint,
    derive_historical_research_run_id,
    reconstruct_historical_research_features,
    run_historical_research_harness,
    splits_overlap,
)
from market_platform_foundation.intelligence.historical_research_harness.labels import (  # noqa: E402
    historical_research_forward_return_label,
)
from market_platform_foundation.intelligence.historical_research_harness.types import (  # noqa: E402
    HISTORICAL_RESEARCH_LABEL_KIND,
)
from market_platform_foundation.market_data.historical_development import (  # noqa: E402
    FixtureHistoricalMarketDataProvider,
    build_historical_rth_dataset,
)
from market_platform_foundation.market_data.historical_development.provider import (  # noqa: E402
    load_fixture_rows_from_json,
)
from market_platform_foundation.paper.calibration.dual_corpus import (  # noqa: E402
    CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT,
    CORPUS_EVIDENCE_AUTHORITY_POST_HORIZON_HISTORICAL_LABEL_EVIDENCE,
)

FIXTURE = ROOT / "tests/fixtures/historical_development/aapl_2026-09-15_rth_sample.json"
SESSION_DAY = "2026-09-15"


def _synthetic_bars(count: int, *, start_ns: int = 1_000_000) -> list[dict]:
    bars: list[dict] = []
    for index in range(count):
        close = 100.0 + index * 0.5
        bars.append(
            {
                "available_time": start_ns + index * 60_000_000_000,
                "event_time": start_ns + index * 60_000_000_000,
                "event_type": "BAR_OHLCV_1M",
                "instrument_id": "canonical:EQUITY:XNAS:AAPL",
                "normalized_event_id": f"evt-{index}",
                "bar_payload": {
                    "open": str(close - 0.1),
                    "high": str(close + 0.2),
                    "low": str(close - 0.2),
                    "close": str(close),
                    "volume": 1000 + index,
                },
            }
        )
    return bars


class HistoricalResearchHarnessTests(unittest.TestCase):
    def test_chronological_split_no_overlap_and_ordered(self) -> None:
        times = [row["available_time"] for row in _synthetic_bars(10)]
        policy = ChronologicalSplitPolicy(train_fraction=0.6, development_validate_fraction=0.2)
        assignments = assign_chronological_splits(times, policy)
        self.assertFalse(splits_overlap(assignments))
        assert_chronological_order(assignments)
        splits = {row.split for row in assignments}
        self.assertIn(HistoricalResearchSplitName.HISTORICAL_TRAIN, splits)
        self.assertIn(HistoricalResearchSplitName.HISTORICAL_RESEARCH_TEST, splits)

    def test_split_is_deterministic(self) -> None:
        times = [row["available_time"] for row in _synthetic_bars(12)]
        policy = ChronologicalSplitPolicy()
        first = assign_chronological_splits(times, policy)
        second = assign_chronological_splits(times, policy)
        self.assertEqual(first, second)

    def test_research_test_holdout_refused_for_training(self) -> None:
        with self.assertRaises(HistoricalResearchHoldoutConsumptionError):
            assert_split_consumable_for_training_or_selection(
                HistoricalResearchSplitName.HISTORICAL_RESEARCH_TEST,
                purpose="model_selection",
            )

    def test_feature_cutoff_excludes_future_bars(self) -> None:
        bars = _synthetic_bars(8)
        cutoff = int(bars[4]["available_time"])
        features = reconstruct_historical_research_features(bars, prediction_cutoff_ns=cutoff)
        self.assertEqual(features["prediction_cutoff_ns"], cutoff)
        self.assertNotIn("PIT_FEATURE_FUTURE_INPUT", features.get("pit_rejection_reasons", []))

    def test_label_kind_distinct_from_post_horizon(self) -> None:
        bars = _synthetic_bars(6)
        label = historical_research_forward_return_label(
            bars,
            decision_time_ns=int(bars[2]["available_time"]),
            forward_horizon_bars=1,
        )
        self.assertIsNotNone(label)
        assert label is not None
        self.assertEqual(label["label_kind"], HISTORICAL_RESEARCH_LABEL_KIND)
        self.assertNotEqual(
            label["corpus_evidence_authority"],
            CORPUS_EVIDENCE_AUTHORITY_POST_HORIZON_HISTORICAL_LABEL_EVIDENCE,
        )

    def test_run_fingerprint_reproducible(self) -> None:
        config = HistoricalResearchRunConfig(
            experiment_id="exp-test",
            hypothesis_id="hyp-test",
        )
        fp = config_fingerprint(config)
        run_id = derive_historical_research_run_id(
            experiment_id=config.experiment_id,
            dataset_fingerprint="dataset-fp",
            config_fingerprint=fp,
            research_code_sha="abc123",
        )
        run_id_again = derive_historical_research_run_id(
            experiment_id=config.experiment_id,
            dataset_fingerprint="dataset-fp",
            config_fingerprint=fp,
            research_code_sha="abc123",
        )
        self.assertEqual(run_id, run_id_again)

    def test_fixture_harness_pipeline(self) -> None:
        provider = FixtureHistoricalMarketDataProvider(load_fixture_rows_from_json(FIXTURE))
        with tempfile.TemporaryDirectory() as tmp:
            corpus_root = Path(tmp) / "corpus"
            harness_root = Path(tmp) / "harness"
            build = build_historical_rth_dataset(
                repository_root=ROOT,
                provider=provider,
                instrument="AAPL",
                start_date=SESSION_DAY,
                end_date=SESSION_DAY,
                artifact_root=corpus_root,
                fixture_only=True,
            )
            self.assertTrue(build.ok)
            config = HistoricalResearchRunConfig(
                experiment_id="hist-harness-fixture",
                hypothesis_id="hist-harness-hypothesis",
            )
            first = run_historical_research_harness(
                repository_root=ROOT,
                build=build,
                config=config,
                artifact_root=harness_root,
            )
            second = run_historical_research_harness(
                repository_root=ROOT,
                build=build,
                config=config,
                artifact_root=harness_root,
            )
            self.assertTrue(first.ok)
            self.assertTrue(second.ok)
            self.assertEqual(first.run_id, second.run_id)
            self.assertEqual(first.body["run_fingerprint"], second.body["run_fingerprint"])
            self.assertEqual(
                first.body["corpus_evidence_authority"],
                CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT,
            )
            self.assertEqual(
                first.body["simulator"]["result_kind"],
                SIMULATOR_RESEARCH_RESULT_KIND,
            )
            self.assertTrue(first.artifact_path.is_file())


if __name__ == "__main__":
    unittest.main()
