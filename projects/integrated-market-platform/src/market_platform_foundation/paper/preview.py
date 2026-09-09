"""Server-side preview records (G3 / BL-0201 preview binding).

A preview is server-issued, server-verifiable state that binds the exact
order intent to the operational account, mode, instrument, portfolio state,
and risk policy that were current when the preview was created. The client
receives an opaque ``preview_id`` and cannot forge, mutate, or extend a
preview: submission must present a valid, unexpired preview whose claims
still match the current server state.

Design choice (G3 §13): **Option B — server-stored preview record.** IMP is a
single-process local tool with a server-side ``ReplayStore`` and an
event-sourced Paper ledger; a signed opaque token (Option A) would add
crypto/secret management without a distributed trust boundary, and a hybrid
(Option C) buys nothing here. The server stores the authoritative claims and
the client carries only the preview id, which keeps forgery impossible and
makes staleness server-checkable.

Isolation (G3 §91): the store is keyed by ``(account_id, mode)``; there is
no global preview singleton. ``account_id`` and ``mode`` are bound into every
record and re-verified at submit.

TTL: bounded and short (default 60s, configurable via ``preview_ttl_seconds``
on issue). A preview never reserves funds (G3 §59); abandoned previews expire
without locking account resources.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Mapping

from ..canonical import canonical_bytes, sha256_bytes

PREVIEW_TTL_SECONDS = 60
PREVIEW_SCHEMA_VERSION = 1


class PreviewErrorCode:
    PREVIEW_NOT_FOUND = "PREVIEW_NOT_FOUND"
    PREVIEW_EXPIRED = "PREVIEW_EXPIRED"
    PREVIEW_INTENT_MISMATCH = "PREVIEW_INTENT_MISMATCH"
    PREVIEW_ACCOUNT_MISMATCH = "PREVIEW_ACCOUNT_MISMATCH"
    PREVIEW_MODE_MISMATCH = "PREVIEW_MODE_MISMATCH"
    PREVIEW_PORTFOLIO_STALE = "PREVIEW_PORTFOLIO_STALE"
    PREVIEW_POLICY_STALE = "PREVIEW_POLICY_STALE"
    PREVIEW_MARGIN_STALE = "PREVIEW_MARGIN_STALE"


class PreviewError(ValueError):
    """Fail-closed preview verification error carrying a machine-readable code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


@dataclass(frozen=True, slots=True)
class PreviewRecord:
    """Authoritative server-side preview claims (G3 §14)."""

    preview_id: str
    account_id: str
    mode: str
    instrument_id: str
    intent_digest: str
    side: str
    quantity: int
    order_type: str
    risk_policy_revision: str
    portfolio_revision: str
    observation_time: int
    issued_at_ns: int
    expires_at_ns: int
    limit_price_minor: int | None = None
    margin_facts_revision: str = ""
    schema_version: int = PREVIEW_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "account_id": self.account_id,
            "expires_at_ns": self.expires_at_ns,
            "instrument_id": self.instrument_id,
            "intent_digest": self.intent_digest,
            "issued_at_ns": self.issued_at_ns,
            "mode": self.mode,
            "observation_time": self.observation_time,
            "order_type": self.order_type,
            "portfolio_revision": self.portfolio_revision,
            "preview_id": self.preview_id,
            "quantity": self.quantity,
            "risk_policy_revision": self.risk_policy_revision,
            "schema_version": self.schema_version,
            "side": self.side,
        }
        if self.limit_price_minor is not None:
            body["limit_price_minor"] = self.limit_price_minor
        if self.margin_facts_revision:
            body["margin_facts_revision"] = self.margin_facts_revision
        return body

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "PreviewRecord":
        return cls(
            preview_id=str(payload["preview_id"]),
            account_id=str(payload["account_id"]),
            mode=str(payload["mode"]),
            instrument_id=str(payload["instrument_id"]),
            intent_digest=str(payload["intent_digest"]),
            side=str(payload["side"]),
            quantity=int(payload["quantity"]),
            order_type=str(payload["order_type"]),
            risk_policy_revision=str(payload["risk_policy_revision"]),
            portfolio_revision=str(payload["portfolio_revision"]),
            observation_time=int(payload["observation_time"]),
            issued_at_ns=int(payload["issued_at_ns"]),
            expires_at_ns=int(payload["expires_at_ns"]),
            limit_price_minor=(
                int(payload["limit_price_minor"])
                if payload.get("limit_price_minor") is not None
                else None
            ),
            margin_facts_revision=str(payload.get("margin_facts_revision", "")),
            schema_version=int(payload.get("schema_version", PREVIEW_SCHEMA_VERSION)),
        )


class PreviewStore:
    """Account/mode-scoped in-memory preview registry.

    Thread-safe (one lock); previews are ephemeral server state, never
    persisted to the Paper event ledger and never reserving funds.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._records: dict[tuple[str, str, str], PreviewRecord] = {}
        self._by_id: dict[str, PreviewRecord] = {}

    def issue(
        self,
        *,
        account_id: str,
        mode: str,
        instrument_id: str,
        intent_digest: str,
        side: str,
        quantity: int,
        order_type: str,
        risk_policy_revision: str,
        portfolio_revision: str,
        observation_time: int,
        now_ns: int | None = None,
        ttl_seconds: int = PREVIEW_TTL_SECONDS,
        limit_price_minor: int | None = None,
        margin_facts_revision: str = "",
    ) -> PreviewRecord:
        """Create and store one preview record bound to the given claims."""
        now = now_ns if now_ns is not None else time.time_ns()
        if ttl_seconds <= 0:
            raise ValueError("PREVIEW_TTL_INVALID")
        body = {
            "account_id": account_id.upper(),
            "instrument_id": instrument_id.upper(),
            "intent_digest": intent_digest,
            "issued_at_ns": now,
            "mode": mode.upper(),
            "observation_time": observation_time,
            "order_type": order_type.upper(),
            "portfolio_revision": portfolio_revision,
            "quantity": int(quantity),
            "risk_policy_revision": risk_policy_revision,
            "side": side.upper(),
        }
        if limit_price_minor is not None:
            body["limit_price_minor"] = int(limit_price_minor)
        if margin_facts_revision:
            body["margin_facts_revision"] = str(margin_facts_revision)
        preview_id = sha256_bytes(canonical_bytes(body))
        record = PreviewRecord(
            preview_id=preview_id,
            account_id=account_id.upper(),
            mode=mode.upper(),
            instrument_id=instrument_id.upper(),
            intent_digest=intent_digest,
            side=side.upper(),
            quantity=int(quantity),
            order_type=order_type.upper(),
            risk_policy_revision=risk_policy_revision,
            portfolio_revision=portfolio_revision,
            observation_time=int(observation_time),
            issued_at_ns=now,
            expires_at_ns=now + int(ttl_seconds) * 1_000_000_000,
            limit_price_minor=int(limit_price_minor) if limit_price_minor is not None else None,
            margin_facts_revision=str(margin_facts_revision),
        )
        with self._lock:
            self._records[(record.account_id, record.mode, preview_id)] = record
            self._by_id[preview_id] = record
        return record

    def get(self, *, account_id: str, mode: str, preview_id: str) -> PreviewRecord | None:
        with self._lock:
            return self._records.get((account_id.upper(), mode.upper(), preview_id))

    def get_by_id(self, preview_id: str) -> PreviewRecord | None:
        """Scope-free lookup used only to distinguish mismatch codes (G3 §18)."""
        with self._lock:
            return self._by_id.get(preview_id)

    def revoke(self, *, account_id: str, mode: str, preview_id: str) -> None:
        with self._lock:
            self._records.pop((account_id.upper(), mode.upper(), preview_id), None)
            self._by_id.pop(preview_id, None)

    def purge_expired(self, *, now_ns: int | None = None) -> int:
        """Drop expired records; returns how many were removed (G3 §17)."""
        now = now_ns if now_ns is not None else time.time_ns()
        with self._lock:
            expired = [
                key
                for key, record in self._records.items()
                if record.expires_at_ns <= now
            ]
            for key in expired:
                self._records.pop(key, None)
                self._by_id.pop(key[2], None)
            return len(expired)

def portfolio_state_revision(ledger: Any) -> str:
    """Deterministic revision of the Paper ledger's financial state (G3 §15).

    Includes account, mode, cash, position, realized P&L, and working-order
    obligations (open orders by remaining quantity) so a preview binds to
    material state rather than a single scalar. Two previews issued against
    the same financial state hash identically; any cash/position/open-order
    change produces a different revision. Uses only the ledger's public
    projection surface (``project_account``, ``project_positions``,
    ``project_orders``), so it stays a pure read-side consumer.
    """
    account = ledger.project_account()
    positions = ledger.project_positions()
    working: list[tuple[str, int]] = []
    for order in ledger.project_orders():
        state = str(order.get("state", ""))
        if state in {"ACTIVATED", "WORKING", "PARTIALLY_FILLED", "REPLACE_PENDING", "REPLACED"}:
            working_remaining = order.get("working_remaining")
            if working_remaining is not None:
                remaining = int(working_remaining)
            else:
                remaining = int(order.get("remaining_quantity", order.get("desired_quantity", 0)))
            working.append((str(order.get("order_id", "")), max(0, remaining)))
    body = {
        "account_id": str(ledger.paper_account_id),
        "cash_minor": int(account.get("cash_minor", 0)),
        "event_count": len(ledger.events),
        "execution_mode": str(ledger.execution_mode),
        "position_shares": [
            (str(row.get("instrument_id", "")), int(row.get("quantity", 0)))
            for row in positions
        ],
        "working": sorted(working),
    }
    return sha256_bytes(canonical_bytes(body))


def verify_preview_submit(
    store: PreviewStore,
    *,
    preview_id: str,
    account_id: str,
    mode: str,
    intent_digest: str,
    instrument_id: str,
    side: str,
    quantity: int,
    order_type: str,
    limit_price_minor: int | None,
    portfolio_revision: str,
    risk_policy_revision: str,
    margin_facts_revision: str = "",
    now_ns: int | None = None,
) -> PreviewRecord:
    """Verify a preview can authorize an exact submission (G3 §20).

    Fail-closed: any mismatch raises ``PreviewError`` with a machine
    readable code; the preview is never treated as an authorization
    bypass and the final server risk check still runs after this.
    """
    record = store.get(account_id=account_id, mode=mode, preview_id=preview_id)
    if record is None:
        known = store.get_by_id(preview_id)
        if known is not None and str(known.account_id) != str(account_id).upper():
            raise PreviewError(PreviewErrorCode.PREVIEW_ACCOUNT_MISMATCH, "preview account mismatch")
        if known is not None and str(known.mode) != str(mode).upper():
            raise PreviewError(PreviewErrorCode.PREVIEW_MODE_MISMATCH, "preview mode mismatch")
        raise PreviewError(PreviewErrorCode.PREVIEW_NOT_FOUND, "unknown preview")
    now = now_ns if now_ns is not None else time.time_ns()
    if record.expires_at_ns <= now:
        store.revoke(account_id=account_id, mode=mode, preview_id=preview_id)
        raise PreviewError(PreviewErrorCode.PREVIEW_EXPIRED, "preview has expired")
    if str(record.account_id) != str(account_id).upper():
        raise PreviewError(PreviewErrorCode.PREVIEW_ACCOUNT_MISMATCH, "preview account mismatch")
    if str(record.mode) != str(mode).upper():
        raise PreviewError(PreviewErrorCode.PREVIEW_MODE_MISMATCH, "preview mode mismatch")
    if record.intent_digest != intent_digest:
        raise PreviewError(PreviewErrorCode.PREVIEW_INTENT_MISMATCH, "submitted intent differs from preview")
    if str(record.instrument_id) != str(instrument_id).upper():
        raise PreviewError(PreviewErrorCode.PREVIEW_INTENT_MISMATCH, "submitted instrument differs from preview")
    if record.side != str(side).upper():
        raise PreviewError(PreviewErrorCode.PREVIEW_INTENT_MISMATCH, "submitted side differs from preview")
    if int(record.quantity) != int(quantity):
        raise PreviewError(PreviewErrorCode.PREVIEW_INTENT_MISMATCH, "submitted quantity differs from preview")
    if record.order_type != str(order_type).upper():
        raise PreviewError(PreviewErrorCode.PREVIEW_INTENT_MISMATCH, "submitted order type differs from preview")
    if (record.limit_price_minor or None) != (int(limit_price_minor) if limit_price_minor is not None else None):
        raise PreviewError(PreviewErrorCode.PREVIEW_INTENT_MISMATCH, "submitted limit price differs from preview")
    if record.portfolio_revision != portfolio_revision:
        raise PreviewError(PreviewErrorCode.PREVIEW_PORTFOLIO_STALE, "portfolio state changed since preview")
    if record.risk_policy_revision != risk_policy_revision:
        raise PreviewError(PreviewErrorCode.PREVIEW_POLICY_STALE, "risk policy changed since preview")
    if record.margin_facts_revision != str(margin_facts_revision):
        raise PreviewError(PreviewErrorCode.PREVIEW_MARGIN_STALE, "margin facts changed since preview")
    return record


__all__ = [
    "PREVIEW_TTL_SECONDS",
    "PreviewError",
    "PreviewErrorCode",
    "PreviewRecord",
    "PreviewStore",
    "portfolio_state_revision",
    "verify_preview_submit",
]