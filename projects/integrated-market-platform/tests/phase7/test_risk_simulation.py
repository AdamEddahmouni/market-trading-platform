"""Phase 7 risk, simulation, and accounting tests."""

from __future__ import annotations

import unittest

from market_platform_foundation.risk.decision import evaluate_risk
from market_platform_foundation.risk.kill_switch import KillSwitchState
from market_platform_foundation.risk.policy import DEFAULT_RISK_POLICY
from market_platform_foundation.risk_simulation.evaluation import (
    audit_fill_eligibility,
    run_risk_simulation_evaluation,
    risk_simulation_root_hash,
)


def _synthetic_events(count: int = 8) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    base = 2_000_000_000_000_000_000
    for index in range(count):
        available = base + index * 60_000_000_000
        events.append(
            {
                "available_time": available,
                "bar_payload": {
                    "close": str(100 + index),
                    "high": str(101 + index),
                    "low": str(99 + index),
                    "open": str(100 + index),
                    "timeframe": "1_MINUTE",
                    "volume": 10000 + index * 100,
                },
                "channel_id": "EQ-1",
                "event_time": available - 1,
                "event_type": "BAR_OHLCV_1M",
                "historical_ingested_time": available,
                "ingest_run_id": "RUN-SYNTH",
                "instrument_id": "EQ-1",
                "normalization_version": "test/1.0.0",
                "normalized_event_id": f"evt-{index}",
                "operation": "UPSERT",
                "publisher_id": "PUB-1",
                "quality_observation_refs": [],
                "raw_reference": f"test://{index}",
                "schema_version": "1.0.0",
                "source_instance_id": "SRC-1",
                "source_record_id": f"REC-{index}",
                "source_revision_id": "1",
                "venue_id": "VEN-1",
            }
        )
    return events


class Phase7Tests(unittest.TestCase):
    def test_kill_switch_rejects(self) -> None:
        intent = {
            "desired_quantity": 10,
            "direction": "long",
            "instrument_id": "EQ-1",
            "intent_id": "INTENT-1",
        }
        decision = evaluate_risk(
            intent=intent,
            policy=DEFAULT_RISK_POLICY,
            kill_switch=KillSwitchState(active=True, reason_code="TEST"),
            current_position_shares=0,
            open_order_count=0,
        )
        self.assertEqual(decision["decision"], "REJECT")

    def test_pre_activation_fill_audit_fails(self) -> None:
        audit = audit_fill_eligibility(
            [],
            [{"activation_time": 1000, "fill_id": "F1", "fill_time": 900}],
        )
        self.assertEqual(audit["status"], "FAIL")

    def test_risk_simulation_deterministic(self) -> None:
        events = _synthetic_events(10)
        result_a = run_risk_simulation_evaluation(events)
        result_b = run_risk_simulation_evaluation(events)
        self.assertEqual(risk_simulation_root_hash(result_a), risk_simulation_root_hash(result_b))
        self.assertEqual(result_a["reconciliation"]["status"], "PASS")


if __name__ == "__main__":
    unittest.main()
