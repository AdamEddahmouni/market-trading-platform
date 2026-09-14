"""Non-semantic persistence and Paper comparator contracts.

No orders. Live host forbidden. Threshold SET without a value is blocking.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.execution.simulator import (  # noqa: E402
    SIMULATOR_VERSION,
    SOURCE_CAPABILITY,
)
from market_platform_foundation.intelligence.paper_forward_bridge.paper_ledger_join import (  # noqa: E402
    paper_execution_from_ledger,
)
from market_platform_foundation.local_state.connection import LocalStateConnection  # noqa: E402
from market_platform_foundation.local_state.paths import persistence_enabled  # noqa: E402
from market_platform_foundation.local_state.startup import (  # noqa: E402
    configuration_hash,
    open_local_state,
    reset_local_state_for_tests,
)
from market_platform_foundation.paper.calibration.comparator_contract import (  # noqa: E402
    COMPARATOR_NOT_MARKET_TRUTH_STATEMENT,
    ComparatorContractError,
    validate_comparator_binding,
)
from market_platform_foundation.paper.calibration.metrics import FillObservation  # noqa: E402
from market_platform_foundation.paper.calibration.pairing import (  # noqa: E402
    PAIR_CONFIDENCE_HIGH,
    PAIR_METHOD_CORRELATION_ID,
    PairedObservation,
)
from market_platform_foundation.paper.calibration.persistence import (  # noqa: E402
    build_pair_observation_payload,
)
from market_platform_foundation.paper.calibration.thresholds import (  # noqa: E402
    CalibrationThresholdError,
    default_unset_threshold_config,
    validate_threshold_config,
)


class PersistenceGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self._persist = os.environ.pop("IMP_PERSIST_STATE", None)
        self._state_dir = os.environ.pop("IMP_STATE_DIR", None)
        reset_local_state_for_tests()

    def tearDown(self) -> None:
        reset_local_state_for_tests()
        if self._persist is None:
            os.environ.pop("IMP_PERSIST_STATE", None)
        else:
            os.environ["IMP_PERSIST_STATE"] = self._persist
        if self._state_dir is None:
            os.environ.pop("IMP_STATE_DIR", None)
        else:
            os.environ["IMP_STATE_DIR"] = self._state_dir

    def test_persist_off_does_not_open_state(self) -> None:
        self.assertFalse(persistence_enabled())
        self.assertIsNone(open_local_state())

    def test_configuration_hash_is_deterministic(self) -> None:
        first = configuration_hash(
            data_mode="FIXTURE_REPLAY",
            execution_mode="INTERNAL_SIMULATION",
            data_provider="INTERNAL",
            execution_provider="INTERNAL",
            starting_cash_minor=100_000,
        )
        second = configuration_hash(
            data_mode="FIXTURE_REPLAY",
            execution_mode="INTERNAL_SIMULATION",
            data_provider="INTERNAL",
            execution_provider="INTERNAL",
            starting_cash_minor=100_000,
        )
        self.assertEqual(first, second)
        changed = configuration_hash(
            data_mode="FIXTURE_REPLAY",
            execution_mode="INTERNAL_SIMULATION",
            data_provider="INTERNAL",
            execution_provider="INTERNAL",
            starting_cash_minor=100_001,
        )
        self.assertNotEqual(first, changed)


class PaperLedgerJoinSqliteTests(unittest.TestCase):
    def test_fill_then_position_join_is_order_scoped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            connection = LocalStateConnection(Path(tmp) / "imp-state.sqlite3")
            try:
                connection.execute(
                    """
                    INSERT INTO paper_events(
                        event_id, session_id, event_type, event_time, available_time,
                        correlation_id, payload_json, schema_version, sequence
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "evt-fill",
                        "sess-1",
                        "FillRecorded",
                        10,
                        10,
                        "corr-1",
                        json.dumps({"order_id": "ord-1"}),
                        1,
                        1,
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO paper_events(
                        event_id, session_id, event_type, event_time, available_time,
                        correlation_id, payload_json, schema_version, sequence
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "evt-pos",
                        "sess-1",
                        "PositionChanged",
                        11,
                        11,
                        "corr-1",
                        json.dumps({"realized_pnl_minor": 25, "unrealized_pnl_minor": 3}),
                        1,
                        2,
                    ),
                )
                realized, fill_count, unrealized = paper_execution_from_ledger(
                    connection,
                    paper_order_id="ord-1",
                )
                self.assertEqual(realized, 25)
                self.assertEqual(fill_count, 1)
                self.assertEqual(unrealized, 3)
                missed, other_fills, _ = paper_execution_from_ledger(
                    connection,
                    paper_order_id="ord-other",
                )
                self.assertIsNone(missed)
                self.assertEqual(other_fills, 0)
            finally:
                connection.close()


class ComparatorContractTests(unittest.TestCase):
    def test_incomplete_binding_and_missing_limitations_fail_closed(self) -> None:
        with self.assertRaises(ComparatorContractError) as ctx:
            validate_comparator_binding(
                {"comparator_id": "tradier", "environment": "sandbox", "account_mode": ""}
            )
        self.assertEqual(str(ctx.exception), "COMPARATOR_BINDING_INCOMPLETE")
        with self.assertRaises(ComparatorContractError) as ctx:
            validate_comparator_binding(
                {
                    "comparator_id": "tradier",
                    "environment": "sandbox",
                    "account_mode": "paper",
                    "limitations": [],
                }
            )
        self.assertEqual(str(ctx.exception), "COMPARATOR_LIMITATIONS_REQUIRED")

    def test_live_account_mode_forbidden(self) -> None:
        with self.assertRaises(ComparatorContractError) as ctx:
            validate_comparator_binding(
                {
                    "comparator_id": "tradier",
                    "environment": "sandbox",
                    "account_mode": "live",
                    "limitations": ["equity_only"],
                }
            )
        self.assertEqual(str(ctx.exception), "COMPARATOR_LIVE_ACCOUNT_FORBIDDEN")

    def test_binding_to_dict_declares_not_market_truth(self) -> None:
        binding = validate_comparator_binding(
            {
                "comparator_id": "tradier",
                "environment": "sandbox",
                "account_mode": "paper",
                "limitations": ["equity_only"],
            }
        )
        payload = binding.to_dict()
        self.assertFalse(payload["is_market_truth"])
        self.assertEqual(
            payload["not_market_truth_statement"],
            COMPARATOR_NOT_MARKET_TRUTH_STATEMENT,
        )

    def test_threshold_set_without_value_fail_closed(self) -> None:
        payload = default_unset_threshold_config().to_dict()
        payload["thresholds"]["fill_no_fill_disagreement_rate_max"] = {"status": "SET"}
        with self.assertRaises(CalibrationThresholdError) as ctx:
            validate_threshold_config(payload)
        self.assertIn("CALIBRATION_THRESHOLD_VALUE_REQUIRED", str(ctx.exception))

    def test_unset_threshold_must_not_carry_a_value(self) -> None:
        payload = default_unset_threshold_config().to_dict()
        payload["thresholds"]["timing_error_max_ns"] = {
            "status": "UNSET/BLOCKING",
            "value": 1,
        }
        with self.assertRaises(CalibrationThresholdError) as ctx:
            validate_threshold_config(payload)
        self.assertIn("CALIBRATION_THRESHOLD_UNSET_MUST_NOT_HAVE_VALUE", str(ctx.exception))

    def test_pair_observation_payload_never_claims_calibrated(self) -> None:
        binding = validate_comparator_binding(
            {
                "comparator_id": "tradier",
                "environment": "sandbox",
                "account_mode": "paper",
                "limitations": ["equity_only"],
            }
        )
        pair = PairedObservation(
            correlation_id="forward_test:ftd-1",
            forward_test_id="ftd-1",
            paper_order_id="ord-1",
            comparator_order_id="cmp-1",
            pair_method=PAIR_METHOD_CORRELATION_ID,
            pair_confidence=PAIR_CONFIDENCE_HIGH,
            simulator_version=SIMULATOR_VERSION,
            source_capability=SOURCE_CAPABILITY,
            paper_account_id="acct-1",
            instrument_id="AAPL",
            asset_class="US_EQUITY",
            imp=FillObservation(order_id="ord-1", filled=True),
            comparator=FillObservation(order_id="cmp-1", filled=True),
            observable=True,
        )
        payload = build_pair_observation_payload(
            pair,
            comparator=binding,
            evidence_class="CANDIDATE",
            observation_label="pair",
        )
        self.assertFalse(payload["calibrated"])
        self.assertFalse(payload["empirical_active"])
        self.assertFalse(payload["is_market_truth"])
        self.assertEqual(
            payload["comparator_binding"]["not_market_truth_statement"],
            COMPARATOR_NOT_MARKET_TRUTH_STATEMENT,
        )


if __name__ == "__main__":
    unittest.main()
