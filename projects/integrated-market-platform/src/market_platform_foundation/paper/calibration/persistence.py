"""Persist calibration pairs onto PD-09 schema v6 forward_test_observations.

No second campaign database. Observations are append-only on the existing
SQLite store. Live mode is refused. Restart reconstructs from the same rows.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping

from ...clock import monotonic_wall_ns
from ...execution.simulator import SIMULATOR_VERSION
from ...intelligence.paper_forward_bridge.identity import forward_test_observation_id
from ...intelligence.paper_forward_bridge.paper_handoff import (
    forward_test_correlation_id,
)
from ...intelligence.paper_forward_bridge.repository import (
    ForwardTestRepository,
    ForwardTestRepositoryError,
)
from ...intelligence.paper_forward_bridge.types import (
    ForwardTestDecision,
    ForwardTestObservation,
)
from .asset_scope import EQUITY_PAPER_DOES_NOT_VALIDATE_ES, equity_es_firewall_payload
from .comparator_contract import ExternalPaperComparatorBinding
from .pairing import PairedObservation, PairingResult

CALIBRATION_OBSERVATION_SCHEMA = "paper/calibration_observation/1.0.0"
CALIBRATION_PAIR_KIND = "CALIBRATION_PAIR"
CALIBRATION_STATUS_KIND = "CALIBRATION_RUN_STATUS"


class CalibrationPersistenceError(ValueError):
    """Calibration observation could not be written to schema v6."""


def _reject_live(mode: str) -> None:
    if str(mode).upper() == "LIVE":
        raise ForwardTestRepositoryError("FORWARD_TEST_LIVE_MODE_FORBIDDEN")


def build_pair_observation_payload(
    pair: PairedObservation,
    *,
    comparator: ExternalPaperComparatorBinding,
    evidence_class: str,
    observation_label: str,
) -> dict[str, Any]:
    return {
        "kind": CALIBRATION_PAIR_KIND,
        "schema": CALIBRATION_OBSERVATION_SCHEMA,
        "correlation_id": pair.correlation_id,
        "forward_test_id": pair.forward_test_id,
        "paper_order_id": pair.paper_order_id,
        "comparator_order_id": pair.comparator_order_id,
        "pair_method": pair.pair_method,
        "pair_confidence": pair.pair_confidence,
        "simulator_version": pair.simulator_version or SIMULATOR_VERSION,
        "source_capability": pair.source_capability,
        "paper_account_id": pair.paper_account_id,
        "instrument_id": pair.instrument_id,
        "asset_class": pair.asset_class,
        "imp_leg": pair.imp.to_dict(),
        "comparator_leg": pair.comparator.to_dict(),
        "comparator_binding": comparator.to_dict(),
        "is_market_truth": False,
        "evidence_class": evidence_class,
        "observation_label": observation_label,
        "calibrated": False,
        "empirical_active": False,
        **equity_es_firewall_payload(),
    }


def persist_pairing_result(
    repository: ForwardTestRepository,
    *,
    decision: ForwardTestDecision,
    pairing: PairingResult,
    comparator: ExternalPaperComparatorBinding,
    evidence_class: str,
    observation_label: str,
    observed_at_ns: int | None = None,
) -> ForwardTestDecision:
    """Append paired calibration observations to an existing locked decision."""
    _reject_live(decision.mode)
    for pair in pairing.pairs:
        if pair.paper_account_id and pair.paper_account_id != decision.account_id:
            raise CalibrationPersistenceError("CALIBRATION_ACCOUNT_ISOLATION")
        if (
            pair.instrument_id
            and decision.symbol
            and pair.instrument_id.upper() != str(decision.symbol).upper()
        ):
            raise CalibrationPersistenceError("CALIBRATION_INSTRUMENT_ISOLATION")
    now_ns = observed_at_ns if observed_at_ns is not None else monotonic_wall_ns()
    new_rows: list[ForwardTestObservation] = []
    existing_ids = {item.observation_id for item in decision.observations}
    for offset, pair in enumerate(pairing.pairs):
        source_time_ns = now_ns + offset
        observation_id = forward_test_observation_id(
            forward_test_id=decision.forward_test_id,
            observed_at_ns=now_ns,
            source_time_ns=source_time_ns,
        )
        if observation_id in existing_ids:
            continue
        payload = build_pair_observation_payload(
            pair,
            comparator=comparator,
            evidence_class=evidence_class,
            observation_label=observation_label,
        )
        payload["correlation_id"] = payload.get("correlation_id") or forward_test_correlation_id(
            decision.forward_test_id
        )
        payload["available_time_ns"] = source_time_ns
        payload["receive_time_ns"] = now_ns
        new_rows.append(
            ForwardTestObservation(
                observation_id=observation_id,
                observed_at_ns=now_ns,
                source_time_ns=source_time_ns,
                payload=payload,
            )
        )
    updated = replace(decision, observations=decision.observations + tuple(new_rows))
    repository.put_decision(updated)
    stored = repository.get_decision(decision.forward_test_id)
    if stored is None:
        raise CalibrationPersistenceError("CALIBRATION_OBSERVATION_PERSIST_FAILED")
    return stored


def persist_run_status(
    repository: ForwardTestRepository,
    *,
    decision: ForwardTestDecision,
    status: str,
    detail: Mapping[str, Any] | None = None,
    observed_at_ns: int | None = None,
) -> ForwardTestDecision:
    """Append a harness status row (WAITING_FOR_MARKET / COMPARATOR_NOT_CONFIGURED)."""
    _reject_live(decision.mode)
    now_ns = observed_at_ns if observed_at_ns is not None else monotonic_wall_ns()
    observation_id = forward_test_observation_id(
        forward_test_id=decision.forward_test_id,
        observed_at_ns=now_ns,
        source_time_ns=now_ns,
    )
    payload = {
        "kind": CALIBRATION_STATUS_KIND,
        "schema": CALIBRATION_OBSERVATION_SCHEMA,
        "status": status,
        "correlation_id": forward_test_correlation_id(decision.forward_test_id),
        "simulator_version": SIMULATOR_VERSION,
        "is_market_truth": False,
        "calibrated": False,
        "empirical_active": False,
        "equity_paper_does_not_validate_es": EQUITY_PAPER_DOES_NOT_VALIDATE_ES,
        "detail": dict(detail or {}),
        "available_time_ns": now_ns,
        "receive_time_ns": now_ns,
    }
    row = ForwardTestObservation(
        observation_id=observation_id,
        observed_at_ns=now_ns,
        source_time_ns=now_ns,
        payload=payload,
    )
    updated = replace(decision, observations=decision.observations + (row,))
    repository.put_decision(updated)
    stored = repository.get_decision(decision.forward_test_id)
    if stored is None:
        raise CalibrationPersistenceError("CALIBRATION_OBSERVATION_PERSIST_FAILED")
    return stored


__all__ = [
    "CALIBRATION_OBSERVATION_SCHEMA",
    "CALIBRATION_PAIR_KIND",
    "CALIBRATION_STATUS_KIND",
    "CalibrationPersistenceError",
    "build_pair_observation_payload",
    "persist_pairing_result",
    "persist_run_status",
]
