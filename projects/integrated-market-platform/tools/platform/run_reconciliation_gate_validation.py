"""Platformization P4 / sub-milestone 4B gate validation (offline, deterministic).

Drives the reconciliation engine against a BROKER_PAPER ledger with one filled
Tradier sandbox order, polls the fixture-first provider for the broker order
status, asserts the ``P4-REC-*`` invariants, and writes
``evidence/platform/reconciliation-gate-report.json``. Strictly offline: the
engine performs no network I/O and the provider fails closed without a fixture
record.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from market_platform_foundation.offline_guard import install_guard  # noqa: E402
from market_platform_foundation.paper.contracts import build_instrument_ref  # noqa: E402
from market_platform_foundation.paper.broker_paper import submit_broker_paper_order  # noqa: E402
from market_platform_foundation.paper.ledger import PaperExecutionLedger  # noqa: E402
from market_platform_foundation.platform.reconciliation import (  # noqa: E402
    MATCHED,
    MISMATCH,
    BrokerOrderSnapshot,
    ReconciliationViolation,
    assert_no_unexplained_mismatch,
    build_reconciliation_report,
    hold_reconciliation,
    record_reconciliation,
    resolve_reconciliation_field,
)
from market_platform_foundation.providers.adapters.tradier_paper import (  # noqa: E402
    TRADIER_SANDBOX_ENDPOINT,
    TradierReplayStore,
    make_tradier_paper_provider,
)
from market_platform_foundation.providers.broker_execution import (  # noqa: E402
    BrokerAccountSnapshot,
    BrokerOrderStatusEvent,
    BrokerPositionSnapshot,
)

GATED_ENV = {
    "IMP_TRADIER_PAPER": "1",
    "IMP_BROKER_PAPER_EXECUTION": "1",
    "IMP_TRADIER_TOKEN": "gate-fixture-token",
    "IMP_TRADIER_ENDPOINT": TRADIER_SANDBOX_ENDPOINT,
    "IMP_TRADIER_ACCOUNT_ID": "gate-fixture-account",
}
SYMBOL_MAP = {"BIYA": "BIYA"}
INSTRUMENT = build_instrument_ref(instrument_id="BIYA", symbol="BIYA")
AS_OF_NS = 1787000000500000000

REPORT_PATH = ROOT / "evidence/platform/reconciliation-gate-report.json"


def _broker_ledger() -> PaperExecutionLedger:
    return PaperExecutionLedger.open_session(
        replay_session_id="p4-4b-gate",
        instrument_id="BIYA",
        symbol="BIYA",
        execution_mode="BROKER_PAPER",
        execution_authority="PAPER_ONLY",
        data_mode="BROKER_DELAYED",
        data_provider="TRADIER",
        execution_provider="TRADIER",
    )


def _filled_ledger(provider: object) -> PaperExecutionLedger:
    ledger = _broker_ledger()
    result = submit_broker_paper_order(
        ledger=ledger,
        provider=provider,
        instrument=INSTRUMENT,
        side="BUY",
        quantity=100,
        observation_time=1787000000000000000,
        client_order_id="cli-broker-market-1",
        idempotency_key="key-broker-market-1",
    )
    if result["broker_order_id"] != "TR-FILL-0001":
        raise RuntimeError("fixture mismatch: expected TR-FILL-0001 fill")
    return ledger


def _polled_order_snapshot(provider: object) -> BrokerOrderSnapshot:
    """Poll the fixture provider for the broker order status (no network)."""
    result = provider.fetch_order("TR-FILL-0001")
    if result.status != "ok" or not result.events:
        raise RuntimeError(f"fixture fetch_order failed: {result.status}")
    envelope = result.events[0]
    status_event = BrokerOrderStatusEvent.from_record(envelope["payload"])
    return BrokerOrderSnapshot.from_status_event(
        status_event,
        raw_source_reference=str(envelope.get("raw_reference", "tradier:fetch_order:TR-FILL-0001")),
    )


def _consistent_snapshots(ledger: PaperExecutionLedger, order_snapshot: BrokerOrderSnapshot) -> dict[str, object]:
    account = ledger.project_account()
    return {
        "orders": [order_snapshot],
        "positions": [
            BrokerPositionSnapshot(
                instrument_id="BIYA",
                quantity=100,
                avg_price_minor=11620,
                as_of_ns=AS_OF_NS,
            )
        ],
        "account": BrokerAccountSnapshot(
            cash_minor=int(account["cash_minor"]),
            buying_power_minor=int(account["cash_minor"]),
            as_of_ns=AS_OF_NS,
        ),
    }


def _drifted_snapshots(snapshots: dict[str, object]) -> dict[str, object]:
    drifted = dict(snapshots)
    order = drifted["orders"][0]
    drifted["orders"] = [
        BrokerOrderSnapshot(
            broker_order_id=order.broker_order_id,
            status=order.status,
            filled_quantity=90,
            avg_fill_price_minor=order.avg_fill_price_minor,
            fills=order.fills,
            event_time_ns=order.event_time_ns,
            receive_time_ns=order.receive_time_ns,
            raw_source_reference=order.raw_source_reference,
        )
    ]
    return drifted


def _report(ledger: PaperExecutionLedger, snapshots: dict[str, object]) -> dict:
    return build_reconciliation_report(
        ledger,
        order_snapshots=snapshots["orders"],  # type: ignore[arg-type]
        position_snapshots=snapshots["positions"],  # type: ignore[arg-type]
        account_snapshot=snapshots["account"],  # type: ignore[arg-type]
        as_of_ns=AS_OF_NS,
    )


def main() -> int:
    install_guard([])
    checks: dict[str, object] = {}
    failures: list[str] = []

    store = TradierReplayStore.load()
    provider = make_tradier_paper_provider(
        env=dict(GATED_ENV), symbol_map=dict(SYMBOL_MAP), replay_store=store
    )
    ledger = _filled_ledger(provider)
    order_snapshot = _polled_order_snapshot(provider)
    snapshots = _consistent_snapshots(ledger, order_snapshot)

    # P4-REC-001: deterministic report under identical snapshots; append-only recording.
    first = _report(ledger, snapshots)
    second = _report(ledger, snapshots)
    checks["P4-REC-001"] = first == second and first["report_id"] == second["report_id"] and first["overall_status"] == MATCHED
    if not checks["P4-REC-001"]:
        failures.append("P4-REC-001")

    record_reconciliation(ledger, first)
    record_reconciliation(ledger, first)
    recorded = [e for e in ledger.events if e["event_type"] == "ReconciliationRecorded"]
    checks["P4-REC-001.append_only"] = len(recorded) == 2 and len(ledger.project_fills()) == 1
    if not checks["P4-REC-001.append_only"]:
        failures.append("P4-REC-001.append_only")
    checks["P4-REC-001.status"] = ledger.project_risk()["reconciliation_status"] == "BROKER_RECONCILED"
    if not checks["P4-REC-001.status"]:
        failures.append("P4-REC-001.status")

    # P4-REC-002: quantity drift surfaces as MISMATCH, is never silently absorbed,
    # and resolves only via a root-cause correction or an explicit hold.
    drift_ledger = _filled_ledger(provider)
    drifted = _report(drift_ledger, _drifted_snapshots(snapshots))
    checks["P4-REC-002.drift_detected"] = drifted["overall_status"] == MISMATCH and "orders.TR-FILL-0001.filled_quantity" in drifted["mismatch_fields"]
    if not checks["P4-REC-002.drift_detected"]:
        failures.append("P4-REC-002.drift_detected")

    record_reconciliation(drift_ledger, drifted)
    checks["P4-REC-002.unresolved"] = drift_ledger.project_risk()["reconciliation_status"] == MISMATCH
    if not checks["P4-REC-002.unresolved"]:
        failures.append("P4-REC-002.unresolved")
    try:
        assert_no_unexplained_mismatch(drift_ledger, drifted)
        checks["P4-REC-002.fail_closed"] = False
        failures.append("P4-REC-002.fail_closed")
    except ReconciliationViolation:
        checks["P4-REC-002.fail_closed"] = True

    hold_reconciliation(
        drift_ledger,
        report_id=drifted["report_id"],
        reason_codes=["OPERATOR_INVESTIGATING"],
        operator_id="PRINCIPAL-001",
    )
    checks["P4-REC-002.hold"] = drift_ledger.project_risk()["reconciliation_status"] == "RECONCILIATION_HOLD"
    if not checks["P4-REC-002.hold"]:
        failures.append("P4-REC-002.hold")
    assert_no_unexplained_mismatch(drift_ledger, drifted)

    resolve_ledger = _filled_ledger(provider)
    resolved_report = _report(resolve_ledger, _drifted_snapshots(snapshots))
    record_reconciliation(resolve_ledger, resolved_report)
    resolve_reconciliation_field(
        resolve_ledger,
        report_id=resolved_report["report_id"],
        field="orders.TR-FILL-0001.filled_quantity",
        observed_value=90,
        raw_source_reference="tradier:fetch_order:TR-FILL-0001",
        reason_codes=["BROKER_PARTIAL_FILL_RECORDING_DELAY"],
    )
    checks["P4-REC-002.resolved"] = resolve_ledger.project_risk()["reconciliation_status"] == "BROKER_RECONCILED"
    if not checks["P4-REC-002.resolved"]:
        failures.append("P4-REC-002.resolved")

    status = "passed" if not failures else "failed"
    report = {
        "aggregate_status": status,
        "assertions": checks,
        "failures": sorted(failures),
        "completed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f0Z"),
        "fixture_paths": ["tests/fixtures/providers/tradier_sandbox_orders.json"],
        "logical_id": "platform.reconciliation_gate_report",
        "mode": "FIXTURE_REPLAY",
        "offline": True,
        "schema_version": "1.0.0",
        "summary": f"Broker paper 4B gate: {status} with {len(failures)} failed assertion(s).",
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
