"""Historical research harness v1 (HISTORICAL_DEVELOPMENT only)."""

from __future__ import annotations

import json
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
from market_platform_foundation.intelligence.historical_research_harness.simulator import (  # noqa: E402
    run_historical_development_simulator_research,
)
from market_platform_foundation.intelligence.historical_research_harness.split import (  # noqa: E402
    decision_times_for_split,
    filter_events_to_decision_times,
)
from market_platform_foundation.market_data.historical_development.e2e_demo import (  # noqa: E402
    normalized_bars_to_replay_events,
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

    def test_manifest_simulator_metrics_exclude_research_test_holdout(self) -> None:
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
                experiment_id="hist-harness-holdout-scope",
                hypothesis_id="hist-harness-holdout-scope-hyp",
            )
            result = run_historical_research_harness(
                repository_root=ROOT,
                build=build,
                config=config,
                artifact_root=harness_root,
            )
            self.assertTrue(result.ok)
            normalized_path = build.paths.normalized_dir
            bars = json.loads(
                sorted(normalized_path.glob("*_normalized.json"))[0].read_text(encoding="utf-8")
            )
            clocks = sorted({int(bar["available_time"]) for bar in bars})
            assignments = assign_chronological_splits(clocks, config.split_policy)
            ingest_run_id = f"HIST-RESEARCH-{build.normalized_fingerprint[:12]}"
            events = normalized_bars_to_replay_events(bars, ingest_run_id=ingest_run_id)
            dev_times = decision_times_for_split(
                assignments,
                HistoricalResearchSplitName.HISTORICAL_DEVELOPMENT_VALIDATE,
            )
            test_times = decision_times_for_split(
                assignments,
                HistoricalResearchSplitName.HISTORICAL_RESEARCH_TEST,
            )
            dev_events = filter_events_to_decision_times(events, dev_times)
            dev_sim = run_historical_development_simulator_research(
                dev_events,
                simulator_version=config.simulator_version,
                cost_slippage_bps=config.cost_slippage_bps,
            )
            full_sim = run_historical_development_simulator_research(
                events,
                simulator_version=config.simulator_version,
                cost_slippage_bps=config.cost_slippage_bps,
            )
            metrics = result.body["metrics"]
            self.assertEqual(
                metrics["evaluation_split"],
                HistoricalResearchSplitName.HISTORICAL_DEVELOPMENT_VALIDATE.value,
            )
            self.assertEqual(metrics["simulated_fills"], dev_sim["fill_count"])
            self.assertEqual(metrics["gross_pnl"], dev_sim["gross_pnl"])
            self.assertEqual(metrics["net_pnl"], dev_sim["net_pnl"])
            self.assertTrue(test_times.isdisjoint(frozenset(dev_sim["scoped_event_times_ns"])))
            self.assertEqual(
                result.body["simulator"]["risk_simulation_root_hash"],
                dev_sim["risk_simulation_root_hash"],
            )
            if test_times:
                self.assertTrue(test_times.issubset(frozenset(full_sim["scoped_event_times_ns"])))
                self.assertNotEqual(
                    frozenset(full_sim["scoped_event_times_ns"]),
                    frozenset(dev_sim["scoped_event_times_ns"]),
                )


if __name__ == "__main__":
    unittest.main()
