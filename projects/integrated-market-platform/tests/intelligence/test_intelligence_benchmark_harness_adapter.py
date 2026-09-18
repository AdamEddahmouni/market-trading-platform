"""IBP v1 adapter + contamination controls for historical research harness."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.benchmark_protocol import (  # noqa: E402
    BenchmarkContaminationError,
    adapt_historical_research_run_manifest_v1,
    assess_benchmark_smoke10_readiness,
    build_smoke10_invocation_contract,
    load_suite_catalog,
    strip_evaluator_only_fields,
)
from market_platform_foundation.intelligence.benchmark_protocol.contamination import (  # noqa: E402
    EVALUATOR_ONLY_MANIFEST_KEYS,
)
from market_platform_foundation.intelligence.historical_research_harness import (  # noqa: E402
    HistoricalResearchRunConfig,
    SIMULATOR_RESEARCH_RESULT_KIND,
    run_historical_research_harness,
)
from market_platform_foundation.market_data.historical_development import (  # noqa: E402
    FixtureHistoricalMarketDataProvider,
    build_historical_rth_dataset,
)
from market_platform_foundation.market_data.historical_development.provider import (  # noqa: E402
    load_fixture_rows_from_json,
)

FIXTURE = ROOT / "tests/fixtures/historical_development/aapl_2026-09-15_rth_sample.json"
SESSION_DAY = "2026-09-15"


def _fixture_harness_manifest() -> dict:
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
        assert build.ok
        result = run_historical_research_harness(
            repository_root=ROOT,
            build=build,
            config=HistoricalResearchRunConfig(
                experiment_id="ibp-adapter-fixture",
                hypothesis_id="ibp-adapter-hypothesis",
            ),
            artifact_root=harness_root,
        )
        assert result.ok and result.body is not None
        return result.body


class IntelligenceBenchmarkHarnessAdapterTests(unittest.TestCase):
    def test_suite_catalog_has_thirty_cases(self) -> None:
        catalog = load_suite_catalog(ROOT)
        self.assertEqual(len(catalog["cases"]), 30)
        self.assertEqual(len(catalog["smoke10_case_ids"]), 10)

    def test_strip_removes_labels_path_from_sut_bundle(self) -> None:
        manifest = _fixture_harness_manifest()
        self.assertIn("labels_path", manifest.get("outputs", {}))
        stripped = strip_evaluator_only_fields(manifest)
        outputs = stripped.get("outputs", {})
        self.assertNotIn("labels_path", outputs)

    def test_adapter_preserves_simulator_research_not_item9(self) -> None:
        manifest = _fixture_harness_manifest()
        self.assertEqual(manifest["simulator"]["result_kind"], SIMULATOR_RESEARCH_RESULT_KIND)
        record = adapt_historical_research_run_manifest_v1(manifest)
        self.assertFalse(record["scores_executed"])
        self.assertEqual(record["case_results"], [])
        sut = record["system_under_test_input"]
        for key in EVALUATOR_ONLY_MANIFEST_KEYS:
            self.assertNotIn(key, sut)

    def test_item9_calibration_manifest_refused(self) -> None:
        manifest = _fixture_harness_manifest()
        manifest = dict(manifest)
        manifest["simulator"] = dict(manifest["simulator"])
        manifest["simulator"]["result_kind"] = "ITEM9_CALIBRATION_RESULT"
        with self.assertRaises(BenchmarkContaminationError):
            adapt_historical_research_run_manifest_v1(manifest)

    def test_smoke10_plan_does_not_execute_scores(self) -> None:
        manifest = _fixture_harness_manifest()
        record = adapt_historical_research_run_manifest_v1(manifest)
        contract = build_smoke10_invocation_contract(ROOT, historical_run_record=record)
        self.assertFalse(contract["scores_executed"])
        self.assertFalse(contract["evaluator_invoked"])
        self.assertEqual(len(contract["case_plans"]), 10)
        for plan in contract["case_plans"]:
            self.assertFalse(plan["scores_executed"])
            self.assertFalse(plan["evaluator_gold_loaded_for_sut"])

    def test_readiness_yes_with_fixture_manifest(self) -> None:
        manifest = _fixture_harness_manifest()
        payload = assess_benchmark_smoke10_readiness(ROOT, sample_historical_manifest=manifest)
        self.assertEqual(payload["BENCHMARK_SMOKE10_READY"], "YES")
        self.assertFalse(payload["scores_executed"])


if __name__ == "__main__":
    unittest.main()
