"""Legal bridge from Item 9 prospective proof receipts to comparator analysis (no orders)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .bar_ohlcv_experiment import run_bounded_bar_ohlcv_experiment
from .bar_ohlcv_prospective_proof import (
    PROOF_MODE_PROSPECTIVE,
    RECEIPT_CONTRACT_VERSION,
    build_first_post_signal_proof,
)
from .runner import (
    STATUS_COMPARATOR_NOT_CONFIGURED,
    alpaca_paper_configured,
    classify_calibration_run,
)

REASON_NOT_PROSPECTIVE_RECEIPT = "NOT_PROSPECTIVE_RECEIPT"
REASON_RECEIPT_INCOMPLETE = "RECEIPT_INCOMPLETE"
BRIDGE_STATUS_IMP_LEG_ONLY = "PROSPECTIVE_RECEIPT_IMP_LEG_ONLY"


def load_prospective_receipt(path: Path) -> dict[str, Any]:
    """Load and minimally validate a persisted prospective proof receipt."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("receipt root must be a JSON object")
    return payload


def _required_receipt_fields(receipt: Mapping[str, Any]) -> tuple[str, ...]:
    return (
        "experiment_id",
        "proof_mode",
        "instrument_id",
        "signal_time_ns",
        "observation_time_ns",
        "runtime_git_sha",
        "orders_placed",
        "calibrated",
    )


def validate_prospective_receipt_for_comparator(receipt: Mapping[str, Any]) -> dict[str, Any]:
    """Fail closed unless the receipt is lawful prospective evidence."""

    missing = [key for key in _required_receipt_fields(receipt) if key not in receipt]
    if missing:
        return {
            "ok": False,
            "reason_code": REASON_RECEIPT_INCOMPLETE,
            "missing_fields": missing,
        }
    if str(receipt.get("proof_mode")) != PROOF_MODE_PROSPECTIVE:
        return {
            "ok": False,
            "reason_code": REASON_NOT_PROSPECTIVE_RECEIPT,
            "proof_mode": receipt.get("proof_mode"),
        }
    if receipt.get("not_prospective_evidence"):
        return {
            "ok": False,
            "reason_code": REASON_NOT_PROSPECTIVE_RECEIPT,
            "not_prospective_evidence": True,
        }
    if receipt.get("orders_placed") or receipt.get("calibrated"):
        return {
            "ok": False,
            "reason_code": REASON_RECEIPT_INCOMPLETE,
            "detail": "receipt must stamp orders_placed=false and calibrated=false",
        }
    return {"ok": True, "reason_code": None}


def comparator_configuration_summary(
    env: Mapping[str, str],
    *,
    now_ns: int,
) -> dict[str, Any]:
    """Expose gate presence without secrets."""

    return {
        "alpaca_paper_configured": alpaca_paper_configured(env),
        "imp_alpaca_paper_gate": env.get("IMP_ALPACA_PAPER") == "1",
        "imp_broker_paper_execution_gate": env.get("IMP_BROKER_PAPER_EXECUTION") == "1",
        "apca_key_id_present": bool(str(env.get("APCA_API_KEY_ID") or "").strip()),
        "apca_secret_present": bool(str(env.get("APCA_API_SECRET_KEY") or "").strip()),
        "comparator_harness_status": classify_calibration_run(env=env, now_ns=now_ns),
    }


def build_comparator_bridge_from_receipt(
    receipt: Mapping[str, Any],
    *,
    env: Mapping[str, str],
    collection_root: Path,
) -> dict[str, Any]:
    """Map a prospective receipt to comparator-ready analysis without placing orders."""

    gate = validate_prospective_receipt_for_comparator(receipt)
    if not gate["ok"]:
        return {
            "ok": False,
            "reason_code": gate["reason_code"],
            "bridge_status": None,
            "matched_pair_count": 0,
            "orders_placed": False,
            "calibrated": False,
            "detail": gate,
        }

    observation_ns = int(receipt["observation_time_ns"])
    harness_status = str(
        receipt.get("comparator_harness_status")
        or classify_calibration_run(env=env, now_ns=observation_ns),
    )
    config = comparator_configuration_summary(env, now_ns=observation_ns)
    config["comparator_harness_status_at_bridge"] = harness_status

    first_bar = receipt.get("first_post_signal_bar")
    if isinstance(first_bar, Mapping) and "available_time_ns" in first_bar:
        bar_row = {
            "event_time": first_bar.get("event_time_ns"),
            "available_time": first_bar["available_time_ns"],
            "normalized_event_id": first_bar.get("normalized_event_id"),
        }
    else:
        bar_row = {
            "event_time": receipt.get("bar_event_time_ns"),
            "available_time": receipt.get("bar_available_time_ns"),
            "normalized_event_id": receipt.get("bar_id"),
        }

    proof = receipt.get("first_post_signal_proof")
    if not isinstance(proof, Mapping):
        proof = build_first_post_signal_proof(
            signal_time_ns=int(receipt["signal_time_ns"]),
            signal_established_at_ns=receipt.get("signal_established_at_ns"),
            bar=bar_row if bar_row.get("available_time") is not None else None,
            observation_time_ns=observation_ns,
        )

    dry_run = run_bounded_bar_ohlcv_experiment(
        signal_time_ns=int(receipt["signal_time_ns"]),
        observation_time_ns=observation_ns,
        instrument_id=str(receipt["instrument_id"]),
        source="moomoo-opend",
        collection_root=collection_root,
        env=env,
        kline_rows=None,
    )

    return {
        "ok": True,
        "reason_code": None,
        "bridge_status": BRIDGE_STATUS_IMP_LEG_ONLY,
        "experiment_id": str(receipt["experiment_id"]),
        "receipt_contract_version": str(receipt.get("receipt_contract_version") or RECEIPT_CONTRACT_VERSION),
        "runtime_git_sha": str(receipt.get("runtime_git_sha") or ""),
        "proof_mode": PROOF_MODE_PROSPECTIVE,
        "first_post_signal_proof": dict(proof),
        "imp_simulator_leg": {
            "simulator_version": receipt.get("simulator_version") or dry_run.simulator_version,
            "sim_order_state": receipt.get("sim_order_state") or dry_run.sim_order_state,
            "sim_reason_codes": list(receipt.get("sim_reason_codes") or dry_run.sim_reason_codes),
            "classification": dry_run.classification,
        },
        "comparator_external_leg": None,
        "comparator_configuration": config,
        "matched_pair_count": 0,
        "orders_placed": False,
        "calibrated": False,
        "empirical_active": False,
        "item9_status": "PARTIAL_NOT_CALIBRATED",
        "message": (
            "Prospective receipt binds IMP simulator timing only; "
            "external Paper fill pairing requires a separate lawful order — not generated here."
        ),
        "dry_run_replay": dry_run.to_dict(),
    }


def bridge_payload_for_missing_comparator(env: Mapping[str, str], *, now_ns: int) -> dict[str, Any]:
    """Explicit negative result when Alpaca Paper is not configured."""

    config = comparator_configuration_summary(env, now_ns=now_ns)
    status = str(config["comparator_harness_status"])
    return {
        "ok": False,
        "reason_code": status if status == STATUS_COMPARATOR_NOT_CONFIGURED else status,
        "comparator_configuration": config,
        "matched_pair_count": 0,
        "orders_placed": False,
        "calibrated": False,
    }


__all__ = [
    "BRIDGE_STATUS_IMP_LEG_ONLY",
    "REASON_NOT_PROSPECTIVE_RECEIPT",
    "REASON_RECEIPT_INCOMPLETE",
    "build_comparator_bridge_from_receipt",
    "bridge_payload_for_missing_comparator",
    "comparator_configuration_summary",
    "load_prospective_receipt",
    "validate_prospective_receipt_for_comparator",
]
