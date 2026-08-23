"""Platformization P4 / sub-milestone 4B — broker/ledger reconciliation engine.

Pure, replay-safe reconciliation of broker snapshots against the event-sourced
IMP paper ledger (PLATFORM-P4-001 §7). ``build_reconciliation_report`` is a
deterministic function of (ledger, snapshots, as_of_ns): identical inputs
produce an identical report (P4-REC-001). Mismatches are never patched in
place and never silently absorbed: a report is recorded as an immutable
``ReconciliationRecorded`` ledger event, and every mismatch must be either
resolved by an operator correction event carrying the observed broker value
and raw-source reference or explicitly held open in ``RECONCILIATION_HOLD``
(P4-REC-002, audit F7).

Reconciliation sources (broker order/position/account snapshots) are supplied
by a poll; the engine itself never performs network I/O and is offline-safe.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from ...canonical import canonical_bytes, sha256_bytes
from ...paper.ledger import PaperExecutionLedger
from ...providers.broker_execution import (
    BrokerAccountSnapshot,
    BrokerOrderStatusEvent,
    BrokerPositionSnapshot,
    map_broker_status,
)

RECONCILIATION_SCHEMA = "1.0.0"
RECONCILIATION_VERSION = "platform/reconciliation/1.0.0"

MATCHED = "MATCHED"
MISMATCH = "MISMATCH"
UNAVAILABLE = "UNAVAILABLE"
RECONCILIATION_STATUSES: tuple[str, ...] = (MATCHED, MISMATCH, UNAVAILABLE)


class ReconciliationViolation(ValueError):
    """Raised when a reconciliation safety invariant is violated (P4-REC-002)."""


@dataclass(frozen=True)
class BrokerOrderSnapshot:
    """Broker-side order observation for reconciliation (poll snapshot).

    ``fills`` is ``None`` when the poll did not provide executions (fill count
    then reconciles as ``UNAVAILABLE`` rather than fabricating a comparison).
    """

    broker_order_id: str
    status: str
    filled_quantity: int = 0
    avg_fill_price_minor: int | None = None
    fills: tuple[dict[str, Any], ...] | None = None
    event_time_ns: int = 0
    receive_time_ns: int = 0
    raw_source_reference: str = ""

    @classmethod
    def from_status_event(
        cls,
        event: BrokerOrderStatusEvent,
        *,
        raw_source_reference: str = "",
    ) -> BrokerOrderSnapshot:
        return cls(
            broker_order_id=event.broker_order_id,
            status=event.status,
            filled_quantity=event.filled_quantity,
            avg_fill_price_minor=event.avg_fill_price_minor,
            fills=tuple(fill.to_dict() for fill in event.fills) if event.fills else (),
            event_time_ns=event.event_time_ns,
            receive_time_ns=event.receive_time_ns,
            raw_source_reference=raw_source_reference,
        )


def _field(
    name: str,
    expected: Any,
    observed: Any,
    status: str,
    reason_codes: list[str] | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "name": name,
        "expected": expected,
        "observed": observed,
        "status": status,
    }
    if reason_codes:
        row["reason_codes"] = list(reason_codes)
    return row


def _overall(fields: Iterable[dict[str, Any]]) -> str:
    """Scope status: any MISMATCH wins, else UNAVAILABLE, else MATCHED."""
    statuses = [str(row.get("status")) for row in fields]
    if MISMATCH in statuses:
        return MISMATCH
    if UNAVAILABLE in statuses:
        return UNAVAILABLE
    return MATCHED


def _weighted_avg_minor(fills: list[dict[str, Any]]) -> int | None:
    total_quantity = sum(int(row.get("fill_quantity") or 0) for row in fills)
    if total_quantity <= 0:
        return None
    total_notional = sum(
        int(row.get("fill_quantity") or 0) * int(row.get("fill_price_minor") or 0)
        for row in fills
    )
    return total_notional // total_quantity


def _compare_order(
    order: dict[str, Any],
    snapshot: BrokerOrderSnapshot,
    fills: list[dict[str, Any]],
) -> dict[str, Any]:
    broker_id = snapshot.broker_order_id
    fields: list[dict[str, Any]] = []
    reason_codes: list[str] = []

    try:
        observed_state = map_broker_status(snapshot.status)
        state_status = MATCHED if observed_state == order.get("state") else MISMATCH
        if state_status == MISMATCH:
            reason_codes.append("ORDER_STATE_DRIFT")
        fields.append(
            _field(f"orders.{broker_id}.state", order.get("state"), observed_state, state_status)
        )
    except ValueError:
        fields.append(
            _field(
                f"orders.{broker_id}.state",
                order.get("state"),
                snapshot.status,
                UNAVAILABLE,
                ["BROKER_STATUS_UNMAPPED"],
            )
        )

    expected_quantity = sum(int(row.get("fill_quantity") or 0) for row in fills)
    quantity_status = MATCHED if expected_quantity == snapshot.filled_quantity else MISMATCH
    if quantity_status == MISMATCH:
        reason_codes.append("FILLED_QUANTITY_DRIFT")
    fields.append(
        _field(
            f"orders.{broker_id}.filled_quantity",
            expected_quantity,
            snapshot.filled_quantity,
            quantity_status,
        )
    )

    if snapshot.fills is None:
        fields.append(_field(f"orders.{broker_id}.fill_count", len(fills), None, UNAVAILABLE))
    else:
        fill_count_status = MATCHED if len(fills) == len(snapshot.fills) else MISMATCH
        if fill_count_status == MISMATCH:
            reason_codes.append("FILL_COUNT_DRIFT")
        fields.append(
            _field(
                f"orders.{broker_id}.fill_count",
                len(fills),
                len(snapshot.fills),
                fill_count_status,
            )
        )

    expected_avg = _weighted_avg_minor(fills)
    observed_avg = snapshot.avg_fill_price_minor
    if expected_avg is None and observed_avg is None:
        avg_status = MATCHED
    elif expected_avg is None and observed_avg is not None:
        avg_status = MISMATCH
        reason_codes.append("AVG_FILL_PRICE_UNEXPECTED")
    elif expected_avg is not None and observed_avg is None:
        avg_status = UNAVAILABLE
    else:
        avg_status = MATCHED if expected_avg == observed_avg else MISMATCH
        if avg_status == MISMATCH:
            reason_codes.append("AVG_FILL_PRICE_DRIFT")
    fields.append(
        _field(
            f"orders.{broker_id}.avg_fill_price_minor",
            expected_avg,
            observed_avg,
            avg_status,
        )
    )

    return {
        "broker_order_id": broker_id,
        "order_id": order.get("order_id"),
        "fields": fields,
        "overall_status": _overall(fields),
        "reason_codes": sorted(set(reason_codes)),
    }


def _unreconcilable_order(order: dict[str, Any], reason: str) -> dict[str, Any]:
    broker_id = str(order.get("broker_order_id") or order.get("order_id") or "")
    fields = [
        _field(f"orders.{broker_id}.state", order.get("state"), None, UNAVAILABLE, [reason]),
        _field(f"orders.{broker_id}.filled_quantity", None, None, UNAVAILABLE, [reason]),
    ]
    return {
        "broker_order_id": order.get("broker_order_id"),
        "order_id": order.get("order_id"),
        "fields": fields,
        "overall_status": UNAVAILABLE,
        "reason_codes": [reason],
    }


def build_reconciliation_report(
    ledger: PaperExecutionLedger,
    *,
    order_snapshots: Iterable[BrokerOrderSnapshot],
    position_snapshots: Iterable[BrokerPositionSnapshot],
    account_snapshot: BrokerAccountSnapshot | None,
    as_of_ns: int,
) -> dict[str, Any]:
    """Deterministically reconcile broker snapshots against the ledger.

    Pure function of the inputs: no wall clock, no network, and a
    content-derived ``report_id``, so identical inputs reproduce an identical
    report (P4-REC-001). A broker-side order with no ledger record is a
    mismatch, never silently dropped (P4-REC-002).
    """
    snapshots_by_id = {snapshot.broker_order_id: snapshot for snapshot in order_snapshots}
    fills_by_order: dict[str, list[dict[str, Any]]] = {}
    for fill in ledger.project_fills():
        fills_by_order.setdefault(str(fill.get("order_id")), []).append(fill)

    ledger_orders = sorted(
        ledger.project_orders(),
        key=lambda row: str(row.get("broker_order_id") or row.get("order_id") or ""),
    )
    order_rows: list[dict[str, Any]] = []
    for order in ledger_orders:
        broker_id = str(order.get("broker_order_id") or "")
        if not broker_id:
            order_rows.append(_unreconcilable_order(order, "BROKER_ORDER_ID_UNKNOWN"))
            continue
        snapshot = snapshots_by_id.get(broker_id)
        if snapshot is None:
            order_rows.append(_unreconcilable_order(order, "BROKER_ORDER_NOT_IN_SNAPSHOT"))
            continue
        order_rows.append(
            _compare_order(
                order,
                snapshot,
                fills_by_order.get(str(order.get("order_id")), []),
            )
        )

    ledger_broker_ids = {
        str(row.get("broker_order_id"))
        for row in ledger_orders
        if row.get("broker_order_id")
    }
    for snapshot in sorted(
        {s.broker_order_id: s for s in order_snapshots}.values(),
        key=lambda row: row.broker_order_id,
    ):
        if snapshot.broker_order_id in ledger_broker_ids:
            continue
        field = _field(
            f"orders.{snapshot.broker_order_id}.presence",
            "PRESENT_IN_LEDGER",
            "ABSENT_FROM_LEDGER",
            MISMATCH,
            ["BROKER_ORDER_MISSING_FROM_LEDGER"],
        )
        order_rows.append(
            {
                "broker_order_id": snapshot.broker_order_id,
                "order_id": None,
                "fields": [field],
                "overall_status": MISMATCH,
                "reason_codes": ["BROKER_ORDER_MISSING_FROM_LEDGER"],
            }
        )

    account_fields: list[dict[str, Any]] = []
    expected_cash = int(ledger.project_account()["cash_minor"])
    if account_snapshot is None:
        account_fields.append(
            _field(
                "account.cash_minor",
                expected_cash,
                None,
                UNAVAILABLE,
                ["ACCOUNT_SNAPSHOT_UNAVAILABLE"],
            )
        )
    else:
        cash_status = MATCHED if expected_cash == account_snapshot.cash_minor else MISMATCH
        if cash_status == MISMATCH:
            account_fields.append(
                _field(
                    "account.cash_minor",
                    expected_cash,
                    account_snapshot.cash_minor,
                    cash_status,
                    ["CASH_DRIFT"],
                )
            )
        else:
            account_fields.append(
                _field(
                    "account.cash_minor",
                    expected_cash,
                    account_snapshot.cash_minor,
                    cash_status,
                )
            )

    ledger_positions = {
        str(row.get("instrument_id")): row for row in ledger.project_positions()
    }
    snapshot_positions = {snapshot.instrument_id: snapshot for snapshot in position_snapshots}
    position_rows: list[dict[str, Any]] = []
    for instrument_id in sorted(set(ledger_positions) | set(snapshot_positions)):
        ledger_position = ledger_positions.get(instrument_id)
        snapshot_position = snapshot_positions.get(instrument_id)
        expected_quantity = int(ledger_position.get("quantity") or 0) if ledger_position else 0
        fields: list[dict[str, Any]] = []
        reason_codes: list[str] = []
        if snapshot_position is None:
            fields.append(
                _field(
                    f"positions.{instrument_id}.quantity",
                    expected_quantity,
                    None,
                    UNAVAILABLE,
                    ["POSITION_SNAPSHOT_UNAVAILABLE"],
                )
            )
            reason_codes.append("POSITION_SNAPSHOT_UNAVAILABLE")
        else:
            quantity_status = MATCHED if expected_quantity == snapshot_position.quantity else MISMATCH
            if quantity_status == MISMATCH:
                reason_codes.append("POSITION_QUANTITY_DRIFT")
            fields.append(
                _field(
                    f"positions.{instrument_id}.quantity",
                    expected_quantity,
                    snapshot_position.quantity,
                    quantity_status,
                )
            )
            if snapshot_position.avg_price_minor is not None:
                expected_avg = ledger_position.get("average_fill_minor") if ledger_position else None
                if expected_avg is None:
                    fields.append(
                        _field(
                            f"positions.{instrument_id}.avg_price_minor",
                            None,
                            snapshot_position.avg_price_minor,
                            UNAVAILABLE,
                        )
                    )
                else:
                    avg_status = (
                        MATCHED if expected_avg == snapshot_position.avg_price_minor else MISMATCH
                    )
                    if avg_status == MISMATCH:
                        reason_codes.append("POSITION_AVG_PRICE_DRIFT")
                    fields.append(
                        _field(
                            f"positions.{instrument_id}.avg_price_minor",
                            expected_avg,
                            snapshot_position.avg_price_minor,
                            avg_status,
                        )
                    )
        position_rows.append(
            {
                "instrument_id": instrument_id,
                "fields": fields,
                "overall_status": _overall(fields),
                "reason_codes": sorted(set(reason_codes)),
            }
        )

    all_fields = (
        account_fields
        + [field for row in order_rows for field in row["fields"]]
        + [field for row in position_rows for field in row["fields"]]
    )
    mismatch_fields = sorted(field["name"] for field in all_fields if field["status"] == MISMATCH)
    unavailable_fields = sorted(
        field["name"] for field in all_fields if field["status"] == UNAVAILABLE
    )
    if mismatch_fields:
        overall_status = MISMATCH
    elif unavailable_fields:
        overall_status = UNAVAILABLE
    else:
        overall_status = MATCHED

    body: dict[str, Any] = {
        "as_of_ns": int(as_of_ns),
        "counts": {
            "matched_orders": sum(
                1 for row in order_rows if row["overall_status"] == MATCHED
            ),
            "mismatch_orders": sum(
                1 for row in order_rows if row["overall_status"] == MISMATCH
            ),
            "orders": len(order_rows),
            "unavailable_orders": sum(
                1 for row in order_rows if row["overall_status"] == UNAVAILABLE
            ),
        },
        "mismatch_fields": mismatch_fields,
        "overall_status": overall_status,
        "scope": {
            "account": {"fields": account_fields},
            "orders": order_rows,
            "positions": position_rows,
        },
        "schema_version": RECONCILIATION_SCHEMA,
        "unavailable_fields": unavailable_fields,
        "version": RECONCILIATION_VERSION,
    }
    report = {**body, "report_id": sha256_bytes(canonical_bytes(body))}
    return report


def record_reconciliation(ledger: PaperExecutionLedger, report: dict[str, Any]) -> dict[str, Any]:
    """Append one reconciliation run as an immutable ledger event (P4-REC-001)."""
    return ledger.append_reconciliation_report(report)


def resolve_reconciliation_field(
    ledger: PaperExecutionLedger,
    *,
    report_id: str,
    field: str,
    observed_value: Any,
    raw_source_reference: str,
    reason_codes: list[str] | None = None,
) -> dict[str, Any]:
    """Operator root-cause event explaining one mismatch field (P4-REC-002)."""
    return ledger.append_reconciliation_correction(
        report_id=report_id,
        field=field,
        resolution="RESOLVED",
        observed_value=observed_value,
        raw_source_reference=raw_source_reference,
        reason_codes=reason_codes,
    )


def hold_reconciliation(
    ledger: PaperExecutionLedger,
    *,
    report_id: str,
    reason_codes: list[str] | None = None,
    operator_id: str = "OPERATOR",
) -> dict[str, Any]:
    """Explicitly hold a mismatch report open in RECONCILIATION_HOLD (P4-REC-002)."""
    return ledger.append_reconciliation_correction(
        report_id=report_id,
        field=None,
        resolution="HELD",
        raw_source_reference=f"operator:{operator_id}",
        reason_codes=reason_codes,
    )


def assert_no_unexplained_mismatch(
    ledger: PaperExecutionLedger,
    report: dict[str, Any],
) -> None:
    """Fail closed if a MISMATCH report has no root cause or hold (P4-REC-002).

    Every mismatch field must be covered by a RESOLVED correction (carrying the
    observed broker value and raw-source reference) or the report must be held.
    Silent absorption of a difference is a P4 safety violation.
    """
    if report.get("overall_status") != MISMATCH:
        return
    report_id = str(report.get("report_id") or "")
    corrections = [
        event["payload"]
        for event in ledger.events
        if event["event_type"] == "ReconciliationCorrectionRecorded"
        and isinstance(event.get("payload"), dict)
        and str(event["payload"].get("report_id", "")) == report_id
    ]
    if any(str(row.get("resolution")) == "HELD" for row in corrections):
        return
    resolved_fields = {
        str(row.get("field"))
        for row in corrections
        if str(row.get("resolution")) == "RESOLVED" and row.get("field")
    }
    mismatch_fields = {str(value) for value in report.get("mismatch_fields", [])}
    if mismatch_fields and mismatch_fields <= resolved_fields:
        return
    raise ReconciliationViolation(f"UNEXPLAINED_RECONCILIATION_MISMATCH:{report_id}")


__all__ = [
    "MATCHED",
    "MISMATCH",
    "RECONCILIATION_SCHEMA",
    "RECONCILIATION_STATUSES",
    "RECONCILIATION_VERSION",
    "UNAVAILABLE",
    "BrokerOrderSnapshot",
    "ReconciliationViolation",
    "assert_no_unexplained_mismatch",
    "build_reconciliation_report",
    "hold_reconciliation",
    "record_reconciliation",
    "resolve_reconciliation_field",
]
