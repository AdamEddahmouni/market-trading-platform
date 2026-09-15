"""Strategy research promotion registry tests (Phase 5 Lane J)."""

from __future__ import annotations

import unittest

from market_platform_foundation.intelligence.contracts.common import INTELLIGENCE_SCHEMA_VERSION
from market_platform_foundation.intelligence.promotion import (
    PromotionError,
    ResearchPromotionReasonCode,
    RuntimeParityComparisonRecordV1,
    RuntimeParityDisposition,
    STRATEGY_RESEARCH_PROMOTION_REGISTRY_READY,
    StrategyResearchEvidenceBundleV1,
    StrategyResearchPromotionLifecycleState,
    StrategyResearchPromotionRegistry,
    assess_auto_execution_authority,
    minimal_research_result,
    runtime_parity_comparison_record_v1_from_dict,
    runtime_parity_comparison_record_v1_to_dict,
    strategy_research_promotion_record_v1_from_dict,
    strategy_research_promotion_record_v1_to_dict,
)
from market_platform_foundation.strategy import eligibility as strategy_eligibility


def _full_evidence(*, strategy_id: str = "STRAT-1") -> StrategyResearchEvidenceBundleV1:
    return StrategyResearchEvidenceBundleV1(
        strategy_id=strategy_id,
        runtime_id="python",
        runtime_version="3.11.0",
        source_hash="sha256:source",
        dataset_hashes=("sha256:dataset-a",),
        pit_classification="PIT-PASS",
        in_sample_result=minimal_research_result(
            summary_id="is-1",
            metric_name="sharpe",
            metric_value=1.1,
            sample_count=120,
            window_label="in_sample",
        ),
        out_of_sample_result=minimal_research_result(
            summary_id="oos-1",
            metric_name="sharpe",
            metric_value=0.6,
            sample_count=40,
            window_label="out_of_sample",
        ),
        walk_forward_result=minimal_research_result(
            summary_id="wf-1",
            metric_name="sharpe",
            metric_value=0.5,
            sample_count=5,
            window_label="walk_forward",
        ),
        transaction_cost_assumptions="10bps round-trip; linear slippage",
        regime_sensitivity="stable across high/low vol buckets",
        capacity_liquidity_notes="<=5% ADV without impact escalation",
        multiple_testing_controls="bonferroni across 3 variants",
        challenger_results=("challenger_beat_baseline_holdout",),
        known_contradictions=("NONE_OBSERVED",),
    )


def _parity_record(*, strategy_id: str = "STRAT-1") -> RuntimeParityComparisonRecordV1:
    return RuntimeParityComparisonRecordV1(
        comparison_id="parity-python-matlab-1",
        schema_version=INTELLIGENCE_SCHEMA_VERSION,
        strategy_id=strategy_id,
        reference_runtime_id="python",
        candidate_runtime_id="matlab",
        reference_source_hash="sha256:py",
        candidate_source_hash="sha256:ml",
        disposition=RuntimeParityDisposition.PASS,
        metric_comparisons=(
            {"metric_name": "signal_correlation", "delta": 0.01, "tolerance": 0.05},
        ),
    )


class StrategyResearchPromotionRegistryTests(unittest.TestCase):
    def test_lifecycle_transitions_forward_only(self) -> None:
        registry = StrategyResearchPromotionRegistry()
        record = registry.register_discovered(strategy_id="STRAT-1", effective_at_ns=1)
        registry.upsert_evidence(
            record.promotion_record_id,
            _full_evidence(strategy_id="STRAT-1"),
        )
        registry.attach_parity_record(record.promotion_record_id, _parity_record())
        path = [
            StrategyResearchPromotionLifecycleState.RUNNABLE,
            StrategyResearchPromotionLifecycleState.PARITY_CHECKED,
            StrategyResearchPromotionLifecycleState.HISTORICAL_VALIDATED,
            StrategyResearchPromotionLifecycleState.OOS_VALIDATED,
            StrategyResearchPromotionLifecycleState.RESEARCH_APPROVED,
            StrategyResearchPromotionLifecycleState.FTEP_ELIGIBLE,
            StrategyResearchPromotionLifecycleState.FTEP_TESTING,
            StrategyResearchPromotionLifecycleState.PROMOTION_REVIEW,
        ]
        current = record
        for index, target in enumerate(path, start=2):
            current = registry.transition(
                current.promotion_record_id,
                to_state=target,
                effective_at_ns=index,
            )
        self.assertEqual(
            current.lifecycle_state,
            StrategyResearchPromotionLifecycleState.PROMOTION_REVIEW,
        )
        self.assertTrue(current.review_eligible)
        history = registry.transition_history(current.promotion_record_id)
        self.assertEqual(len(history), len(path) + 1)

    def test_missing_evidence_fails_closed(self) -> None:
        registry = StrategyResearchPromotionRegistry()
        record = registry.register_discovered(strategy_id="STRAT-2", effective_at_ns=1)
        with self.assertRaises(PromotionError) as ctx:
            registry.transition(
                record.promotion_record_id,
                to_state=StrategyResearchPromotionLifecycleState.RUNNABLE,
                effective_at_ns=2,
            )
        self.assertEqual(ctx.exception.code, ResearchPromotionReasonCode.EVIDENCE_INCOMPLETE.value)

    def test_auto_paper_live_activation_forbidden(self) -> None:
        registry = StrategyResearchPromotionRegistry()
        record = registry.register_discovered(strategy_id="STRAT-3", effective_at_ns=1)
        registry.upsert_evidence(record.promotion_record_id, _full_evidence(strategy_id="STRAT-3"))
        registry.attach_parity_record(record.promotion_record_id, _parity_record(strategy_id="STRAT-3"))
        for target in (
            StrategyResearchPromotionLifecycleState.RUNNABLE,
            StrategyResearchPromotionLifecycleState.PARITY_CHECKED,
            StrategyResearchPromotionLifecycleState.HISTORICAL_VALIDATED,
            StrategyResearchPromotionLifecycleState.OOS_VALIDATED,
            StrategyResearchPromotionLifecycleState.RESEARCH_APPROVED,
            StrategyResearchPromotionLifecycleState.FTEP_ELIGIBLE,
            StrategyResearchPromotionLifecycleState.FTEP_TESTING,
            StrategyResearchPromotionLifecycleState.PROMOTION_REVIEW,
        ):
            record = registry.transition(
                record.promotion_record_id,
                to_state=target,
                effective_at_ns=3,
            )
        granted, reasons = assess_auto_execution_authority(record)
        self.assertFalse(granted)
        self.assertIn(
            ResearchPromotionReasonCode.AUTO_PAPER_LIVE_ACTIVATION_FORBIDDEN,
            reasons,
        )
        self.assertFalse(record.grants_execution_authority)

    def test_generic_parity_record_round_trip(self) -> None:
        parity = _parity_record()
        pinets = RuntimeParityComparisonRecordV1(
            comparison_id="parity-python-pinets-1",
            schema_version=INTELLIGENCE_SCHEMA_VERSION,
            strategy_id="STRAT-1",
            reference_runtime_id="python",
            candidate_runtime_id="pinets",
            reference_source_hash="sha256:py",
            candidate_source_hash="sha256:pine",
            disposition=RuntimeParityDisposition.INCONCLUSIVE,
            metric_comparisons=(),
            notes="adapter pending merge",
        )
        restored = runtime_parity_comparison_record_v1_from_dict(
            runtime_parity_comparison_record_v1_to_dict(parity)
        )
        self.assertEqual(restored.reference_runtime_id, "python")
        self.assertEqual(restored.candidate_runtime_id, "matlab")
        restored_pinets = runtime_parity_comparison_record_v1_from_dict(
            runtime_parity_comparison_record_v1_to_dict(pinets)
        )
        self.assertEqual(restored_pinets.candidate_runtime_id, "pinets")

    def test_promotion_record_serialization_round_trip(self) -> None:
        registry = StrategyResearchPromotionRegistry()
        record = registry.register_discovered(strategy_id="STRAT-4", effective_at_ns=1)
        registry.upsert_evidence(record.promotion_record_id, _full_evidence(strategy_id="STRAT-4"))
        restored = strategy_research_promotion_record_v1_from_dict(
            strategy_research_promotion_record_v1_to_dict(registry.get(record.promotion_record_id))
        )
        self.assertEqual(restored.strategy_id, "STRAT-4")
        self.assertFalse(restored.grants_execution_authority)

    def test_registry_does_not_mutate_strategy_execution_eligibility_module(self) -> None:
        before = (
            strategy_eligibility.EXECUTION_ELIGIBILITY_SCHEMA_VERSION,
            strategy_eligibility.GATE_REASON_CODE,
            strategy_eligibility.FORWARD_EVIDENCE_CLASSES_FOR_EXECUTION_INTENT,
        )
        registry = StrategyResearchPromotionRegistry()
        record = registry.register_discovered(strategy_id="STRAT-5", effective_at_ns=1)
        registry.upsert_evidence(record.promotion_record_id, _full_evidence(strategy_id="STRAT-5"))
        registry.attach_parity_record(record.promotion_record_id, _parity_record(strategy_id="STRAT-5"))
        for target in (
            StrategyResearchPromotionLifecycleState.RUNNABLE,
            StrategyResearchPromotionLifecycleState.PARITY_CHECKED,
            StrategyResearchPromotionLifecycleState.HISTORICAL_VALIDATED,
            StrategyResearchPromotionLifecycleState.OOS_VALIDATED,
            StrategyResearchPromotionLifecycleState.RESEARCH_APPROVED,
        ):
            registry.transition(
                record.promotion_record_id,
                to_state=target,
                effective_at_ns=2,
            )
        after = (
            strategy_eligibility.EXECUTION_ELIGIBILITY_SCHEMA_VERSION,
            strategy_eligibility.GATE_REASON_CODE,
            strategy_eligibility.FORWARD_EVIDENCE_CLASSES_FOR_EXECUTION_INTENT,
        )
        self.assertEqual(before, after)


class StrategyResearchPromotionRegistryAcceptanceTests(unittest.TestCase):
    def test_strategy_research_promotion_registry_ready(self) -> None:
        registry = StrategyResearchPromotionRegistry()
        record = registry.register_discovered(strategy_id="ACCEPT-STRAT", effective_at_ns=1)
        registry.upsert_evidence(
            record.promotion_record_id,
            _full_evidence(strategy_id="ACCEPT-STRAT"),
        )
        registry.attach_parity_record(
            record.promotion_record_id,
            _parity_record(strategy_id="ACCEPT-STRAT"),
        )
        for target in (
            StrategyResearchPromotionLifecycleState.RUNNABLE,
            StrategyResearchPromotionLifecycleState.PARITY_CHECKED,
            StrategyResearchPromotionLifecycleState.HISTORICAL_VALIDATED,
            StrategyResearchPromotionLifecycleState.OOS_VALIDATED,
            StrategyResearchPromotionLifecycleState.RESEARCH_APPROVED,
            StrategyResearchPromotionLifecycleState.FTEP_ELIGIBLE,
            StrategyResearchPromotionLifecycleState.FTEP_TESTING,
            StrategyResearchPromotionLifecycleState.PROMOTION_REVIEW,
        ):
            record = registry.transition(
                record.promotion_record_id,
                to_state=target,
                effective_at_ns=3,
            )
        self.assertEqual(STRATEGY_RESEARCH_PROMOTION_REGISTRY_READY, "STRATEGY_RESEARCH_PROMOTION_REGISTRY_READY")
        self.assertTrue(record.review_eligible)
        self.assertFalse(record.grants_execution_authority)


if __name__ == "__main__":
    unittest.main()
