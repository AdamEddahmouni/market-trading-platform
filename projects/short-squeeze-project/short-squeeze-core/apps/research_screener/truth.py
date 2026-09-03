"""The display truth model.

Every value the screener shows travels as a :class:`FieldValue`. A ``FieldValue`` either
carries a real observed value together with its provenance, or carries no value at all
plus an explicit reason. There is no third state, so a missing value can never reach the
user interface disguised as ``0``, ``""`` or a neutral blank.

This module holds no metric formula and no rule logic.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

SCHEMA_VERSION = "1.0.0"


class DataMode(StrEnum):
    """How the value relates to the market clock. Never inferred, always asserted."""

    LIVE = "LIVE"
    DELAYED = "DELAYED"
    HISTORICAL = "HISTORICAL"
    FROZEN_RESEARCH = "FROZEN_RESEARCH"
    REPLAY = "REPLAY"
    UNAVAILABLE = "UNAVAILABLE"


class Freshness(StrEnum):
    """Explicit freshness. ``UNKNOWN_AGE`` is used whenever age cannot be computed."""

    CURRENT = "CURRENT"
    DELAYED = "DELAYED"
    STALE = "STALE"
    FROZEN = "FROZEN"
    UNKNOWN_AGE = "UNKNOWN_AGE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ValueStatus(StrEnum):
    """Why a cell has, or does not have, a value."""

    KNOWN = "KNOWN"
    UNKNOWN = "UNKNOWN"
    UNAVAILABLE = "UNAVAILABLE"
    NOT_COLLECTED = "NOT_COLLECTED"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    BLOCKED = "BLOCKED"


#: Statuses that mean "there is no value here". Rendered as an em dash plus the label.
MISSING_STATUSES = frozenset(
    {
        ValueStatus.UNKNOWN,
        ValueStatus.UNAVAILABLE,
        ValueStatus.NOT_COLLECTED,
        ValueStatus.NOT_CONFIGURED,
        ValueStatus.BLOCKED,
    }
)

#: What the user interface prints where a value would have been.
MISSING_PLACEHOLDER = "—"


class FieldValue:
    """One displayable cell with its full provenance.

    ``value`` is ``None`` for every status other than ``KNOWN``. The constructor enforces
    that, so no caller can attach a placeholder number to a missing field.
    """

    __slots__ = (
        "status",
        "value",
        "unit",
        "provider",
        "event_time",
        "received_time",
        "freshness",
        "data_mode",
        "evidence_id",
        "readiness",
        "provider_field",
        "selection_reason",
        "research_admissibility",
        "missing_reason",
        "missing_reason_code",
    )

    def __init__(
        self,
        *,
        status: ValueStatus,
        value: Any = None,
        unit: str | None = None,
        provider: str | None = None,
        event_time: str | None = None,
        received_time: str | None = None,
        freshness: Freshness = Freshness.UNKNOWN_AGE,
        data_mode: DataMode = DataMode.UNAVAILABLE,
        evidence_id: str | None = None,
        readiness: str | None = None,
        provider_field: str | None = None,
        selection_reason: str | None = None,
        research_admissibility: str | None = None,
        missing_reason: str | None = None,
        missing_reason_code: str | None = None,
    ) -> None:
        status = ValueStatus(status)
        if status is ValueStatus.KNOWN:
            if value is None:
                raise ValueError("a KNOWN FieldValue must carry a value")
            if missing_reason or missing_reason_code:
                raise ValueError("a KNOWN FieldValue must not carry a missing reason")
        else:
            if value is not None:
                raise ValueError(
                    f"a {status} FieldValue must not carry a value; missing is never a number"
                )
            if not missing_reason:
                raise ValueError(f"a {status} FieldValue must explain why it is missing")
        self.status = status
        self.value = value
        self.unit = unit
        self.provider = provider
        self.event_time = event_time
        self.received_time = received_time
        self.freshness = Freshness(freshness)
        self.data_mode = DataMode(data_mode)
        self.evidence_id = evidence_id
        self.readiness = readiness
        self.provider_field = provider_field
        self.selection_reason = selection_reason
        self.research_admissibility = research_admissibility
        self.missing_reason = missing_reason
        self.missing_reason_code = missing_reason_code

    @property
    def is_missing(self) -> bool:
        return self.status in MISSING_STATUSES

    @property
    def display(self) -> str:
        """The exact string the table renders. Missing is a dash, never a zero."""
        if self.is_missing:
            return MISSING_PLACEHOLDER
        return str(self.value)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": str(self.status),
            "value": self.value,
            "display": self.display,
            "unit": self.unit,
            "provider": self.provider,
            "event_time": self.event_time,
            "received_time": self.received_time,
            "freshness": str(self.freshness),
            "data_mode": str(self.data_mode),
            "evidence_id": self.evidence_id,
            "readiness": self.readiness,
            "provider_field": self.provider_field,
            "selection_reason": self.selection_reason,
            "research_admissibility": self.research_admissibility,
            "missing_reason": self.missing_reason,
            "missing_reason_code": self.missing_reason_code,
        }


def known(
    value: Any,
    *,
    unit: str | None = None,
    provider: str | None = None,
    event_time: str | None = None,
    received_time: str | None = None,
    freshness: Freshness = Freshness.UNKNOWN_AGE,
    data_mode: DataMode = DataMode.UNAVAILABLE,
    evidence_id: str | None = None,
    readiness: str | None = None,
    provider_field: str | None = None,
    selection_reason: str | None = None,
    research_admissibility: str | None = None,
) -> FieldValue:
    """Build a value-bearing cell."""
    return FieldValue(
        status=ValueStatus.KNOWN,
        value=value,
        unit=unit,
        provider=provider,
        event_time=event_time,
        received_time=received_time,
        freshness=freshness,
        data_mode=data_mode,
        evidence_id=evidence_id,
        readiness=readiness,
        provider_field=provider_field,
        selection_reason=selection_reason,
        research_admissibility=research_admissibility,
    )


def missing(
    status: ValueStatus,
    reason: str,
    *,
    reason_code: str | None = None,
    provider: str | None = None,
    data_mode: DataMode = DataMode.UNAVAILABLE,
    freshness: Freshness = Freshness.NOT_APPLICABLE,
    readiness: str | None = None,
) -> FieldValue:
    """Build a valueless cell that states why it is valueless."""
    return FieldValue(
        status=status,
        missing_reason=reason,
        missing_reason_code=reason_code,
        provider=provider,
        data_mode=data_mode,
        freshness=freshness,
        readiness=readiness,
    )


__all__ = [
    "MISSING_PLACEHOLDER",
    "MISSING_STATUSES",
    "SCHEMA_VERSION",
    "DataMode",
    "FieldValue",
    "Freshness",
    "ValueStatus",
    "known",
    "missing",
]
