"""Opportunity Engine freshness — platform decision support using G7 axes.

Pure function of explicit inputs. Deterministic tests inject ``as_of_time_ns``;
this module never reads a wall clock. Does not reopen G7 runtime wiring
(COMPLETE). Structured statuses are FRESH / STALE / UNKNOWN / NOT_APPLICABLE.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

FRESHNESS_FRESH = "FRESH"
FRESHNESS_STALE = "STALE"
FRESHNESS_UNKNOWN = "UNKNOWN"
FRESHNESS_NOT_APPLICABLE = "NOT_APPLICABLE"

HONESTY_SOURCES = frozenset({"FIXTURE", "REPLAY", "RECORDED_ARTIFACTS"})
SESSION_NON_OPEN = frozenset({"CLOSED", "OUTSIDE", "SESSION_CLOSED"})
DEFAULT_STALE_AFTER_NS = 5_000_000_000  # 5 seconds, same default as G5 book policy
CLOCK_UTC_NS = "UTC_NS"


@dataclass(frozen=True, slots=True)
class OpportunityFreshnessPolicy:
    stale_after_ns: int = DEFAULT_STALE_AFTER_NS
    name: str = "opportunity.default"
    realtime_required: bool = True

    def __post_init__(self) -> None:
        if isinstance(self.stale_after_ns, bool) or not isinstance(self.stale_after_ns, int):
            raise ValueError(f"stale_after_ns must be int ns: {self.stale_after_ns!r}")
        if self.stale_after_ns < 0:
            raise ValueError("stale_after_ns must be >= 0")


@dataclass(frozen=True, slots=True)
class OpportunityFreshnessResult:
    status: str
    policy_name: str
    reason_code: str
    source: str
    actionable: bool
    as_of_time_ns: int | None = None
    age_ns: int | None = None
    stale_after_ns: int | None = None
    clock: str = CLOCK_UTC_NS
    timeliness: str | None = None
    entitlement: str | None = None

    def to_dict(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "status": self.status,
            "policy": self.policy_name,
            "reason_code": self.reason_code,
            "source": self.source,
            "actionable": self.actionable,
            "clock": self.clock,
        }
        if self.as_of_time_ns is not None:
            body["as_of_time_ns"] = self.as_of_time_ns
        if self.age_ns is not None:
            body["age_ns"] = self.age_ns
        if self.stale_after_ns is not None:
            body["stale_after_ns"] = self.stale_after_ns
        if self.timeliness is not None:
            body["timeliness"] = self.timeliness
        if self.entitlement is not None:
            body["entitlement"] = self.entitlement
        return body


def _result(
    *,
    status: str,
    reason_code: str,
    source: str,
    policy: OpportunityFreshnessPolicy,
    as_of_time_ns: int | None = None,
    age_ns: int | None = None,
    timeliness: str | None = None,
    entitlement: str | None = None,
) -> OpportunityFreshnessResult:
    actionable = status == FRESHNESS_FRESH
    return OpportunityFreshnessResult(
        status=status,
        policy_name=policy.name,
        reason_code=reason_code,
        source=source,
        actionable=actionable,
        as_of_time_ns=as_of_time_ns,
        age_ns=age_ns,
        stale_after_ns=policy.stale_after_ns if status in {FRESHNESS_FRESH, FRESHNESS_STALE} else None,
        timeliness=timeliness,
        entitlement=entitlement,
    )


def _axis(value: Any) -> str | None:
    if value is None:
        return None
    raw = getattr(value, "value", value)
    text = str(raw).strip()
    return text or None


def evaluate_opportunity_freshness(
    *,
    source: str,
    as_of_time_ns: int | None = None,
    last_source_time_ns: int | None = None,
    policy: OpportunityFreshnessPolicy | None = None,
    runtime_capability: Mapping[str, Any] | None = None,
    session_state: str | None = None,
    book_validity: str | None = None,
) -> OpportunityFreshnessResult:
    """Evaluate freshness for Opportunity Engine ranking / operator quality.

    ``as_of_time_ns`` is injected. Honesty sources never claim FRESH. STALE and
    UNKNOWN are not actionable. Book INVALID is never FRESH.
    """

    policy = policy or OpportunityFreshnessPolicy()
    src = str(source or "UNKNOWN")
    if as_of_time_ns is not None and (
        isinstance(as_of_time_ns, bool) or not isinstance(as_of_time_ns, int)
    ):
        raise ValueError(f"as_of_time_ns must be int ns: {as_of_time_ns!r}")
    if last_source_time_ns is not None and (
        isinstance(last_source_time_ns, bool) or not isinstance(last_source_time_ns, int)
    ):
        raise ValueError(f"last_source_time_ns must be int ns: {last_source_time_ns!r}")

    if src in HONESTY_SOURCES:
        return _result(
            status=FRESHNESS_NOT_APPLICABLE,
            reason_code="HONESTY_SOURCE_NOT_LIVE_FRESHNESS",
            source=src,
            policy=policy,
            as_of_time_ns=as_of_time_ns,
        )

    if src == "LIVE_OBSERVATIONAL" and as_of_time_ns is None:
        # Missing live receive clock is not MISSING_AS_OF/UNKNOWN fail-close and
        # is never FRESH. Opportunity created_at is not a live clock.
        return _result(
            status=FRESHNESS_NOT_APPLICABLE,
            reason_code="LIVE_AS_OF_UNAVAILABLE",
            source=src,
            policy=policy,
        )

    session = str(session_state or "").upper()
    if session in SESSION_NON_OPEN:
        return _result(
            status=FRESHNESS_NOT_APPLICABLE,
            reason_code="SESSION_NOT_OPEN",
            source=src,
            policy=policy,
            as_of_time_ns=as_of_time_ns,
        )

    if str(book_validity or "").upper() == "INVALID":
        return _result(
            status=FRESHNESS_UNKNOWN,
            reason_code="BOOK_INVALID",
            source=src,
            policy=policy,
            as_of_time_ns=as_of_time_ns,
        )

    snapshot = dict(runtime_capability) if runtime_capability else {}
    timeliness = _axis(snapshot.get("timeliness"))
    entitlement = _axis(snapshot.get("entitlement"))
    runtime_state = _axis(snapshot.get("runtime_state"))

    if entitlement == "NOT_ENTITLED" or runtime_state == "NOT_ENTITLED":
        return _result(
            status=FRESHNESS_UNKNOWN,
            reason_code="NOT_ENTITLED",
            source=src,
            policy=policy,
            as_of_time_ns=as_of_time_ns,
            timeliness=timeliness,
            entitlement=entitlement or "NOT_ENTITLED",
        )

    if timeliness == "STALE" or runtime_state == "STALE":
        return _result(
            status=FRESHNESS_STALE,
            reason_code="G7_RUNTIME_STALE",
            source=src,
            policy=policy,
            as_of_time_ns=as_of_time_ns,
            timeliness=timeliness or "STALE",
            entitlement=entitlement,
        )

    if timeliness == "DELAYED" and policy.realtime_required:
        return _result(
            status=FRESHNESS_UNKNOWN,
            reason_code="DELAYED_WHEN_REALTIME_REQUIRED",
            source=src,
            policy=policy,
            as_of_time_ns=as_of_time_ns,
            timeliness=timeliness,
            entitlement=entitlement,
        )

    if as_of_time_ns is None:
        return _result(
            status=FRESHNESS_UNKNOWN,
            reason_code="MISSING_AS_OF",
            source=src,
            policy=policy,
            timeliness=timeliness,
            entitlement=entitlement,
        )

    if last_source_time_ns is None and not snapshot:
        return _result(
            status=FRESHNESS_UNKNOWN,
            reason_code="NO_EVENT",
            source=src,
            policy=policy,
            as_of_time_ns=as_of_time_ns,
            timeliness=timeliness,
            entitlement=entitlement,
        )

    if last_source_time_ns is None:
        return _result(
            status=FRESHNESS_UNKNOWN,
            reason_code="MISSING_SOURCE_TIME",
            source=src,
            policy=policy,
            as_of_time_ns=as_of_time_ns,
            timeliness=timeliness,
            entitlement=entitlement,
        )

    age_ns = as_of_time_ns - last_source_time_ns
    delayed_allowed = timeliness == "DELAYED" and not policy.realtime_required
    if age_ns > policy.stale_after_ns:
        return _result(
            status=FRESHNESS_STALE,
            reason_code="STALE_AFTER_THRESHOLD",
            source=src,
            policy=policy,
            as_of_time_ns=as_of_time_ns,
            age_ns=age_ns,
            timeliness=timeliness,
            entitlement=entitlement,
        )
    return _result(
        status=FRESHNESS_FRESH,
        reason_code="DELAYED_ALLOWED" if delayed_allowed else "FRESH",
        source=src,
        policy=policy,
        as_of_time_ns=as_of_time_ns,
        age_ns=age_ns,
        timeliness=timeliness,
        entitlement=entitlement,
    )


def merge_freshness_into_payload(
    payload: Mapping[str, Any] | None,
    evaluation: OpportunityFreshnessResult,
) -> dict[str, Any]:
    body = dict(payload or {})
    body["freshness"] = evaluation.to_dict()
    return body


def fail_closed_for_actionable(evaluation: OpportunityFreshnessResult | Mapping[str, Any]) -> bool:
    if isinstance(evaluation, OpportunityFreshnessResult):
        status = evaluation.status
    else:
        status = str(evaluation.get("status") or "")
    return status in {FRESHNESS_STALE, FRESHNESS_UNKNOWN}


__all__ = [
    "CLOCK_UTC_NS",
    "DEFAULT_STALE_AFTER_NS",
    "FRESHNESS_FRESH",
    "FRESHNESS_NOT_APPLICABLE",
    "FRESHNESS_STALE",
    "FRESHNESS_UNKNOWN",
    "HONESTY_SOURCES",
    "OpportunityFreshnessPolicy",
    "OpportunityFreshnessResult",
    "evaluate_opportunity_freshness",
    "fail_closed_for_actionable",
    "merge_freshness_into_payload",
]
