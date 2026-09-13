"""Frozen multi-provider observation snapshot comparison (offline only).

Compares normalized rows keyed by ``instrument_key`` across provider arms in a
frozen capture. Intended for local probes and fixture-backed audits — never for
live network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

FROZEN_COMPARE_SCHEMA_VERSION = "1.0.0"
FROZEN_COMPARE_LOGICAL_ID = "providers.frozen_observation_compare"


class FrozenCompareError(ValueError):
    """Invalid frozen compare snapshot or compare inputs."""


@dataclass(frozen=True, slots=True)
class FrozenObservationRow:
    instrument_key: str
    value: float | str | int | bool | None
    latency_ns: int | None = None
    received_time_ns: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "instrument_key": self.instrument_key,
            "value": self.value,
            "latency_ns": self.latency_ns,
            "received_time_ns": self.received_time_ns,
        }


@dataclass(frozen=True, slots=True)
class FrozenProviderArm:
    provider_id: str
    observations: tuple[FrozenObservationRow, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "observations": [row.to_dict() for row in self.observations],
        }


@dataclass(frozen=True, slots=True)
class FrozenCompareSnapshot:
    schema_version: str
    logical_id: str
    observed_at: str
    capability_id: str
    arms: tuple[FrozenProviderArm, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "logical_id": self.logical_id,
            "observed_at": self.observed_at,
            "capability_id": self.capability_id,
            "arms": [arm.to_dict() for arm in self.arms],
        }


@dataclass(frozen=True, slots=True)
class ArmCompareMetrics:
    candidate_provider_id: str
    reference_provider_id: str
    instrument_keys_compared: int
    missing_in_candidate: tuple[str, ...]
    missing_in_reference: tuple[str, ...]
    value_disagreements: tuple[dict[str, Any], ...]
    latency_deltas_ns: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_provider_id": self.candidate_provider_id,
            "reference_provider_id": self.reference_provider_id,
            "instrument_keys_compared": self.instrument_keys_compared,
            "missing_in_candidate": list(self.missing_in_candidate),
            "missing_in_reference": list(self.missing_in_reference),
            "value_disagreements": list(self.value_disagreements),
            "latency_deltas_ns": list(self.latency_deltas_ns),
        }


@dataclass(frozen=True, slots=True)
class FrozenSnapshotCompareReport:
    schema_version: str
    logical_id: str
    capability_id: str
    reference_provider_id: str
    arms: tuple[ArmCompareMetrics, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "logical_id": self.logical_id,
            "capability_id": self.capability_id,
            "reference_provider_id": self.reference_provider_id,
            "arms": [arm.to_dict() for arm in self.arms],
        }


def _row_index(arm: FrozenProviderArm) -> dict[str, FrozenObservationRow]:
    index: dict[str, FrozenObservationRow] = {}
    for row in arm.observations:
        key = row.instrument_key.strip()
        if not key:
            raise FrozenCompareError("observation instrument_key must be non-empty")
        if key in index:
            raise FrozenCompareError(
                f"duplicate instrument_key {key!r} in arm {arm.provider_id!r}"
            )
        index[key] = row
    return index


def _values_equal(
    left: float | str | int | bool | None,
    right: float | str | int | bool | None,
    *,
    numeric_tolerance: float,
) -> bool:
    if left is None and right is None:
        return True
    if left is None or right is None:
        return False
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return abs(float(left) - float(right)) <= numeric_tolerance
    return left == right


def validate_frozen_compare_snapshot(snapshot: FrozenCompareSnapshot) -> None:
    if snapshot.schema_version != FROZEN_COMPARE_SCHEMA_VERSION:
        raise FrozenCompareError("unsupported schema_version")
    if snapshot.logical_id != FROZEN_COMPARE_LOGICAL_ID:
        raise FrozenCompareError("unexpected logical_id")
    if not snapshot.observed_at.strip():
        raise FrozenCompareError("observed_at required")
    if not snapshot.capability_id.strip():
        raise FrozenCompareError("capability_id required")
    if len(snapshot.arms) < 2:
        raise FrozenCompareError("at least two provider arms required")
    provider_ids = [arm.provider_id for arm in snapshot.arms]
    if len(set(provider_ids)) != len(provider_ids):
        raise FrozenCompareError("duplicate provider_id across arms")
    for arm in snapshot.arms:
        _row_index(arm)


def frozen_compare_snapshot_from_dict(payload: Mapping[str, Any]) -> FrozenCompareSnapshot:
    arms: list[FrozenProviderArm] = []
    for arm_payload in payload.get("arms") or ():
        observations: list[FrozenObservationRow] = []
        for row in arm_payload.get("observations") or ():
            observations.append(
                FrozenObservationRow(
                    instrument_key=str(row["instrument_key"]),
                    value=row.get("value"),
                    latency_ns=row.get("latency_ns"),
                    received_time_ns=row.get("received_time_ns"),
                )
            )
        arms.append(
            FrozenProviderArm(
                provider_id=str(arm_payload["provider_id"]),
                observations=tuple(observations),
            )
        )
    snapshot = FrozenCompareSnapshot(
        schema_version=str(payload.get("schema_version", "")),
        logical_id=str(payload.get("logical_id", "")),
        observed_at=str(payload.get("observed_at", "")),
        capability_id=str(payload.get("capability_id", "")),
        arms=tuple(arms),
    )
    validate_frozen_compare_snapshot(snapshot)
    return snapshot


def compare_frozen_provider_snapshot(
    snapshot: FrozenCompareSnapshot,
    *,
    reference_provider_id: str | None = None,
    numeric_tolerance: float = 1e-9,
) -> FrozenSnapshotCompareReport:
    """Compare all non-reference arms against the reference arm."""
    validate_frozen_compare_snapshot(snapshot)
    ordered = sorted(snapshot.arms, key=lambda arm: arm.provider_id)
    reference_id = reference_provider_id or ordered[0].provider_id
    reference_arm = next((arm for arm in ordered if arm.provider_id == reference_id), None)
    if reference_arm is None:
        raise FrozenCompareError(f"reference provider {reference_id!r} not in snapshot")

    reference_index = _row_index(reference_arm)
    reference_keys = set(reference_index)
    metrics: list[ArmCompareMetrics] = []

    for candidate in ordered:
        if candidate.provider_id == reference_id:
            continue
        candidate_index = _row_index(candidate)
        candidate_keys = set(candidate_index)
        missing_in_candidate = tuple(sorted(reference_keys - candidate_keys))
        missing_in_reference = tuple(sorted(candidate_keys - reference_keys))
        shared = sorted(reference_keys & candidate_keys)

        disagreements: list[dict[str, Any]] = []
        latency_deltas: list[dict[str, Any]] = []
        for key in shared:
            ref_row = reference_index[key]
            cand_row = candidate_index[key]
            if not _values_equal(
                ref_row.value, cand_row.value, numeric_tolerance=numeric_tolerance
            ):
                disagreements.append(
                    {
                        "instrument_key": key,
                        "reference_value": ref_row.value,
                        "candidate_value": cand_row.value,
                    }
                )
            if ref_row.latency_ns is not None and cand_row.latency_ns is not None:
                latency_deltas.append(
                    {
                        "instrument_key": key,
                        "reference_latency_ns": ref_row.latency_ns,
                        "candidate_latency_ns": cand_row.latency_ns,
                        "delta_ns": cand_row.latency_ns - ref_row.latency_ns,
                    }
                )

        metrics.append(
            ArmCompareMetrics(
                candidate_provider_id=candidate.provider_id,
                reference_provider_id=reference_id,
                instrument_keys_compared=len(shared),
                missing_in_candidate=missing_in_candidate,
                missing_in_reference=missing_in_reference,
                value_disagreements=tuple(disagreements),
                latency_deltas_ns=tuple(latency_deltas),
            )
        )

    return FrozenSnapshotCompareReport(
        schema_version=FROZEN_COMPARE_SCHEMA_VERSION,
        logical_id=FROZEN_COMPARE_LOGICAL_ID,
        capability_id=snapshot.capability_id,
        reference_provider_id=reference_id,
        arms=tuple(metrics),
    )


def summarize_missingness(report: FrozenSnapshotCompareReport) -> dict[str, int]:
    """Aggregate missing-key counts per candidate arm (deterministic ordering)."""
    summary: dict[str, int] = {}
    for arm in report.arms:
        summary[arm.candidate_provider_id] = len(arm.missing_in_candidate)
    return summary


__all__ = [
    "ArmCompareMetrics",
    "FrozenCompareError",
    "FrozenCompareSnapshot",
    "FrozenObservationRow",
    "FrozenProviderArm",
    "FrozenSnapshotCompareReport",
    "FROZEN_COMPARE_LOGICAL_ID",
    "FROZEN_COMPARE_SCHEMA_VERSION",
    "compare_frozen_provider_snapshot",
    "frozen_compare_snapshot_from_dict",
    "summarize_missingness",
    "validate_frozen_compare_snapshot",
]
