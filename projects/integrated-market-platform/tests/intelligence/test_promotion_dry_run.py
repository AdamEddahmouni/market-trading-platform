"""Hardening P0-2 — promotion dry-run harness tests.

The dry run replays recorded paper outcomes through the BUILD 20 promotion
ladder and freezes an immutable decision record. These tests prove the ladder
works and that the record grants no execution authority.
"""

from __future__ import annotations

import unittest

from market_platform_foundation.intelligence.promotion import PromotionEngine
from market_platform_foundation.intelligence.promotion.dry_run import (
    DRY_RUN_DISALLOWED_TOKENS,
    PromotionDryRunRecord,
    run_promotion_dry_run,
)
from market_platform_foundation.intelligence.promotion.shadow import (
    build_shadow_evidence_manifest,
)
from market_platform_foundation.intelligence.promotion.types import (
    PromotionDecisionKind,
    ShadowMatchedObservation,
)
from market_platform_foundation.intelligence.research_experiments.types import EvidenceTier
from tests.intelligence.outcome_fixtures import T
from tests.intelligence.promotion_fixtures import (
    bootstrap_control_champion,
    default_promotion_policy,
    shadow_observations,
    shadow_promotion_policy,
    validated_candidate_bundle,
)


class PromotionDryRunTests(unittest.TestCase):
    def _promote_setup(self, *, required_improvement=0.001, better=True, policy=None):
        engine = PromotionEngine()
        _repo, manifest, candidate, artifact_bytes, report, _plan = validated_candidate_bundle(
            candidate_better=better
        )
        policy = policy or default_promotion_policy(required_improvement=required_improvement)
        champion = bootstrap_control_champion(engine, candidate)
        registration = engine.register_challenger(
            policy=policy,
            candidate=candidate,
            validation_report=report,
            current_champion=champion,
            registered_at_ns=T,
            candidate_artifact_bytes=artifact_bytes,
        )
        shadow = build_shadow_evidence_manifest(
            challenger_registration_id=registration.challenger_registration_id,
            champion_assignment_id=champion.assignment_id,
            promotion_policy_id=policy.promotion_policy_id,
            evidence_tier=EvidenceTier.OBSERVED_REPLAY,
            matched_observations=tuple(
                ShadowMatchedObservation(**row)
                for row in shadow_observations(4, challenger_better=better)
            ),
        )
        refs = {
            "preregistration_refs": (
                "PREREG-test-strategy-identity",
                candidate.candidate_id,
            ),
            "evidence_refs": (report.validation_report_id, shadow.shadow_evidence_id),
        }
        return dict(
            engine=engine,
            policy=policy,
            candidate=candidate,
            validation_report=report,
            challenger_registration=registration,
            current_champion=champion,
            shadow_evidence=shadow,
            experiment=manifest,
            **refs,
        )

    def test_dry_run_emits_immutable_promote_record(self) -> None:
        kwargs = self._promote_setup()
        record = run_promotion_dry_run(**kwargs)
        self.assertIsInstance(record, PromotionDryRunRecord)
        self.assertEqual(record.decision.decision, PromotionDecisionKind.PROMOTE)
        self.assertFalse(record.grants_execution_authority)

    def test_dry_run_record_is_deterministic(self) -> None:
        kwargs = self._promote_setup()
        first = run_promotion_dry_run(**kwargs)
        second = run_promotion_dry_run(**kwargs)
        self.assertEqual(first.dry_run_id, second.dry_run_id)
        self.assertEqual(
            first.decision.promotion_decision_id,
            second.decision.promotion_decision_id,
        )

    def test_dry_run_retain_record_is_distinct_but_deterministic(self) -> None:
        retain = run_promotion_dry_run(**self._promote_setup(required_improvement=0.5))
        promote = run_promotion_dry_run(**self._promote_setup(required_improvement=0.001))
        self.assertEqual(retain.decision.decision, PromotionDecisionKind.RETAIN_CHAMPION)
        self.assertEqual(promote.decision.decision, PromotionDecisionKind.PROMOTE)
        self.assertNotEqual(retain.dry_run_id, promote.dry_run_id)
        self.assertEqual(
            retain.dry_run_id,
            run_promotion_dry_run(**self._promote_setup(required_improvement=0.5)).dry_run_id,
        )

    def test_record_pins_preregistration_and_evidence_refs(self) -> None:
        kwargs = self._promote_setup()
        record = run_promotion_dry_run(**kwargs)
        for ref in kwargs["preregistration_refs"]:
            self.assertIn(ref, record.preregistration_refs)
        for ref in kwargs["evidence_refs"]:
            self.assertIn(ref, record.evidence_refs)

    def test_insufficient_shadow_evidence_returns_inconclusive_record(self) -> None:
        kwargs = self._promote_setup(
            policy=shadow_promotion_policy(minimum_shadow_samples=10)
        )
        record = run_promotion_dry_run(**{**kwargs, "shadow_evidence": None})
        self.assertEqual(record.decision.decision, PromotionDecisionKind.INCONCLUSIVE)

    def test_dry_run_has_no_execution_authority_surface(self) -> None:
        source = open(
            "src/market_platform_foundation/intelligence/promotion/dry_run.py",
            encoding="utf-8",
        ).read()
        # The harness may never import from an execution, portfolio or paper module.
        for module_root in (
            "from ..execution",
            "from ..portfolio",
            "from ..paper",
            "from .execution",
            "import execution",
        ):
            self.assertNotIn(module_root, source)
        # A dry-run record can never claim execution authority.
        record = run_promotion_dry_run(**self._promote_setup())
        self.assertFalse(record.grants_execution_authority)
        # Neither the record nor the decision schema exposes an execution surface.
        self.assertFalse(hasattr(record, "execution_mode"))
        self.assertFalse(hasattr(record.decision, "execution_mode"))
        self.assertIn("grants_execution_authority", source)


if __name__ == "__main__":
    unittest.main()
