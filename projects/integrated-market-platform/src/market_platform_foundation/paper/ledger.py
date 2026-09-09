"""Append-only event-sourced paper execution ledger."""

from __future__ import annotations

import threading
import uuid
from decimal import Decimal
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator

from ..canonical import canonical_bytes, sha256_bytes
from ..portfolio.canonical import CanonicalPortfolio, CashBalance, PortfolioKey
from ..portfolio.ledger import apply_fill, build_ledger_state
from ..portfolio.paper_fill import apply_paper_fill_to_portfolio, rebuild_portfolio_from_fills
from ..risk.kill_switch import KillSwitchState
from ..risk.policy import DEFAULT_RISK_POLICY
from ..clock import monotonic_wall_ns
from .contracts import (
    build_instrument_ref,
    build_semantic_intent_digest,
    decimal_minor_to_display,
    next_event_sequence,
    validate_order_transition,
)


EVENT_TYPES: tuple[str, ...] = (
    "PaperAccountCreated",
    "PaperSessionOpened",
    "PaperSessionClosed",
    "OrderIntentCreated",
    "RiskDecisionRecorded",
    "OrderSubmitted",
    "OrderStateChanged",
    "OrderReplaced",
    "FillRecorded",
    "PositionChanged",
    "ReconciliationRecorded",
    "ReconciliationCorrectionRecorded",
)


OPEN_ORDER_STATES: frozenset[str] = frozenset(
    {"ACTIVATED", "WORKING", "PARTIALLY_FILLED", "REPLACE_PENDING", "REPLACED"}
)


def order_state_open_count_delta(prior_state: str | None, next_state: str) -> int:
    """Pure open-order-count delta for one OrderStateChanged transition.

    Mirrors the replay accounting in ``local_state/startup.py`` (+1 when the
    order enters an open state, -1 when it enters a terminal state) so a
    live-maintained counter and a replayed ledger agree. ``startup.py`` can
    adopt this helper for its replay loop in a later change; keeping it pure
    here means both call sites share one derivation with no ledger coupling.
    ``prior_state=None`` models an order's first observed transition (the
    implicit OrderStateChanged appended by ``append_order``).
    """
    before = 1 if prior_state in OPEN_ORDER_STATES else 0
    after = 1 if next_state in OPEN_ORDER_STATES else 0
    return after - before


@dataclass
class PaperExecutionLedger:
    """Immutable event log with derived portfolio projections."""

    paper_account_id: str
    session_id: str
    events: list[dict[str, Any]] = field(default_factory=list)
    idempotency_index: dict[str, str] = field(default_factory=dict)
    kill_switch: KillSwitchState = field(default_factory=KillSwitchState)
    policy: dict[str, Any] = field(default_factory=lambda: DEFAULT_RISK_POLICY.copy())
    data_mode: str = "FIXTURE_REPLAY"
    execution_mode: str = "NONE"
    execution_authority: str = "BLOCKED"
    data_provider: str = "INTERNAL"
    execution_provider: str = "INTERNAL"
    open_order_count: int = 0
    _submit_lock: threading.RLock = field(default_factory=threading.RLock, repr=False)
    _live_mark_minor: int | None = field(default=None, repr=False)
    _live_mark_provider: str | None = field(default=None, repr=False)
    _live_mark_as_of_ns: int | None = field(default=None, repr=False)
    _live_mark_quality: str | None = field(default=None, repr=False)
    persist_sink: Callable[["PaperExecutionLedger", list[dict[str, Any]]], None] | None = field(
        default=None,
        repr=False,
    )
    _pending_persist: list[dict[str, Any]] = field(default_factory=list, repr=False)
    _batch_depth: int = field(default=0, repr=False)
    _canonical_portfolio: CanonicalPortfolio | None = field(default=None, repr=False)
    _applied_fill_ids: set[str] = field(default_factory=set, repr=False)
    _derivative_fill_ids: set[str] = field(default_factory=set, repr=False)
    _fill_intents: dict[str, dict[str, Any]] = field(default_factory=dict, repr=False)

    @classmethod
    def open_session(
        cls,
        *,
        replay_session_id: str,
        instrument_id: str,
        symbol: str,
        policy: dict[str, Any] | None = None,
        execution_mode: str = "NONE",
        execution_authority: str = "BLOCKED",
        data_mode: str = "FIXTURE_REPLAY",
        data_provider: str = "INTERNAL",
        execution_provider: str = "INTERNAL",
    ) -> PaperExecutionLedger:
        active_policy = policy or DEFAULT_RISK_POLICY
        account_body = {
            "currency": active_policy["currency"],
            "initial_cash_minor": active_policy["initial_cash_minor"],
            "instrument_id": instrument_id,
            "replay_session_id": replay_session_id,
        }
        paper_account_id = sha256_bytes(canonical_bytes(account_body))
        session_body = {
            "execution_authority": execution_authority,
            "execution_mode": execution_mode,
            "opened_at_ns": monotonic_wall_ns(),
            "paper_account_id": paper_account_id,
            "replay_session_id": replay_session_id,
            # Cross-process uniqueness nonce: opened_at_ns is strictly
            # increasing within a process (the shared clock), but two processes
            # could still open in the same wall tick, so a random nonce keeps
            # session ids globally distinct.
            "session_nonce": uuid.uuid4().hex,
        }
        session_id = sha256_bytes(canonical_bytes(session_body))
        ledger = cls(
            paper_account_id=paper_account_id,
            session_id=session_id,
            policy=active_policy,
            execution_mode=execution_mode,
            execution_authority=execution_authority,
            data_mode=data_mode,
            data_provider=data_provider,
            execution_provider=execution_provider,
        )
        ledger._append(
            "PaperAccountCreated",
            {
                "currency": active_policy["currency"],
                "initial_cash_minor": active_policy["initial_cash_minor"],
                "instrument_id": instrument_id,
                "symbol": symbol,
            },
        )
        ledger._append(
            "PaperSessionOpened",
            {
                "execution_authority": execution_authority,
                "execution_mode": execution_mode,
                "replay_session_id": replay_session_id,
            },
        )
        ledger._ensure_canonical_portfolio()
        return ledger

    def _ensure_canonical_portfolio(self) -> CanonicalPortfolio:
        if self._canonical_portfolio is None:
            key = PortfolioKey(
                account_id=self.paper_account_id,
                mode="PAPER",
                broker="internal.simulation",
                portfolio_id=self.paper_account_id,
            )
            portfolio = CanonicalPortfolio(key)
            scale = int(self.policy.get("price_scale", 100))
            currency = str(self.policy.get("currency", "USD")).upper()
            portfolio.set_cash(
                CashBalance(
                    currency=currency,
                    settled=Decimal(int(self.policy["initial_cash_minor"])) / Decimal(scale),
                )
            )
            self._canonical_portfolio = portfolio
        return self._canonical_portfolio

    @property
    def canonical_portfolio(self) -> CanonicalPortfolio:
        return self._ensure_canonical_portfolio()

    def _lookup_intent_for_fill(self, fill: dict[str, Any], order: dict[str, Any]) -> dict[str, Any] | None:
        order_id = str(order.get("order_id", ""))
        if order_id and order_id in self._fill_intents:
            return self._fill_intents[order_id]
        for event in reversed(self.events):
            if event["event_type"] != "OrderIntentCreated":
                continue
            payload = event.get("payload")
            if not isinstance(payload, dict):
                continue
            intent = payload.get("intent")
            if not isinstance(intent, dict):
                continue
            if str(intent.get("instrument_id", "")) == str(fill.get("instrument_id", "")):
                return intent
        return None

    def _is_derivative_fill(self, fill: dict[str, Any], intent: dict[str, Any] | None) -> bool:
        instrument = fill.get("instrument")
        if isinstance(instrument, dict):
            kind = str(instrument.get("instrument_kind", "")).upper()
            if kind in {"OPTION_CONTRACT", "FUTURE_CONTRACT"}:
                return True
        if intent is not None:
            candidate = intent.get("instrument")
            if isinstance(candidate, dict):
                kind = str(candidate.get("instrument_kind", "")).upper()
                if kind in {"OPTION_CONTRACT", "FUTURE_CONTRACT"}:
                    return True
        return False

    def _uses_canonical_authority(self) -> bool:
        return bool(self._derivative_fill_ids)

    def _append(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        if event_type not in EVENT_TYPES:
            raise ValueError("PAPER_EVENT_TYPE_INVALID")
        now_ns = monotonic_wall_ns()
        correlation_id = _correlation_id_from_payload(payload)
        body = {
            "available_time": now_ns,
            "data_mode": self.data_mode,
            "data_provider": self.data_provider,
            "event_time": now_ns,
            "event_type": event_type,
            "execution_authority": self.execution_authority,
            "execution_mode": self.execution_mode,
            "execution_provider": self.execution_provider,
            "paper_account_id": self.paper_account_id,
            "payload": payload,
            "schema_version": 1,
            "sequence": next_event_sequence(self.events),
            "session_id": self.session_id,
        }
        if correlation_id:
            body["correlation_id"] = correlation_id
        event = {
            **body,
            "event_id": sha256_bytes(canonical_bytes(body)),
        }
        self.events.append(event)
        self._pending_persist.append(event)
        if self._batch_depth == 0:
            self._flush_persist()
        return event

    @contextmanager
    def submit_critical_section(self) -> Iterator[None]:
        """Account-scoped lock guarding idempotency-check + order creation.

        G3 §21/§52/§53: the lookup of an existing idempotent order, the
        conflict check, the reservation check, and the append sequence must be
        atomic with respect to competing orders for the SAME operational
        account. The lock is per-ledger (per account+mode), so unrelated
        accounts are never serialized against each other, and internal
        callers (strategy engine, direct entrypoints) get the same protection
        as the UI route path.
        """
        with self._submit_lock:
            yield

    @contextmanager
    def atomic_append(self) -> Iterator[None]:
        """One SQLite transaction for a logical multi-event operation (FillRecorded + PositionChanged)."""

        self._batch_depth += 1
        try:
            yield
            if self._batch_depth == 1:
                self._flush_persist()
        finally:
            self._batch_depth = max(0, self._batch_depth - 1)

    def _flush_persist(self) -> None:
        if self.persist_sink is None or not self._pending_persist:
            self._pending_persist.clear()
            return
        pending = list(self._pending_persist)
        self._pending_persist.clear()
        self.persist_sink(self, pending)

    def record_idempotent_order(self, *, idempotency_key: str, order_id: str) -> None:
        self.idempotency_index[idempotency_key] = order_id
        if self.persist_sink is not None:
            self.persist_sink(self, [])

    def lookup_idempotent_order(self, idempotency_key: str) -> str | None:
        return self.idempotency_index.get(idempotency_key)

    def project_account(self) -> dict[str, Any]:
        projection = self._project_ledger()
        cash_minor = int(projection["cash_minor"])
        scale = int(self.policy["price_scale"])
        return {
            "authority_boundary": "PAPER_EXECUTION_OBSERVABILITY",
            "buying_power_minor": cash_minor,
            "cash_minor": cash_minor,
            "cash_display": decimal_minor_to_display(cash_minor, scale=scale),
            "currency": self.policy["currency"],
            "data_mode": self.data_mode,
            "data_provider": self.data_provider,
            "execution_authority": self.execution_authority,
            "execution_mode": self.execution_mode,
            "execution_provider": self.execution_provider,
            "initial_cash_minor": int(self.policy["initial_cash_minor"]),
            "paper_account_id": self.paper_account_id,
            "realized_pnl_minor": int(projection["realized_pnl_minor"]),
            "realized_pnl_display": decimal_minor_to_display(
                int(projection["realized_pnl_minor"]),
                scale=scale,
            ),
            "session_id": self.session_id,
            "total_commission_minor": int(projection["total_commission_minor"]),
            "total_fees_minor": int(projection["total_fees_minor"]),
        }

    def apply_live_mark(
        self,
        *,
        mark_minor: int,
        mark_provider: str,
        mark_as_of_ns: int,
        mark_quality: str,
    ) -> None:
        self._live_mark_minor = mark_minor
        self._live_mark_provider = mark_provider
        self._live_mark_as_of_ns = mark_as_of_ns
        self._live_mark_quality = mark_quality

    def project_positions(self) -> list[dict[str, Any]]:
        positions: list[dict[str, Any]] = []
        if self._uses_canonical_authority():
            positions.extend(self._project_canonical_positions())
        projection = self._project_ledger()
        position_shares = int(projection["position_shares"])
        if position_shares == 0:
            return positions
        instrument_id = self._primary_instrument_id()
        symbol = self._primary_symbol()
        scale = int(self.policy["price_scale"])
        mark = self._latest_mark_minor()
        avg_fill = abs(int(projection["position_cost_basis_minor"])) // abs(position_shares)
        notional_minor = abs(position_shares) * mark if mark is not None else 0
        unrealized_minor = 0
        if mark is not None and avg_fill is not None and position_shares != 0:
            unrealized_minor = (mark - avg_fill) * position_shares
        if self.data_mode == "LIVE_OBSERVATIONAL":
            mark_source = self._live_mark_provider or "LIVE_MARK_UNAVAILABLE"
            mark_quality = self._live_mark_quality or "UNAVAILABLE"
        else:
            mark_source = self._live_mark_provider or ("INTERNAL_FIXTURE" if mark is not None else None)
            mark_quality = self._live_mark_quality or ("PASS" if mark is not None else None)
        positions.append(
            {
                "average_fill_display": decimal_minor_to_display(avg_fill, scale=scale) if avg_fill is not None else None,
                "average_fill_minor": avg_fill,
                "instrument": build_instrument_ref(
                    instrument_id=instrument_id,
                    symbol=symbol,
                ),
                "instrument_id": instrument_id,
                "mark_as_of_ns": self._live_mark_as_of_ns,
                "mark_minor": mark,
                "mark_display": decimal_minor_to_display(mark, scale=scale) if mark is not None else None,
                "mark_provider": mark_source,
                "mark_quality": mark_quality,
                "mark_source": mark_source,
                "notional_minor": notional_minor,
                "quantity": position_shares,
                "side": "LONG" if position_shares > 0 else "SHORT",
                "symbol": symbol,
                "unrealized_pnl_minor": unrealized_minor,
                "unrealized_pnl_display": decimal_minor_to_display(unrealized_minor, scale=scale),
            }
        )
        return positions

    def _project_canonical_positions(self) -> list[dict[str, Any]]:
        portfolio = self._ensure_canonical_portfolio()
        scale = int(self.policy.get("price_scale", 100))
        rows: list[dict[str, Any]] = []
        for instrument_id in sorted(portfolio.positions):
            position = portfolio.positions[instrument_id]
            if position.instrument_kind not in {"OPTION_CONTRACT", "FUTURE_CONTRACT"}:
                continue
            if position.quantity == 0:
                continue
            avg_minor = (
                int((position.average_cost or Decimal("0")) * Decimal(scale))
                if position.average_cost is not None
                else None
            )
            mark = self._latest_mark_minor()
            unrealized_minor = 0
            if mark is not None and avg_minor is not None:
                signed_qty = int(position.quantity)
                unrealized_minor = (mark - avg_minor) * signed_qty
            rows.append(
                {
                    "asset_class": position.asset_class,
                    "average_fill_minor": avg_minor,
                    "contract_multiplier": str(position.multiplier),
                    "instrument_id": position.instrument_id,
                    "instrument_kind": position.instrument_kind,
                    "mark_minor": mark,
                    "quantity": int(position.quantity),
                    "quantity_unit": position.quantity_unit.value,
                    "realized_pnl_minor": int(position.realized_pnl_native * Decimal(scale)),
                    "side": "LONG" if position.quantity > 0 else "SHORT",
                    "symbol": instrument_id,
                    "unrealized_pnl_minor": unrealized_minor,
                }
            )
        return rows

    def project_orders(self) -> list[dict[str, Any]]:
        orders_by_id: dict[str, dict[str, Any]] = {}
        intent_meta: dict[str, dict[str, Any]] = {}
        for event in self.events:
            if event["event_type"] == "OrderSubmitted":
                payload = event["payload"]
                if not isinstance(payload, dict):
                    continue
                order = payload.get("order")
                if not isinstance(order, dict):
                    continue
                order_id = str(order.get("order_id", ""))
                enriched = dict(order)
                enriched["client_order_id"] = payload.get("client_order_id")
                enriched["idempotency_key"] = payload.get("idempotency_key")
                enriched["intent_id"] = payload.get("intent_id")
                enriched["execution_source"] = self.execution_provider
                enriched["submitted_sequence"] = event.get("sequence")
                orders_by_id[order_id] = enriched
            elif event["event_type"] == "OrderStateChanged":
                payload = event["payload"]
                if not isinstance(payload, dict):
                    continue
                order_id = str(payload.get("order_id", ""))
                if order_id in orders_by_id:
                    orders_by_id[order_id]["state"] = payload.get("state")
                    if payload.get("reason_codes"):
                        orders_by_id[order_id]["reason_codes"] = payload.get("reason_codes")
                    if payload.get("broker_order_id"):
                        orders_by_id[order_id]["broker_order_id"] = payload["broker_order_id"]
            elif event["event_type"] == "OrderReplaced":
                payload = event["payload"]
                if not isinstance(payload, dict):
                    continue
                order_id = str(payload.get("order_id", ""))
                if order_id not in orders_by_id:
                    continue
                replaced_quantity = int(payload.get("replaced_quantity", 0))
                orders_by_id[order_id]["state"] = "REPLACED"
                orders_by_id[order_id]["replaced_quantity"] = replaced_quantity
                orders_by_id[order_id]["authorized_quantity"] = replaced_quantity
                orders_by_id[order_id]["replace_count"] = int(payload.get("replace_count", 1))
                orders_by_id[order_id]["replace_revision"] = payload.get("replace_revision")
                if payload.get("order_type"):
                    orders_by_id[order_id]["order_type"] = payload["order_type"]
                if payload.get("limit_price_minor") is not None:
                    orders_by_id[order_id]["limit_price_minor"] = payload["limit_price_minor"]
            elif event["event_type"] == "OrderIntentCreated":
                payload = event["payload"]
                if isinstance(payload, dict) and isinstance(payload.get("intent"), dict):
                    intent = payload["intent"]
                    intent_id = str(intent.get("intent_id", ""))
                    intent_meta[intent_id] = intent
        for order in orders_by_id.values():
            intent_id = str(order.get("intent_id", ""))
            if intent_id in intent_meta:
                intent = intent_meta[intent_id]
                order["side"] = intent.get("side")
                order["order_type"] = intent.get("order_type", "MARKET")
                if intent.get("correlation_id"):
                    order["correlation_id"] = intent.get("correlation_id")
                if isinstance(intent.get("decision_source_snapshot"), dict):
                    order["decision_source_snapshot"] = intent.get("decision_source_snapshot")
                if intent.get("created_time") is not None:
                    order["created_time"] = intent.get("created_time")
                if intent.get("desired_quantity") is not None:
                    order["desired_quantity"] = intent.get("desired_quantity")
                if intent.get("lineage_refs"):
                    order["lineage_refs"] = intent.get("lineage_refs")
                if intent.get("quantity_facts"):
                    order["quantity_facts"] = intent.get("quantity_facts")
                if intent.get("risk_decision_id"):
                    order["risk_decision_id"] = intent.get("risk_decision_id")
                for key in (
                    "allocation_desired_quantity",
                    "allocation_desired_notional_minor",
                    "proposal_requested_quantity",
                    "proposal_requested_notional_minor",
                    "risk_approved_quantity",
                    "risk_approved_notional_minor",
                    "submitted_quantity",
                    "requested_quantity",
                    "approved_quantity",
                ):
                    if intent.get(key) is not None:
                        order[key] = intent.get(key)
                instrument = intent.get("instrument")
                if isinstance(instrument, dict):
                    if instrument.get("symbol"):
                        order["symbol"] = instrument.get("symbol")
                    if instrument.get("instrument_id"):
                        order["instrument_id"] = instrument.get("instrument_id")
                    # G4: order economics are projected from the canonical
                    # instrument ref so financial gates never re-derive them
                    # from symbol text or silent defaults.
                    if instrument.get("instrument_kind"):
                        order["instrument_kind"] = instrument.get("instrument_kind")
                    if instrument.get("contract_multiplier"):
                        order["contract_multiplier"] = instrument.get("contract_multiplier")
                    if instrument.get("currency"):
                        order["currency"] = instrument.get("currency")
                order["intent_digest"] = build_semantic_intent_digest(intent)
        fills_by_order = self._fills_by_order()
        for order in orders_by_id.values():
            order_id = str(order.get("order_id", ""))
            totals = fills_by_order.get(order_id)
            filled = int((totals or {}).get("filled_quantity", 0))
            base = int(
                order.get("authorized_quantity")
                or order.get("submitted_quantity")
                or order.get("approved_quantity")
                or order.get("requested_quantity")
                or order.get("desired_quantity")
                or 0
            )
            order["cumulative_filled_quantity"] = filled
            order["working_remaining"] = max(0, base - filled)
            order["fill_count"] = int((totals or {}).get("fill_count", 0))
            if totals and totals.get("average_fill_minor") is not None:
                order["average_fill_minor"] = totals["average_fill_minor"]
        return list(orders_by_id.values())

    def append_order_state(
        self,
        *,
        order_id: str,
        state: str,
        prior_state: str,
        reason_codes: list[str] | None = None,
        broker_order_id: str | None = None,
    ) -> dict[str, Any]:
        """Append a validated OrderStateChanged transition (broker paper path).

        Maintains ``open_order_count`` from the prior_state→state pair so the
        max_open_orders risk gate observes BROKER_PAPER lifecycle progress
        (SUBMITTED → WORKING/ACTIVATED → terminal) and not just the internal
        simulator's synchronous append. The derivation lives in the pure
        module-level helper so startup replay can share it.
        Optional ``broker_order_id`` (known only after broker submission) is
        attached to the governing state event so projections and the execution
        trace can resolve it.
        """
        validate_order_transition(prior_state=prior_state, next_state=state)
        payload: dict[str, Any] = {
            "order_id": order_id,
            "prior_state": prior_state,
            "reason_codes": list(reason_codes or []),
            "state": state,
        }
        if broker_order_id:
            payload["broker_order_id"] = broker_order_id
        self.open_order_count = max(0, self.open_order_count + order_state_open_count_delta(prior_state, state))
        return self._append("OrderStateChanged", payload)

    def project_fills(self) -> list[dict[str, Any]]:
        fills: list[dict[str, Any]] = []
        for event in self.events:
            if event["event_type"] != "FillRecorded":
                continue
            payload = event["payload"]
            if isinstance(payload, dict) and isinstance(payload.get("fill"), dict):
                fills.append(dict(payload["fill"]))
        return fills

    def _fills_by_order(self) -> dict[str, dict[str, Any]]:
        """Aggregate cumulative fill totals per order (G3 §36–38).

        Cumulative filled quantity, fill count, and notional-weighted average
        fill price derived from immutable FillRecorded events — never from a
        mutable counter, so replay/restart reproduces identical totals.
        """
        totals: dict[str, dict[str, Any]] = {}
        for event in self.events:
            if event["event_type"] != "FillRecorded":
                continue
            payload = event.get("payload")
            if not isinstance(payload, dict):
                continue
            order_id = str(payload.get("order_id", ""))
            fill = payload.get("fill")
            if not isinstance(fill, dict) or not order_id:
                continue
            quantity = int(fill.get("fill_quantity") or 0)
            price = int(fill.get("fill_price_minor") or 0)
            bucket = totals.setdefault(
                order_id,
                {"average_notional_minor": 0, "fill_count": 0, "filled_quantity": 0},
            )
            bucket["filled_quantity"] += quantity
            bucket["average_notional_minor"] += quantity * price
            bucket["fill_count"] += 1
        result: dict[str, dict[str, Any]] = {}
        for order_id, bucket in totals.items():
            filled = bucket["filled_quantity"]
            average_fill_minor = bucket["average_notional_minor"] // filled if filled else None
            result[order_id] = {
                "average_fill_minor": average_fill_minor,
                "fill_count": bucket["fill_count"],
                "filled_quantity": filled,
            }
        return result

    def lookup_intent_for_order(self, order_id: str) -> dict[str, Any] | None:
        """Resolve the canonical intent bound to a submitted order (BL-0207)."""
        for event in self.events:
            if event["event_type"] != "OrderSubmitted":
                continue
            payload = event.get("payload")
            if not isinstance(payload, dict):
                continue
            order = payload.get("order")
            if not (isinstance(order, dict) and str(order.get("order_id")) == order_id):
                continue
            intent_id = payload.get("intent_id")
            for candidate in self.events:
                if candidate["event_type"] != "OrderIntentCreated":
                    continue
                intent_payload = candidate.get("payload")
                intent = intent_payload.get("intent") if isinstance(intent_payload, dict) else None
                if isinstance(intent, dict) and str(intent.get("intent_id")) == intent_id:
                    return intent
        return None

    def append_late_fill_reconciliation(
        self,
        *,
        order_id: str,
        fill_ids: list[str],
    ) -> dict[str, Any]:
        """Record fills that arrived after a terminal order state (BL-0206).

        Provider-valid fill evidence is financially authoritative and is never
        silently dropped just because local lifecycle state says CANCELLED/
        terminal. The fills themselves are appended exactly once (deduped by
        stable broker fill identity upstream); this event marks the anomaly
        with provenance so reconciliation surfaces it instead of hiding it.
        """
        body = {
            "correlation_id": fill_ids[0] if fill_ids else order_id,
            "fills": list(fill_ids),
            "mismatch_fields": ["late_fill_after_terminal"],
            "order_id": order_id,
            "overall_status": "MISMATCH",
            "report_id": sha256_bytes(
                canonical_bytes({"fills": sorted(fill_ids), "order_id": order_id})
            ),
        }
        return self._append("ReconciliationRecorded", body)

    def project_risk(self) -> dict[str, Any]:
        decisions = [
            event["payload"]
            for event in self.events
            if event["event_type"] == "RiskDecisionRecorded" and isinstance(event.get("payload"), dict)
        ]
        last = decisions[-1] if decisions else None
        reconciliation_status, last_reconciliation = self._reconciliation_state()
        return {
            "authority_boundary": "PAPER_RISK_OBSERVABILITY",
            "execution_authority": self.execution_authority,
            "execution_mode": self.execution_mode,
            "kill_switch_active": self.kill_switch.active,
            "last_decision": last,
            "last_reconciliation": last_reconciliation,
            "limits": {
                "max_open_orders": int(self.policy["max_open_orders"]),
                "max_order_shares": int(self.policy["max_order_shares"]),
                "max_position_shares": int(self.policy["max_position_shares"]),
            },
            "open_order_count": self.open_order_count,
            "policy_version": self.policy["policy_version"],
            "reconciliation_status": reconciliation_status,
        }

    def _reconciliation_state(self) -> tuple[str, dict[str, Any] | None]:
        """Derive (reconciliation_status, last_report_payload) from ledger events.

        P4 audit F7: in ``BROKER_PAPER`` mode the broker is authoritative, so the
        status reflects the latest recorded reconciliation report and any
        operator corrections against it. In every other mode the internal
        simulator remains authoritative (``INTERNAL_AUTHORITATIVE``).

        Status mapping:
        - no report yet / report unavailable -> ``RECONCILIATION_PENDING``;
        - last report overall MATCHED -> ``BROKER_RECONCILED``;
        - last report MISMATCH with any HELD correction -> ``RECONCILIATION_HOLD``;
        - last report MISMATCH fully covered by RESOLVED corrections
          (every mismatch field has a root-cause event) -> ``BROKER_RECONCILED``;
        - otherwise -> ``MISMATCH`` (never silently absorbed, P4-REC-002).
        """
        if self.execution_mode != "BROKER_PAPER":
            return "INTERNAL_AUTHORITATIVE", None
        reports = [
            event["payload"]
            for event in self.events
            if event["event_type"] == "ReconciliationRecorded" and isinstance(event.get("payload"), dict)
        ]
        if not reports:
            return "RECONCILIATION_PENDING", None
        last = reports[-1]
        overall = str(last.get("overall_status", "UNAVAILABLE"))
        if overall == "MATCHED":
            return "BROKER_RECONCILED", last
        if overall == "UNAVAILABLE":
            return "RECONCILIATION_PENDING", last
        report_id = str(last.get("report_id", ""))
        corrections = [
            event["payload"]
            for event in self.events
            if event["event_type"] == "ReconciliationCorrectionRecorded"
            and isinstance(event.get("payload"), dict)
            and str(event["payload"].get("report_id", "")) == report_id
        ]
        if any(str(row.get("resolution")) == "HELD" for row in corrections):
            return "RECONCILIATION_HOLD", last
        mismatch_fields = {str(value) for value in last.get("mismatch_fields", [])}
        resolved_fields = {
            str(row.get("field"))
            for row in corrections
            if str(row.get("resolution")) == "RESOLVED" and row.get("field")
        }
        if mismatch_fields and mismatch_fields <= resolved_fields:
            return "BROKER_RECONCILED", last
        return "MISMATCH", last

    def append_reconciliation_report(self, report: dict[str, Any]) -> dict[str, Any]:
        """Record one reconciliation run as an immutable ledger event (P4-REC-001)."""
        report_id = str(report.get("report_id", ""))
        if not report_id:
            raise ValueError("PAPER_RECONCILIATION_REPORT_ID_REQUIRED")
        return self._append(
            "ReconciliationRecorded",
            {
                "as_of_ns": int(report.get("as_of_ns", 0)),
                "correlation_id": report_id,
                "mismatch_fields": list(report.get("mismatch_fields", [])),
                "overall_status": str(report.get("overall_status", "UNAVAILABLE")),
                "report_id": report_id,
            },
        )

    def append_reconciliation_correction(
        self,
        *,
        report_id: str,
        field: str | None,
        resolution: str,
        observed_value: Any = None,
        raw_source_reference: str = "",
        reason_codes: list[str] | None = None,
    ) -> dict[str, Any]:
        """Append an operator-initiated reconciliation correction event.

        ``resolution`` is ``RESOLVED`` (root cause identified for one field,
        carrying the observed broker value and raw-source reference) or
        ``HELD`` (report-level, held open in ``RECONCILIATION_HOLD``).
        Corrections are append-only; a ledger value is never patched.
        """
        if resolution not in {"RESOLVED", "HELD"}:
            raise ValueError("PAPER_RECONCILIATION_RESOLUTION_INVALID")
        if not report_id:
            raise ValueError("PAPER_RECONCILIATION_REPORT_ID_REQUIRED")
        return self._append(
            "ReconciliationCorrectionRecorded",
            {
                "correlation_id": report_id,
                "field": field,
                "observed_value": observed_value,
                "raw_source_reference": raw_source_reference,
                "reason_codes": list(reason_codes or []),
                "report_id": report_id,
                "resolution": resolution,
            },
        )

    def lookup_order(self, order_id: str) -> dict[str, Any] | None:
        for order in self.project_orders():
            if str(order.get("order_id")) == order_id:
                return order
        return None

    def cancel_order(self, *, order_id: str, prior_state: str) -> dict[str, Any]:
        # Routed through append_order_state (not raw _append) so the cancel
        # transitions adjust open_order_count like every other lifecycle move.
        self.append_order_state(
            order_id=order_id,
            state="CANCEL_PENDING",
            prior_state=prior_state,
            reason_codes=["ORDER_CANCEL_REQUESTED"],
        )
        self.append_order_state(
            order_id=order_id,
            state="CANCELLED",
            prior_state="CANCEL_PENDING",
            reason_codes=["ORDER_CANCELLED"],
        )
        order = self.lookup_order(order_id)
        if order is None:
            raise ValueError("PAPER_ORDER_NOT_FOUND")
        order = dict(order)
        order["state"] = "CANCELLED"
        return order

    def replace_order(
        self,
        *,
        order_id: str,
        prior_state: str,
        replaced_quantity: int,
        order_type: str = "MARKET",
        limit_price_minor: int | None = None,
        client_order_id: str | None = None,
    ) -> dict[str, Any]:
        """Replace the working remainder of an open order (G3 §41–43, BL-0205).

        Replacement modifies only the still-working remainder: prior fills are
        immutable ledger events and are never erased or re-summed. The new
        total quantity must not fall below the cumulative filled quantity
        (G3 §41: ``replace total < already filled`` is invalid), and the
        replacement is recorded as an explicit ``OrderReplaced`` event with
        lineage to the original order/client order id. State moves through
        ``REPLACE_PENDING -> REPLACED`` with ``prior_state`` captured for
        projection correctness. A repeat of the same replacement request is
        idempotent (same quantity/type/price digest) and returns the recorded
        replacement without appending a second event (G3 §47/§48).
        """
        replace_digest = sha256_bytes(
            canonical_bytes(
                {
                    "limit_price_minor": limit_price_minor,
                    "order_id": order_id,
                    "order_type": order_type,
                    "replaced_quantity": replaced_quantity,
                }
            )
        )
        # Idempotent replace retry: same order + same replacement claims.
        last_replace = self._last_replace_for_order(order_id)
        if last_replace is not None and last_replace.get("replace_digest") == replace_digest:
            order = self.lookup_order(order_id)
            return {
                "duplicate": True,
                "order": order,
                "order_id": order_id,
                "replace_count": int((order or {}).get("replace_count", 1)),
                "replaced_quantity": replaced_quantity,
                "state": "REPLACED",
                "working_remaining": int((order or {}).get("working_remaining", 0)),
            }

        self.append_order_state(
            order_id=order_id,
            state="REPLACE_PENDING",
            prior_state=prior_state,
            reason_codes=["ORDER_REPLACE_REQUESTED"],
        )
        self.append_order_state(
            order_id=order_id,
            state="REPLACED",
            prior_state="REPLACE_PENDING",
            reason_codes=["ORDER_REPLACED"],
        )
        order_before = self.lookup_order(order_id) or {}
        cumulative_filled = int(order_before.get("cumulative_filled_quantity", 0))
        working_remaining = max(0, replaced_quantity - cumulative_filled)
        replace_count = int((order_before.get("replace_count") or 0)) + 1
        body = {
            "client_order_id": client_order_id,
            "cumulative_filled_quantity": cumulative_filled,
            "limit_price_minor": limit_price_minor,
            "order_id": order_id,
            "order_type": order_type,
            "prior_state": prior_state,
            "replace_count": replace_count,
            "replace_digest": replace_digest,
            "replace_revision": replace_digest[:12],
            "replaced_quantity": replaced_quantity,
            "working_remaining": working_remaining,
        }
        self._append("OrderReplaced", body)
        order = self.lookup_order(order_id)
        return {
            "duplicate": False,
            "order": order,
            "order_id": order_id,
            "replace_count": replace_count,
            "replaced_quantity": replaced_quantity,
            "state": "REPLACED",
            "working_remaining": working_remaining,
        }

    def _last_replace_for_order(self, order_id: str) -> dict[str, Any] | None:
        found: dict[str, Any] | None = None
        for event in self.events:
            if event["event_type"] != "OrderReplaced":
                continue
            payload = event.get("payload")
            if not isinstance(payload, dict):
                continue
            if str(payload.get("order_id")) != order_id:
                continue
            found = payload
        return found

    def close_session(self) -> dict[str, Any]:
        return self._append(
            "PaperSessionClosed",
            {
                "execution_authority": self.execution_authority,
                "execution_mode": self.execution_mode,
                "session_id": self.session_id,
            },
        )

    def project_execution_trace(
        self,
        *,
        intent_id: str | None = None,
        order_id: str | None = None,
        fill_id: str | None = None,
    ) -> dict[str, Any]:
        if not any([intent_id, order_id, fill_id]):
            raise ValueError("PAPER_TRACE_ANCHOR_REQUIRED")

        resolved_intent_id = intent_id
        resolved_order_id = order_id
        resolved_fill_id = fill_id

        if resolved_order_id and not resolved_intent_id:
            for order in self.project_orders():
                if str(order.get("order_id")) == resolved_order_id:
                    resolved_intent_id = str(order.get("intent_id", ""))
                    break
        if resolved_fill_id and not resolved_order_id:
            for fill in self.project_fills():
                if str(fill.get("fill_id")) == resolved_fill_id:
                    resolved_order_id = str(fill.get("order_id", ""))
                    break
            if resolved_order_id and not resolved_intent_id:
                for order in self.project_orders():
                    if str(order.get("order_id")) == resolved_order_id:
                        resolved_intent_id = str(order.get("intent_id", ""))
                        break

        steps: list[dict[str, Any]] = []
        intent_event = None
        risk_event = None
        submit_event = None
        state_events: list[dict[str, Any]] = []
        fill_event = None
        position_event = None
        broker_order_id: str | None = None
        broker_cancels = 0

        for event in self.events:
            payload = event.get("payload")
            if not isinstance(payload, dict):
                continue
            et = event["event_type"]
            if et == "OrderIntentCreated":
                intent = payload.get("intent")
                if isinstance(intent, dict) and str(intent.get("intent_id")) == resolved_intent_id:
                    intent_event = event
            elif et == "RiskDecisionRecorded":
                decision = payload.get("decision")
                if isinstance(decision, dict) and str(decision.get("intent_id")) == resolved_intent_id:
                    risk_event = event
            elif et == "OrderSubmitted":
                if str(payload.get("intent_id")) == resolved_intent_id or (
                    resolved_order_id and isinstance(payload.get("order"), dict)
                    and str(payload["order"].get("order_id")) == resolved_order_id
                ):
                    submit_event = event
                    resolved_order_id = str(payload["order"]["order_id"])
                    resolved_intent_id = str(payload.get("intent_id", resolved_intent_id))
                    if isinstance(payload.get("order"), dict) and payload["order"].get("broker_order_id"):
                        broker_order_id = str(payload["order"]["broker_order_id"])
            elif et == "OrderStateChanged":
                if str(payload.get("order_id")) == resolved_order_id:
                    state_events.append(event)
                    if payload.get("broker_order_id"):
                        broker_order_id = str(payload["broker_order_id"])
                    if "ORDER_CANCELLED" in (payload.get("reason_codes") or []):
                        broker_cancels += 1
            elif et == "FillRecorded":
                if str(payload.get("order_id")) == resolved_order_id or (
                    resolved_fill_id
                    and isinstance(payload.get("fill"), dict)
                    and str(payload["fill"].get("fill_id")) == resolved_fill_id
                ):
                    fill_event = event
                    if isinstance(payload.get("fill"), dict):
                        resolved_fill_id = str(payload["fill"].get("fill_id"))
            elif et == "PositionChanged":
                if resolved_fill_id and str(payload.get("fill_id")) == resolved_fill_id:
                    position_event = event

        if intent_event:
            intent_payload = intent_event["payload"]["intent"]
            steps.append(
                {
                    "stage": "ORDER_INTENT",
                    "event_id": intent_event["event_id"],
                    "sequence": intent_event["sequence"],
                    "summary": f"{intent_payload.get('side', intent_payload.get('direction', '')).upper()} "
                    f"{intent_payload.get('desired_quantity')} "
                    f"{intent_payload.get('instrument', {}).get('symbol', intent_payload.get('instrument_id'))}",
                    "metadata": intent_payload,
                }
            )
        if risk_event:
            decision = risk_event["payload"]["decision"]
            steps.append(
                {
                    "stage": "RISK_DECISION",
                    "event_id": risk_event["event_id"],
                    "sequence": risk_event["sequence"],
                    "summary": str(decision.get("decision")),
                    "metadata": decision,
                }
            )
        if submit_event:
            order = submit_event["payload"]["order"]
            steps.append(
                {
                    "stage": "EXECUTION_AUTHORIZATION",
                    "event_id": submit_event["event_id"],
                    "sequence": submit_event["sequence"],
                    "summary": f"execution_authority={self.execution_authority}",
                    "metadata": {
                        "execution_authority": self.execution_authority,
                        "execution_mode": self.execution_mode,
                        "execution_provider": self.execution_provider,
                    },
                }
            )
            steps.append(
                {
                    "stage": "ORDER_SUBMISSION",
                    "event_id": submit_event["event_id"],
                    "sequence": submit_event["sequence"],
                    "summary": str(order.get("state")),
                    "metadata": {
                        **order,
                        "client_order_id": submit_event["payload"].get("client_order_id"),
                        "idempotency_key": submit_event["payload"].get("idempotency_key"),
                        "intent_id": submit_event["payload"].get("intent_id"),
                    },
                }
            )
        for state_event in state_events:
            payload = state_event["payload"]
            steps.append(
                {
                    "stage": "ORDER_STATE",
                    "event_id": state_event["event_id"],
                    "sequence": state_event["sequence"],
                    "summary": str(payload.get("state")),
                    "metadata": payload,
                }
            )
        if fill_event:
            fill = fill_event["payload"]["fill"]
            steps.append(
                {
                    "stage": "FILL",
                    "event_id": fill_event["event_id"],
                    "sequence": fill_event["sequence"],
                    "summary": f"{fill.get('fill_quantity')} @ {fill.get('fill_price_minor')} minor",
                    "metadata": fill,
                }
            )
        if position_event:
            steps.append(
                {
                    "stage": "PORTFOLIO_IMPACT",
                    "event_id": position_event["event_id"],
                    "sequence": position_event["sequence"],
                    "summary": f"position={position_event['payload'].get('position_shares')} "
                    f"cash={position_event['payload'].get('cash_minor')}",
                    "metadata": position_event["payload"],
                }
            )

        return {
            "correlation": {
                "fill_id": resolved_fill_id,
                "intent_id": resolved_intent_id,
                "order_id": resolved_order_id,
            },
            "data_mode": self.data_mode,
            "data_provider": self.data_provider,
            "execution_authority": self.execution_authority,
            "execution_mode": self.execution_mode,
            "execution_provider": self.execution_provider,
            "market_data_provider": self.data_provider,
            "broker_order_id": broker_order_id,
            "broker_order_submitted": broker_order_id is not None,
            "broker_modifications": 0,
            "broker_cancels": broker_cancels,
            "session_id": self.session_id,
            "steps": sorted(steps, key=lambda row: int(row["sequence"])),
        }

    def append_intent(self, intent: dict[str, Any]) -> dict[str, Any]:
        event = self._append("OrderIntentCreated", {"intent": intent})
        client_order_id = str(intent.get("client_order_id", ""))
        if client_order_id:
            self._fill_intents[client_order_id] = intent
        return event

    def append_risk_decision(self, decision: dict[str, Any]) -> dict[str, Any]:
        return self._append("RiskDecisionRecorded", {"decision": decision})

    def append_order(self, order: dict[str, Any], *, intent: dict[str, Any]) -> dict[str, Any]:
        with self.atomic_append():
            order_id = str(order.get("order_id", ""))
            if order_id:
                self._fill_intents[order_id] = intent
            self._append(
                "OrderSubmitted",
                {
                    "client_order_id": intent.get("client_order_id"),
                    "idempotency_key": intent.get("idempotency_key"),
                    "intent_id": intent.get("intent_id"),
                    "order": order,
                },
            )
            state = str(order.get("state", ""))
            # The implicit first transition of a submitted order has no prior
            # state; the shared pure helper keeps this counter consistent with
            # append_order_state and with startup replay.
            self.open_order_count = max(0, self.open_order_count + order_state_open_count_delta(None, state))
            return self._append(
                "OrderStateChanged",
                {
                    "order_id": order.get("order_id"),
                    "reason_codes": order.get("reason_codes", []),
                    "state": state,
                },
            )
    def append_fill(self, fill: dict[str, Any], *, order: dict[str, Any]) -> dict[str, Any]:
        with self.atomic_append():
            intent = self._lookup_intent_for_fill(fill, order)
            fill_id = str(fill.get("fill_id", ""))
            is_derivative = self._is_derivative_fill(fill, intent)
            if fill_id and fill_id not in self._applied_fill_ids and is_derivative:
                portfolio = self._ensure_canonical_portfolio()
                enriched = dict(fill)
                if intent is not None and "instrument" not in enriched:
                    instrument = intent.get("instrument")
                    if isinstance(instrument, dict):
                        enriched["instrument"] = instrument
                if intent is not None and intent.get("margin_facts") is not None:
                    enriched["margin_facts"] = intent.get("margin_facts")
                apply_paper_fill_to_portfolio(
                    portfolio,
                    fill=enriched,
                    intent=intent,
                    policy=self.policy,
                    applied_fill_ids=self._applied_fill_ids,
                )
                self._derivative_fill_ids.add(fill_id)
            self._append(
                "FillRecorded",
                {
                    "fill": fill,
                    "order_id": order.get("order_id"),
                },
            )
            projection = self._project_ledger()
            return self._append(
                "PositionChanged",
                {
                    "cash_minor": int(projection["cash_minor"]),
                    "fill_id": fill.get("fill_id"),
                    "position_cost_basis_minor": int(projection["position_cost_basis_minor"]),
                    "position_shares": int(projection["position_shares"]),
                    "realized_pnl_minor": int(projection["realized_pnl_minor"]),
                },
            )

    def _project_ledger(self) -> dict[str, Any]:
        state = build_ledger_state(initial_cash_minor=int(self.policy["initial_cash_minor"]))
        for event in self.events:
            if event["event_type"] != "FillRecorded":
                continue
            payload = event.get("payload")
            if not isinstance(payload, dict):
                continue
            fill = payload.get("fill")
            if not isinstance(fill, dict):
                continue
            intent = self._lookup_intent_for_fill(fill, {"order_id": payload.get("order_id")})
            if self._is_derivative_fill(fill, intent):
                continue
            state = apply_fill(state, fill=fill, policy=self.policy)
        if self._uses_canonical_authority():
            state = self._merge_derivative_cash_into_ledger(state)
        return state

    def _merge_derivative_cash_into_ledger(self, state: dict[str, Any]) -> dict[str, Any]:
        """Subtract derivative premium/margin cash from legacy equity cash projection."""
        portfolio = self._ensure_canonical_portfolio()
        scale = int(self.policy.get("price_scale", 100))
        currency = str(self.policy.get("currency", "USD")).upper()
        initial = Decimal(int(self.policy["initial_cash_minor"])) / Decimal(scale)
        derivative_cash = portfolio.cash_balances[0].settled if portfolio.cash_balances else initial
        equity_cash = Decimal(int(state["cash_minor"])) / Decimal(scale)
        # Legacy equity replay cash minus the derivative layer's net cash impact.
        legacy_equity_only = initial + (equity_cash - initial)
        merged_cash = legacy_equity_only + (derivative_cash - initial)
        state = dict(state)
        state["cash_minor"] = int(merged_cash * Decimal(scale))
        return state

    def _primary_instrument_id(self) -> str:
        for event in self.events:
            if event["event_type"] != "PaperAccountCreated":
                continue
            payload = event.get("payload")
            if isinstance(payload, dict) and payload.get("instrument_id"):
                return str(payload["instrument_id"])
        return "UNKNOWN"

    def _primary_symbol(self) -> str:
        for event in self.events:
            if event["event_type"] != "PaperAccountCreated":
                continue
            payload = event.get("payload")
            if isinstance(payload, dict) and payload.get("symbol"):
                return str(payload["symbol"])
        return "UNKNOWN"

    def _latest_mark_minor(self) -> int | None:
        if self._live_mark_minor is not None:
            return self._live_mark_minor
        if self.data_mode == "LIVE_OBSERVATIONAL":
            return None
        fills = self.project_fills()
        if not fills:
            return None
        return int(fills[-1]["fill_price_minor"])

    def _average_fill_minor(self) -> int | None:
        projection = self._project_ledger()
        position_shares = int(projection["position_shares"])
        if position_shares != 0 and "position_cost_basis_minor" in projection:
            return abs(int(projection["position_cost_basis_minor"])) // abs(position_shares)

        fills = self.project_fills()
        if not fills:
            return None
        total_qty = 0
        total_notional = 0
        for fill in fills:
            qty = int(fill.get("fill_quantity") or 0)
            price = int(fill.get("fill_price_minor") or 0)
            if qty <= 0:
                continue
            total_qty += qty
            total_notional += qty * price
        if total_qty <= 0:
            return None
        return total_notional // total_qty


def _correlation_id_from_payload(payload: dict[str, Any]) -> str | None:
    intent = payload.get("intent")
    if isinstance(intent, dict) and intent.get("correlation_id"):
        return str(intent["correlation_id"])
    for key in ("correlation_id", "intent_id", "order_id", "fill_id"):
        if payload.get(key):
            return str(payload[key])
    fill = payload.get("fill")
    if isinstance(fill, dict) and fill.get("fill_id"):
        return str(fill["fill_id"])
    order = payload.get("order")
    if isinstance(order, dict) and order.get("order_id"):
        return str(order["order_id"])
    return None
