"""P1-5 / P2-4: unadmitted captures and donor execution cannot reach gated surfaces."""

from __future__ import annotations

import ast
import inspect
import unittest
from dataclasses import replace
from pathlib import Path

from market_platform_foundation.intelligence.dataset_admission import (
    UNADMITTED_CAPTURE_CODE,
    assert_admitted_for_order_ready,
    assert_admitted_for_promotion,
    assert_admitted_for_training,
    is_unadmitted_capture,
    UnadmittedCaptureError,
)
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository
from market_platform_foundation.intelligence.promotion import PromotionEngine, PromotionError
from market_platform_foundation.intelligence.training import TrainingFactory, TrainingFactoryError
from market_platform_foundation.strategy.scanning import ScanResult, UniversalStrategyScanner
from tests.intelligence.outcome_fixtures import T
from tests.intelligence.promotion_fixtures import (
    bootstrap_control_champion,
    default_promotion_policy,
    validated_candidate_bundle,
)
from tests.intelligence.test_training_factory import _experiment_manifest

PLATFORM_SRC = Path(__file__).resolve().parents[2] / "src" / "market_platform_foundation"

DONOR_EXECUTION_IMPORT_FRAGMENTS = (
    "eric_futuresx",
    "futuresx-main",
    "futuresx_main",
    "internship-project",
    "internship_project",
    "tradingcvdbubble",
    "l1volumebubble",
)

DONOR_BRIDGE_FORBIDDEN_SYMBOLS = frozenset(
    {
        "OrderReadyV1",
        "PaperExecutionOrchestrator",
        "submit_prepared",
        "TradeProposalV1",
    }
)


class UnadmittedCaptureGuardTests(unittest.TestCase):
    def test_explicit_unadmitted_metadata_is_rejected(self) -> None:
        self.assertTrue(is_unadmitted_capture({"admitted_research_dataset": False}))
        self.assertTrue(is_unadmitted_capture({"dataset_admission": "UNADMITTED"}))
        self.assertTrue(is_unadmitted_capture({"live_opt_in_capture": True}))
        self.assertFalse(is_unadmitted_capture({}))
        self.assertFalse(is_unadmitted_capture({"admitted_research_dataset": True}))

    def test_training_factory_rejects_unadmitted_capture(self) -> None:
        factory = TrainingFactory(InMemoryIntelligenceRepository())
        manifest = replace(
            _experiment_manifest(),
            metadata={"admitted_research_dataset": False, "live_opt_in_capture": True},
        )
        with self.assertRaises(TrainingFactoryError) as ctx:
            factory.generate_candidates(manifest)
        self.assertEqual(ctx.exception.code, UNADMITTED_CAPTURE_CODE)

    def test_promotion_rejects_unadmitted_capture(self) -> None:
        engine = PromotionEngine()
        _repo, _manifest, candidate, _bytes, report, _plan = validated_candidate_bundle()
        dirty = replace(candidate, metadata={**candidate.metadata, "dataset_admission": "UNADMITTED"})
        champion = bootstrap_control_champion(engine, candidate, effective_from_ns=T)
        with self.assertRaises(PromotionError) as ctx:
            engine.register_challenger(
                policy=default_promotion_policy(),
                candidate=dirty,
                validation_report=report,
                current_champion=champion,
                registered_at_ns=T,
            )
        self.assertEqual(ctx.exception.code, UNADMITTED_CAPTURE_CODE)

    def test_order_ready_guard_rejects_unadmitted_capture(self) -> None:
        with self.assertRaises(UnadmittedCaptureError):
            assert_admitted_for_order_ready({"live_provider_capture": True})
        assert_admitted_for_training({"admitted_research_dataset": True})
        assert_admitted_for_promotion(None)

    def test_research_scanner_cannot_construct_order_ready(self) -> None:
        self.assertNotIn("order_ready", ScanResult.__dataclass_fields__)
        run_source = inspect.getsource(UniversalStrategyScanner.run)
        self.assertNotIn("put_order_ready", run_source)
        self.assertNotIn("OrderReadyV1", run_source)


class DonorExecutionIsolationTests(unittest.TestCase):
    def test_platform_source_does_not_import_donor_execution_trees(self) -> None:
        hits: list[str] = []
        for path in PLATFORM_SRC.rglob("*.py"):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                names: list[str] = []
                if isinstance(node, ast.Import):
                    names.extend(alias.name.lower() for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names.append(node.module.lower())
                for name in names:
                    normalized = name.replace("_", "-")
                    if any(fragment in normalized or fragment in name for fragment in DONOR_EXECUTION_IMPORT_FRAGMENTS):
                        if "donor-patterns" in normalized or "donor-bridge" in normalized:
                            continue
                        hits.append(f"{path}:{name}")
        self.assertEqual(hits, [])

    def test_donor_bridge_does_not_import_order_ready_or_paper_submit(self) -> None:
        bridge_root = PLATFORM_SRC / "donor_bridge"
        if not bridge_root.exists():
            self.skipTest("donor_bridge not present")
        hits: list[str] = []
        for path in bridge_root.rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            for symbol in DONOR_BRIDGE_FORBIDDEN_SYMBOLS:
                if symbol in source:
                    hits.append(f"{path.name}:{symbol}")
        self.assertEqual(hits, [])


if __name__ == "__main__":
    unittest.main()
