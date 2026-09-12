"""FTEP-V1 session launch-policy enforcement tests."""

from __future__ import annotations

import os
import sys
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.paper_forward_bridge.activation import (  # noqa: E402
    ActivationManifest,
    freeze_manifest,
    load_activation_manifest,
    normalize_manifest,
    write_activation_manifest,
)
from market_platform_foundation.intelligence.paper_forward_bridge.protocol_ref import (  # noqa: E402
    write_test_protocol_ref,
)
from market_platform_foundation.intelligence.paper_forward_bridge.session_policy import (  # noqa: E402
    CALENDAR_US_EQUITY_RTH,
    assert_decision_within_calendar,
    assert_evaluation_force_allowed,
    assert_evidence_class_fail_closed,
    assert_execution_phase_gate,
    assert_no_concurrent_overlap,
    assess_sample_floor_disposition,
    authority_strategy_binding,
    calendar_scope_from_manifest,
    count_integrity_clean_locks,
    is_within_us_equity_rth,
    phase_gate_from_manifest,
    SessionPolicyError,
)
from market_platform_foundation.intelligence.paper_forward_bridge import (  # noqa: E402
    ForwardTestMode,
    ForwardTestService,
    ForwardTestServiceError,
    ForwardTestState,
    ForwardTestStore,
)
from market_platform_foundation.intelligence.paper_forward_bridge.types import (  # noqa: E402
    ForwardTestEvidenceClass,
)
from forward_test_activation_support import (  # noqa: E402
    ActivatedForwardTestCase,
    BASELINE_POLICY,
    CAMPAIGN_SLUG,
    HOUR_NS,
    POLICY_VERSION,
    create_activated_session,
    enable_test_campaigns_root,
    seed_baseline_campaign,
)

ET = ZoneInfo("America/New_York")
_NS = 1_000_000_000
T_RTH = int(datetime(2024, 1, 16, 15, 0, 0, tzinfo=ET).timestamp() * _NS)


def _manifest_with_policy(**overrides: object) -> ActivationManifest:
    raw = normalize_manifest(
        {
            "campaign_slug": CAMPAIGN_SLUG,
            "schema_version": "intelligence/paper_forward_bridge/activation_manifest/1.0.0",
            "manifest_schema_version": 1,
            "protocol_id": "FTEP-V1/0.1.0-PREREG",
            "activation_status": "FROZEN",
            "calendar_scope": CALENDAR_US_EQUITY_RTH,
            "overlap_policy": "FORBID_CONCURRENT",
            "test_mode_phase_1": "SIGNAL_ONLY",
            "test_mode_phase_2": "EXECUTION",
            "phase_transition_min_locks": 5,
            "sample_floors": {
                "locked_decisions": 30,
                "evaluated_decisions": 15,
                "distinct_trading_days": 5,
                "qualifying_sessions": 5,
                "execution_mode_decisions": 10,
                "per_arm_minimum": 10,
            },
            "duration_floors": {
                "min_qualifying_sessions": 5,
                "min_session_duration_ns": 300_000_000_000,
                "min_distinct_trading_days": 5,
            },
            "horizons_ns": [HOUR_NS],
            "paper_account_id": "paper-a",
            "recommended_not_binding": {
                "baseline_policy_id": "news_deterministic_baseline@1.0.0",
                "ai_policy_id": "news_ai_enhanced@1.0.0",
                "universe": ["ACME", "ES"],
            },
            "resolved_fields": {
                "FTEP-ACT-05": {"resolution": "IMP_PERSIST_STATE_REQUIRED"},
                "FTEP-D004": {
                    "classification": "DETERMINISTIC_FROM_AUTHORITY",
                    "resolution": "news_deterministic_baseline@1.0.0",
                    "conditional_on": "OD-1=A",
                },
                "FTEP-D005": {
                    "classification": "DETERMINISTIC_FROM_AUTHORITY",
                    "resolution": "news_ai_enhanced@1.0.0",
                    "conditional_on": "OD-1=A",
                },
                "FTEP-D009": {
                    "classification": "DETERMINISTIC_FROM_AUTHORITY",
                    "resolution": "FUTURES_EQUITY_INDEX / ES",
                    "conditional_on": "OD-1=A",
                },
                "FTEP-ACT-02": {"resolution": 5},
            },
            **overrides,
        }
    )
    return ActivationManifest(raw=raw, path=Path("test.json"))


def _install_policy_manifest(campaigns_root: Path, **overrides: object) -> None:
    manifest = _manifest_with_policy(**overrides)
    manifest.raw["owner_decisions_required"] = []
    manifest.raw["unresolved_fields"] = []
    manifest.raw["activation_status"] = "PENDING_OWNER_DECISIONS"
    write_test_protocol_ref(campaigns_root, campaign_slug=CAMPAIGN_SLUG)
    path = campaigns_root / CAMPAIGN_SLUG / "ACTIVATION_MANIFEST.json"
    write_activation_manifest(path, manifest.raw, campaigns_root_override=campaigns_root)
    loaded = load_activation_manifest(CAMPAIGN_SLUG, campaigns_root_override=campaigns_root)
    frozen = freeze_manifest(loaded, frozen_at="2026-09-11T00:00:00Z")
    write_activation_manifest(path, frozen, campaigns_root_override=campaigns_root)


class SessionPolicyUnitTests(unittest.TestCase):
    def test_rth_window_detection(self) -> None:
        self.assertTrue(is_within_us_equity_rth(T_RTH))
        outside = int(datetime(2024, 1, 16, 8, 0, 0, tzinfo=ET).timestamp() * _NS)
        self.assertFalse(is_within_us_equity_rth(outside))

    def test_calendar_enforcement_blocks_outside_rth(self) -> None:
        outside = int(datetime(2024, 1, 16, 8, 0, 0, tzinfo=ET).timestamp() * _NS)
        with self.assertRaises(SessionPolicyError):
            assert_decision_within_calendar(
                decision_time_ns=outside,
                calendar_scope=CALENDAR_US_EQUITY_RTH,
            )

    def test_phase_gate_requires_clean_locks(self) -> None:
        manifest = _manifest_with_policy()
        phase = phase_gate_from_manifest(manifest)
        self.assertEqual(phase.min_integrity_clean_locks, 5)

    def test_sample_floor_disposition_separates_activation(self) -> None:
        manifest = _manifest_with_policy()
        disposition = assess_sample_floor_disposition(
            manifest=manifest,
            decisions=[],
            session_ids=("sess-1",),
        )
        self.assertFalse(disposition.statistical_disposition_ready)
        self.assertFalse(disposition.activation_ready)
        self.assertIn("SAMPLE_FLOOR_LOCKED_DECISIONS", disposition.blockers)

    def test_authority_strategy_binding_for_od1_option_a(self) -> None:
        binding = authority_strategy_binding(_manifest_with_policy())
        self.assertIsNotNone(binding)
        assert binding is not None
        self.assertEqual(binding["strategy_binding"], "A")
        self.assertEqual(binding["universe"], ["ES"])

    def test_evidence_class_fail_closed(self) -> None:
        with self.assertRaises(SessionPolicyError):
            assert_evidence_class_fail_closed(
                ForwardTestEvidenceClass.ACTUAL_FORWARD,
                boundary="CREATE",
            )

    def test_eval_force_forbidden_without_override(self) -> None:
        from market_platform_foundation.intelligence.paper_forward_bridge.types import (
            ForwardTestSession,
            ForwardTestSessionStatus,
        )

        session = ForwardTestSession(
            session_id="s1",
            account_id="paper-a",
            mode="PAPER",
            strategy_id="s",
            strategy_version="1.0.0",
            universe=("ES",),
            evaluation_horizon_ns=HOUR_NS,
            created_at_ns=T_RTH,
            status=ForwardTestSessionStatus.ACTIVE,
            campaign_id=CAMPAIGN_SLUG,
        )
        os.environ.pop("IMP_FORWARD_TEST_EVAL_FORCE", None)
        with self.assertRaises(SessionPolicyError):
            assert_evaluation_force_allowed(force=True, session=session)


class SessionPolicyRuntimeTests(ActivatedForwardTestCase):
    def setUp(self) -> None:
        super().setUp()
        os.environ["IMP_PERSIST_STATE"] = "1"
        os.environ["IMP_FORWARD_TEST_EVAL_FORCE"] = "1"

    def tearDown(self) -> None:
        os.environ.pop("IMP_PERSIST_STATE", None)
        os.environ.pop("IMP_FORWARD_TEST_EVAL_FORCE", None)
        super().tearDown()

    def test_execution_blocked_before_phase_gate(self) -> None:
        _install_policy_manifest(self.campaigns_root)
        store = ForwardTestStore()
        service = ForwardTestService(store)
        session = create_activated_session(
            service,
            self.campaigns_root,
            evaluation_horizon_ns=HOUR_NS,
            created_at_ns=T_RTH,
        )
        with self.assertRaises(ForwardTestServiceError) as ctx:
            service.create_decision(
                account_id="paper-a",
                mode="PAPER",
                session_id=session.session_id,
                symbol="ACME",
                direction="BUY",
                decision_time_ns=T_RTH,
                source_time_ns=T_RTH - 1,
                strategy_id=BASELINE_POLICY,
                strategy_version=POLICY_VERSION,
                test_mode=ForwardTestMode.EXECUTION,
            )
        self.assertIn("FORWARD_TEST_EXECUTION_PHASE_GATE", str(ctx.exception))

    def test_overlap_forbidden_when_policy_set(self) -> None:
        _install_policy_manifest(self.campaigns_root, overlap_policy="FORBID_CONCURRENT")
        store = ForwardTestStore()
        service = ForwardTestService(store)
        session = create_activated_session(
            service,
            self.campaigns_root,
            evaluation_horizon_ns=HOUR_NS,
            created_at_ns=T_RTH,
        )
        first = service.create_decision(
            account_id="paper-a",
            mode="PAPER",
            session_id=session.session_id,
            symbol="ACME",
            direction="BUY",
            decision_time_ns=T_RTH,
            source_time_ns=T_RTH - 1,
            strategy_id=BASELINE_POLICY,
            strategy_version=POLICY_VERSION,
            test_mode=ForwardTestMode.SIGNAL_ONLY,
        )
        with self.assertRaises(ForwardTestServiceError) as ctx:
            service.create_decision(
                account_id="paper-a",
                mode="PAPER",
                session_id=session.session_id,
                symbol="ACME",
                direction="SELL",
                decision_time_ns=T_RTH + 1,
                source_time_ns=T_RTH,
                strategy_id=BASELINE_POLICY,
                strategy_version=POLICY_VERSION,
                test_mode=ForwardTestMode.SIGNAL_ONLY,
            )
        self.assertIn("FORWARD_TEST_OVERLAP_FORBIDDEN", str(ctx.exception))
        self.assertEqual(first.state, ForwardTestState.DRAFT)


if __name__ == "__main__":
    unittest.main()
