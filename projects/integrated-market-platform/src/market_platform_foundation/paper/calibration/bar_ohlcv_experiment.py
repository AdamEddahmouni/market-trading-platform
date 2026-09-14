"""Dry-run Item 9 bounded comparator experiment (IMP sim vs bar timing contract)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from ...execution.simulator import SIMULATOR_VERSION, BarConservativeSimulator
from ...risk.policy import DEFAULT_RISK_POLICY
from .bar_ohlcv_sources import (
    SOURCE_ADMITTED_EQUITY_INTRADAY,
    SOURCE_MOOMOO_OPEND_KLINE_1M,
    BarLoadResult,
    first_admissible_post_signal_bar,
    load_admitted_equity_intraday_bars,
    load_moomoo_opend_kline_bars,
)
from .runner import classify_calibration_run

CLASSIFICATION_RUNNABLE = "EXPERIMENT_RUNNABLE"
CLASSIFICATION_CONTRACT_MISMATCH = "EXPERIMENT_CONTRACT_MISMATCH"
CLASSIFICATION_SOURCE_UNAVAILABLE = "BAR_SOURCE_UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class BarOhlcvExperimentResult:
    classification: str
    signal_time_ns: int
    observation_time_ns: int
    bar_source_id: str
    instrument_id: str
    bar_provenance: dict[str, Any]
    first_post_signal_bar: dict[str, Any] | None
    simulator_version: str
    sim_order_state: str | None
    sim_reason_codes: tuple[str, ...]
    sim_fill: dict[str, Any] | None
    comparator_harness_status: str
    calibrated: bool
    orders_placed: bool

    def to_dict(self) -> dict[str, Any]:
        first = self.first_post_signal_bar
        return {
            "classification": self.classification,
            "signal_time_ns": self.signal_time_ns,
            "observation_time_ns": self.observation_time_ns,
            "bar_source_id": self.bar_source_id,
            "instrument_id": self.instrument_id,
            "bar_provenance": dict(self.bar_provenance),
            "first_post_signal_bar": None
            if first is None
            else {
                "event_time_ns": int(first.get("event_time") or 0),
                "available_time_ns": int(first["available_time"]),
                "normalized_event_id": first.get("normalized_event_id"),
                "bar_payload": dict(first.get("bar_payload") or {}),
            },
            "simulator_version": self.simulator_version,
            "sim_order_state": self.sim_order_state,
            "sim_reason_codes": list(self.sim_reason_codes),
            "sim_fill": self.sim_fill,
            "comparator_harness_status": self.comparator_harness_status,
            "calibrated": False,
            "orders_placed": False,
            "empirical_active": False,
        }


def _load_bars(
    *,
    source: str,
    collection_root: Path,
    instrument_id: str,
    observation_time_ns: int,
    kline_rows: tuple[Mapping[str, Any], ...] | None,
) -> BarLoadResult:
    if source == "moomoo-opend":
        return load_moomoo_opend_kline_bars(
            instrument_id=instrument_id,
            observation_time_ns=observation_time_ns,
            kline_rows=kline_rows,
        )
    return load_admitted_equity_intraday_bars(
        collection_root=collection_root,
        instrument_id=instrument_id,
        observation_time_ns=observation_time_ns,
    )


def run_bounded_bar_ohlcv_experiment(
    *,
    signal_time_ns: int,
    observation_time_ns: int,
    instrument_id: str,
    source: str = "admitted-fixture",
    collection_root: Path,
    env: Mapping[str, str] | None = None,
    direction: str = "long",
    quantity: int = 1,
    kline_rows: tuple[Mapping[str, Any], ...] | None = None,
) -> BarOhlcvExperimentResult:
    """Classify bar admissibility and dry-run ``BarConservativeSimulator`` (no broker)."""

    env_map = dict(env or {})
    harness_status = classify_calibration_run(env=env_map, now_ns=observation_time_ns)
    loaded = _load_bars(
        source=source,
        collection_root=collection_root,
        instrument_id=instrument_id,
        observation_time_ns=observation_time_ns,
        kline_rows=kline_rows,
    )
    if not loaded.ok:
        classification = (
            CLASSIFICATION_CONTRACT_MISMATCH
            if loaded.reason_code == CLASSIFICATION_CONTRACT_MISMATCH
            else CLASSIFICATION_SOURCE_UNAVAILABLE
        )
        return BarOhlcvExperimentResult(
            classification=classification,
            signal_time_ns=signal_time_ns,
            observation_time_ns=observation_time_ns,
            bar_source_id=loaded.source_id,
            instrument_id=instrument_id,
            bar_provenance={**loaded.provenance, "reason_code": loaded.reason_code},
            first_post_signal_bar=None,
            simulator_version=SIMULATOR_VERSION,
            sim_order_state=None,
            sim_reason_codes=(),
            sim_fill=None,
            comparator_harness_status=harness_status,
            calibrated=False,
            orders_placed=False,
        )

    first_bar = first_admissible_post_signal_bar(loaded.bars, signal_time_ns=signal_time_ns)
    if first_bar is None:
        return BarOhlcvExperimentResult(
            classification=CLASSIFICATION_CONTRACT_MISMATCH,
            signal_time_ns=signal_time_ns,
            observation_time_ns=observation_time_ns,
            bar_source_id=loaded.source_id,
            instrument_id=instrument_id,
            bar_provenance=loaded.provenance,
            first_post_signal_bar=None,
            simulator_version=SIMULATOR_VERSION,
            sim_order_state="REJECTED",
            sim_reason_codes=("SIM_NO_POST_SIGNAL_BAR",),
            sim_fill=None,
            comparator_harness_status=harness_status,
            calibrated=False,
            orders_placed=False,
        )

    simulator = BarConservativeSimulator(policy=DEFAULT_RISK_POLICY)
    intent = {
        "created_time": signal_time_ns,
        "direction": direction,
        "execution_mode": "INTERNAL_SIMULATION",
        "instrument_id": instrument_id,
        "intent_id": f"item9-dry-{signal_time_ns}",
    }
    risk_decision = {"decision": "APPROVE", "approved_quantity": quantity}
    order, fill = simulator.simulate(
        intent=intent,
        risk_decision=risk_decision,
        bars=list(loaded.bars),
    )
    reason_codes = tuple(str(code) for code in order.get("reason_codes") or [])
    return BarOhlcvExperimentResult(
        classification=CLASSIFICATION_RUNNABLE,
        signal_time_ns=signal_time_ns,
        observation_time_ns=observation_time_ns,
        bar_source_id=loaded.source_id,
        instrument_id=instrument_id,
        bar_provenance=loaded.provenance,
        first_post_signal_bar=first_bar,
        simulator_version=SIMULATOR_VERSION,
        sim_order_state=str(order.get("state")),
        sim_reason_codes=reason_codes,
        sim_fill=fill,
        comparator_harness_status=harness_status,
        calibrated=False,
        orders_placed=False,
    )


def default_collection_root() -> Path:
    """Monorepo ``projects/`` root (parent of IMP package)."""

    return Path(__file__).resolve().parents[5]


__all__ = [
    "CLASSIFICATION_CONTRACT_MISMATCH",
    "CLASSIFICATION_RUNNABLE",
    "CLASSIFICATION_SOURCE_UNAVAILABLE",
    "BarOhlcvExperimentResult",
    "default_collection_root",
    "run_bounded_bar_ohlcv_experiment",
    "SOURCE_ADMITTED_EQUITY_INTRADAY",
    "SOURCE_MOOMOO_OPEND_KLINE_1M",
]
