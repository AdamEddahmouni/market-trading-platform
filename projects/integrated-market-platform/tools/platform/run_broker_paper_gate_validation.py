"""Platformization P4 / sub-milestone 4A gate validation (offline, fixture-first).

Loads the Tradier sandbox-contract fixtures, drives the adapter on a BROKER_PAPER
ledger, asserts the ``P4-*`` invariants, and writes
``evidence/platform/broker-paper-gate-report.json``. Strictly offline: no broker
network path is exercised (the adapter fails closed without a fixture record).
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
from market_platform_foundation.paper.broker_paper import (  # noqa: E402
    submit_broker_paper_order,
)
from market_platform_foundation.paper.ledger import PaperExecutionLedger  # noqa: E402
from market_platform_foundation.providers.adapters.tradier_paper import (  # noqa: E402
    TRADIER_SANDBOX_ENDPOINT,
    TradierReplayStore,
    make_tradier_paper_provider,
)
from market_platform_foundation.providers.broker_execution import (  # noqa: E402
    build_broker_execution_envelope,
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

REPORT_PATH = ROOT / "evidence/platform/broker-paper-gate-report.json"


def _broker_ledger() -> PaperExecutionLedger:
    return PaperExecutionLedger.open_session(
        replay_session_id="p4-4a-gate",
        instrument_id="BIYA",
        symbol="BIYA",
        execution_mode="BROKER_PAPER",
        execution_authority="PAPER_ONLY",
        data_mode="BROKER_DELAYED",
        data_provider="TRADIER",
        execution_provider="TRADIER",
    )


def main() -> int:
    install_guard([])
    checks: dict[str, object] = {}
    failures: list[str] = []

    store = TradierReplayStore.load()
    provider = make_tradier_paper_provider(env=dict(GATED_ENV), symbol_map=dict(SYMBOL_MAP), replay_store=store)

    # P4-SAFE-001: gate presence required.
    blocked = make_tradier_paper_provider(env={}, symbol_map=dict(SYMBOL_MAP), replay_store=store)
    safe_gate = blocked.place_order({"instrument_id": "BIYA", "instrument": {"symbol": "BIYA", "instrument_id": "BIYA"}})
    checks["P4-SAFE-001"] = safe_gate.status == "unavailable"
    if not checks["P4-SAFE-001"]:
        failures.append("P4-SAFE-001")

    # P4-IDEM-001: repeated idempotency key -> one broker call.
    ledger = _broker_ledger()
    one = submit_broker_paper_order(
        ledger=ledger,
        provider=provider,
        instrument=INSTRUMENT,
        side="BUY",
        quantity=100,
        observation_time=1787000000000000000,
        client_order_id="cli-broker-market-1",
        idempotency_key="key-broker-market-1",
    )
    two = submit_broker_paper_order(
        ledger=ledger,
        provider=provider,
        instrument=INSTRUMENT,
        side="BUY",
        quantity=100,
        observation_time=1787000000000000000,
        client_order_id="cli-broker-market-1",
        idempotency_key="key-broker-market-1",
    )
    checks["P4-IDEM-001"] = bool(two.get("duplicate")) and store.call_count("place_order") == 1
    if not checks["P4-IDEM-001"]:
        failures.append("P4-IDEM-001")

    # P4-FILL-001 / P4-AUDIT-001: broker fill drives the ledger; audit ids present.
    order = ledger.lookup_order(one["order_id"])
    checks["P4-FILL-001"] = order is not None and order.get("state") == "FILLED" and len(ledger.project_fills()) == 1
    checks["P4-AUDIT-001"] = bool(one.get("broker_order_id")) and bool(order and order.get("client_order_id")) and bool(order and order.get("intent_id"))
    if not checks["P4-FILL-001"]:
        failures.append("P4-FILL-001")
    if not checks["P4-AUDIT-001"]:
        failures.append("P4-AUDIT-001")

    # P4-PROV-001: the returned broker event envelope is canonical.
    mapping = provider.resolve_symbol_mapping(instrument_id="BIYA", symbol="BIYA")
    envelope = build_broker_execution_envelope(
        broker_event_type="ORDER_STATUS",
        instrument_id="BIYA",
        symbol_mapping=mapping,
        provider_id="tradier.paper",
        entitlement="TRADIER_PAPER_SANDBOX",
        event_time_ns=1,
        receive_time_ns=2,
        available_time_ns=2,
        raw_source_reference="tradier:place_order:gate",
        source_record_id="TR-GATE",
        payload={"broker_order_id": "TR-GATE", "status": "filled", "event_time_ns": 1, "receive_time_ns": 2},
        ingest_run_id="ingest-gate",
    )
    from market_platform_foundation.contracts.envelope import validate_envelope

    checks["P4-PROV-001"] = validate_envelope(
        envelope,
        timestamp_states={
            "event_time": "REQUIRED",
            "source_publish_time": "REQUIRED",
            "live_received_time": "REQUIRED",
            "historical_ingested_time": "FORBIDDEN",
            "available_time": "REQUIRED",
        },
        acquisition_mode="live",
    ) == []
    if not checks["P4-PROV-001"]:
        failures.append("P4-PROV-001")

    # P4-AMB-001: ambiguous outcome -> retry returns duplicate, no re-submit.
    amb_ledger = _broker_ledger()
    amb = submit_broker_paper_order(
        ledger=amb_ledger,
        provider=provider,
        instrument=INSTRUMENT,
        side="BUY",
        quantity=1,
        observation_time=1787000000000000000,
        client_order_id="cli-broker-ambiguous-1",
        idempotency_key="key-broker-ambiguous-1",
    )
    before = store.call_count("place_order")
    amb_retry = submit_broker_paper_order(
        ledger=amb_ledger,
        provider=provider,
        instrument=INSTRUMENT,
        side="BUY",
        quantity=1,
        observation_time=1787000000000000000,
        client_order_id="cli-broker-ambiguous-1",
        idempotency_key="key-broker-ambiguous-1",
    )
    checks["P4-AMB-001"] = bool(amb.get("ambiguous")) and bool(amb_retry.get("duplicate")) and store.call_count("place_order") == before
    if not checks["P4-AMB-001"]:
        failures.append("P4-AMB-001")

    status = "passed" if not failures else "failed"
    report = {
        "aggregate_status": status,
        "assertions": checks,
        "failures": sorted(failures),
        "completed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f0Z"),
        "fixture_paths": ["tests/fixtures/providers/tradier_sandbox_orders.json"],
        "logical_id": "platform.broker_paper_gate_report",
        "mode": "FIXTURE_REPLAY",
        "offline": True,
        "schema_version": "1.0.0",
        "summary": f"Broker paper 4A gate: {status} with {len(failures)} failed assertion(s).",
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
