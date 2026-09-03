"""Scoped quality observation model and bar evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from ..canonical import canonical_bytes, sha256_bytes


@dataclass
class QualityObservation:
    dimension: str
    state: str
    severity: str
    scope: dict[str, str]
    available_time: int
    detected_at: int
    rule_id: str
    rule_version: str
    evidence_refs: list[str] = field(default_factory=list)
    expected: str | None = None
    observed: str | None = None
    affected_from: int | None = None
    affected_to: int | None = None
    quality_observation_id: str = ""

    def finalize(self) -> dict[str, Any]:
        body = {
            "affected_from": self.affected_from,
            "affected_to": self.affected_to,
            "available_time": self.available_time,
            "detected_at": self.detected_at,
            "dimension": self.dimension,
            "evidence_refs": sorted(self.evidence_refs),
            "expected": self.expected,
            "observed": self.observed,
            "rule_id": self.rule_id,
            "rule_version": self.rule_version,
            "scope": {key: self.scope[key] for key in sorted(self.scope)},
            "severity": self.severity,
            "state": self.state,
        }
        observation_id = sha256_bytes(canonical_bytes(body))
        body["quality_observation_id"] = observation_id
        return body


def _decimal(value: object) -> Decimal:
    return Decimal(str(value))


def validate_bar_payload(payload: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    try:
        high = _decimal(payload.get("high"))
        low = _decimal(payload.get("low"))
        open_ = _decimal(payload.get("open"))
        close = _decimal(payload.get("close"))
        volume = int(payload.get("volume", 0))
    except (ArithmeticError, TypeError, ValueError):
        return ["QUAL_INVALID_NUMERIC"]
    if high < low:
        reasons.append("QUAL_INVALID_HIGH_LOW")
    if not (low <= open_ <= high):
        reasons.append("QUAL_INVALID_OPEN_RANGE")
    if not (low <= close <= high):
        reasons.append("QUAL_INVALID_CLOSE_RANGE")
    if volume < 0:
        reasons.append("QUAL_INVALID_VOLUME")
    return reasons


def evaluate_bar_event(event: dict[str, Any], *, prior_bar: dict[str, Any] | None) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    scope = {
        "channel_id": str(event.get("channel_id", "")),
        "event_family": str(event.get("event_type", "")),
        "instrument_id": str(event.get("instrument_id", "")),
        "source_instance_id": str(event.get("source_instance_id", "")),
    }
    available_time = int(event["available_time"])
    event_time = int(event["event_time"])
    validity_reasons = validate_bar_payload(dict(event.get("bar_payload", {})))
    if validity_reasons:
        observations.append(
            QualityObservation(
                dimension="validity",
                state="INVALID_QUOTE",
                severity="ERROR",
                scope=scope,
                available_time=available_time,
                detected_at=available_time,
                rule_id="QUAL-BAR-VALIDITY-001",
                rule_version="1.0.0",
                evidence_refs=[str(event.get("normalized_event_id", ""))],
                expected="VALID",
                observed=",".join(validity_reasons),
            ).finalize()
        )
    if prior_bar is not None:
        prior_available = int(prior_bar["available_time"])
        prior_event_time = int(prior_bar["event_time"])
        if event_time < prior_event_time:
            observations.append(
                QualityObservation(
                    dimension="sequencing",
                    state="REGRESSION",
                    severity="ERROR",
                    scope=scope,
                    available_time=available_time,
                    detected_at=available_time,
                    rule_id="QUAL-BAR-SEQ-001",
                    rule_version="1.0.0",
                    evidence_refs=[str(event.get("normalized_event_id", ""))],
                    expected=str(prior_event_time),
                    observed=str(event_time),
                ).finalize()
            )
        elif event_time == prior_event_time:
            observations.append(
                QualityObservation(
                    dimension="sequencing",
                    state="DUPLICATE",
                    severity="WARN",
                    scope=scope,
                    available_time=available_time,
                    detected_at=available_time,
                    rule_id="QUAL-BAR-SEQ-002",
                    rule_version="1.0.0",
                    evidence_refs=[str(event.get("normalized_event_id", ""))],
                ).finalize()
            )
        elif event_time > prior_event_time + 60_000_000_000:
            observations.append(
                QualityObservation(
                    dimension="sequencing",
                    state="GAP",
                    severity="WARN",
                    scope=scope,
                    available_time=available_time,
                    detected_at=available_time,
                    affected_from=prior_available,
                    affected_to=available_time,
                    rule_id="QUAL-BAR-SEQ-003",
                    rule_version="1.0.0",
                    evidence_refs=[str(event.get("normalized_event_id", ""))],
                    expected="CONTIGUOUS_1M",
                    observed="GAP",
                ).finalize()
            )
    return observations


def consumer_eligibility(
    observations: list[dict[str, Any]],
    *,
    required_dimensions: tuple[str, ...] = ("validity", "sequencing"),
) -> tuple[str, list[str]]:
    blocking_states = {
        ("validity", "INVALID_QUOTE"),
        ("sequencing", "REGRESSION"),
    }
    reasons: list[str] = []
    for observation in observations:
        key = (str(observation["dimension"]), str(observation["state"]))
        if key in blocking_states:
            reasons.append(f"QUAL_BLOCKED_{key[0].upper()}_{key[1]}")
    for dimension in required_dimensions:
        if not any(row["dimension"] == dimension for row in observations):
            continue
    if reasons:
        return "BLOCKED", sorted(set(reasons))
    return "ELIGIBLE", []
