"""Smoke10 baseline execution, contamination audit, and evaluator isolation."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.benchmark_protocol import (  # noqa: E402
    adapt_historical_research_run_manifest_v1,
    audit_smoke10_run_contamination,
    execute_smoke10_baseline,
    freeze_smoke10_run_configuration,
    load_suite_catalog,
    suite_catalog_fingerprint,
)
from market_platform_foundation.intelligence.benchmark_protocol.contamination import (  # noqa: E402
    EVALUATOR_ONLY_MANIFEST_KEYS,
)
from market_platform_foundation.intelligence.benchmark_protocol.synthetic_sut import (  # noqa: E402
    build_blind_case_input,
    run_synthetic_intelligence_sut,
)
from market_platform_foundation.intelligence.historical_research_harness import (  # noqa: E402
    HistoricalResearchRunConfig,
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
                experiment_id="ibp-smoke10-fixture",
                hypothesis_id="ibp-smoke10-hypothesis",
            ),
            artifact_root=harness_root,
        )
        assert result.ok and result.body is not None
        return result.body


class IntelligenceBenchmarkSmoke10ExecutionTests(unittest.TestCase):
    def test_smoke10_case_list_is_first_ten_catalog_ids(self) -> None:
        catalog = load_suite_catalog(ROOT)
        self.assertEqual(
            catalog["smoke10_case_ids"],
            [f"IBP-CASE-{index:03d}" for index in range(1, 11)],
        )

    def test_blind_input_excludes_evaluator_gold_keys(self) -> None:
        catalog = load_suite_catalog(ROOT)
        case = catalog["cases"][0]
        blind = build_blind_case_input(case, context_reset_token="token-001")
        self.assertNotIn("evaluator_gold_ref", blind)
        for key in EVALUATOR_ONLY_MANIFEST_KEYS:
            self.assertNotIn(key, blind)

    def test_freeze_then_execute_smoke10_baseline(self) -> None:
        manifest = _fixture_harness_manifest()
        catalog = load_suite_catalog(ROOT)
        record = adapt_historical_research_run_manifest_v1(
            manifest,
            suite_id=catalog.get("suite_id"),
            suite_catalog_fingerprint=suite_catalog_fingerprint(catalog),
        )
        frozen = freeze_smoke10_run_configuration(ROOT, historical_run_record=record)
        self.assertIn("frozen_config_fingerprint", frozen)
        with tempfile.TemporaryDirectory() as tmp:
            run = execute_smoke10_baseline(
                ROOT,
                frozen_config=frozen,
                historical_run_record=record,
                artifact_root=Path(tmp),
            )
        self.assertTrue(run["scores_executed"])
        self.assertFalse(run["full30_executed"])
        self.assertEqual(len(run["case_results"]), 10)
        self.assertEqual(run["contamination_audit"]["overall"], "PASS")
        self.assertEqual(run["contamination_audit"]["checks"]["DID_SYSTEM_SEE_GOLD"], "PASS")
        for case_row in run["case_results"]:
            self.assertFalse(case_row["evaluator_gold_loaded_for_sut"])
            self.assertTrue(case_row["scores_executed"])
            self.assertIn("facts", case_row["dimension_scores"])

    def test_contamination_fails_when_gold_loaded_for_sut(self) -> None:
        frozen = freeze_smoke10_run_configuration(ROOT)
        run = execute_smoke10_baseline(ROOT, frozen_config=frozen)
        run["case_results"][0]["evaluator_gold_loaded_for_sut"] = True
        audit = audit_smoke10_run_contamination(
            run,
            frozen_config_fingerprint=frozen["frozen_config_fingerprint"],
        )
        self.assertEqual(audit["checks"]["DID_SYSTEM_SEE_GOLD"], "FAIL")

    def test_synthetic_sut_never_emits_gold_answer_field(self) -> None:
        catalog = load_suite_catalog(ROOT)
        case = catalog["cases"][0]
        response = run_synthetic_intelligence_sut(
            build_blind_case_input(case, context_reset_token="t")
        )
        self.assertNotIn("gold_answer", response)


if __name__ == "__main__":
    unittest.main()
