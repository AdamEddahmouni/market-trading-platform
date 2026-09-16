"""Item 9 OpenD BAR_OHLCV_1M prospective vs transport-proof operator contract."""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from ...git_ref import read_git_head
from ...intelligence.paper_forward_bridge.session_policy import is_within_us_equity_rth
from .bar_ohlcv_experiment import BarOhlcvExperimentResult, run_bounded_bar_ohlcv_experiment
from .bar_ohlcv_sources import (
    SOURCE_MOOMOO_OPEND_KLINE_1M,
    BarLoadResult,
    first_admissible_post_signal_bar,
    load_moomoo_opend_kline_bars,
    pit_visible_bars,
)

RECEIPT_CONTRACT_VERSION = "item9.bar-ohlcv-prospective-proof/1.1.0"
PROOF_MODE_RETROSPECTIVE = "RETROSPECTIVE_TRANSPORT_PROOF"
PROOF_MODE_PROSPECTIVE = "PROSPECTIVE_BAR_OHLCV_1M"
NOT_PROSPECTIVE_EVIDENCE = "NOT_PROSPECTIVE_EVIDENCE"

READINESS_TOOL_READY = "ITEM9_PROSPECTIVE_PROOF_TOOL_READY"
READINESS_RTH_REQUIRED = "SOFTWARE_READY_RTH_REQUIRED"

REASON_PROSPECTIVE_EXPLICIT_SIGNAL = "PROSPECTIVE_REFUSES_EXPLICIT_SIGNAL"
REASON_PROSPECTIVE_RETROSPECTIVE_SIGNAL = "PROSPECTIVE_REFUSES_RETROSPECTIVE_SIGNAL"
REASON_PROSPECTIVE_WRONG_SOURCE = "PROSPECTIVE_REQUIRES_MOOMOO_OPEND"
REASON_PROSPECTIVE_RTH_REQUIRED = READINESS_RTH_REQUIRED
REASON_NO_POST_SIGNAL_BAR = "PROSPECTIVE_NO_POST_SIGNAL_BAR"
REASON_POLL_REQUIRED = "POLL_REQUIRED"
REASON_PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"

DEFAULT_RECEIPT_DIR = Path("artifacts/ftep-v1-002/item9-prospective-proof-receipts")


@dataclass(frozen=True, slots=True)
class ProspectiveSignalValidation:
    ok: bool
    reason_code: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "reason_code": self.reason_code}


@dataclass(frozen=True, slots=True)
class BarDisplayRow:
    instrument_id: str
    bar_start_ns: int
    bar_end_ns: int
    available_time_ns: int
    fetch_time_ns: int
    provider_id: str
    source_instance_id: str
    normalized_event_id: str
    raw_row_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "instrument_id": self.instrument_id,
            "bar_start_ns": self.bar_start_ns,
            "bar_end_ns": self.bar_end_ns,
            "available_time_ns": self.available_time_ns,
            "fetch_time_ns": self.fetch_time_ns,
            "provider_id": self.provider_id,
            "source_instance_id": self.source_instance_id,
            "normalized_event_id": self.normalized_event_id,
            "raw_row_hash": self.raw_row_hash,
        }


def imp_package_root() -> Path:
    """IMP package root ``projects/integrated-market-platform/``."""

    return Path(__file__).resolve().parents[4]


def build_first_post_signal_proof(
    *,
    signal_time_ns: int,
    signal_established_at_ns: int | None,
    bar: Mapping[str, Any] | None,
    observation_time_ns: int | None = None,
) -> dict[str, Any]:
    """Document strict first-post-signal admissibility (no retrospective selection)."""

    if bar is None or bar.get("available_time") is None:
        return {
            "ok": False,
            "reason_code": REASON_NO_POST_SIGNAL_BAR,
            "signal_time_ns": signal_time_ns,
            "signal_established_at_ns": signal_established_at_ns,
        }
    bar_available = int(bar["available_time"])
    bar_start = int(bar.get("event_time") or 0)
    gate = validate_prospective_signal_vs_bar(
        signal_time_ns=signal_time_ns,
        signal_established_at_ns=signal_established_at_ns or signal_time_ns,
        bar_available_time_ns=bar_available,
    )
    return {
        "ok": gate.ok,
        "reason_code": gate.reason_code,
        "signal_time_ns": signal_time_ns,
        "signal_established_at_ns": signal_established_at_ns,
        "bar_id": str(bar.get("normalized_event_id") or ""),
        "bar_start_ns": bar_start,
        "bar_end_ns": bar_available,
        "bar_available_time_ns": bar_available,
        "strict_available_after_signal": bar_available > signal_time_ns,
        "signal_established_before_bar_available": (
            signal_established_at_ns is not None and signal_established_at_ns < bar_available
        ),
        "observation_at_or_after_bar_available": (
            observation_time_ns is not None and observation_time_ns >= bar_available
        ),
    }


def resolve_runtime_git_sha(*, start: Path | None = None) -> str:
    """Current HEAD via stdlib ``git_ref`` (no subprocess)."""

    anchor = start if start is not None else Path(__file__).resolve()
    head = read_git_head(start=anchor)
    if head is None or not head.strip():
        return "unknown"
    return head.strip()


def hash_raw_kline_rows(rows: Sequence[Mapping[str, Any]]) -> str:
    payload = json.dumps(list(rows), sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def validate_prospective_signal_request(
    *,
    proof_mode: str,
    signal_time_ns: int | None,
    signal_established_at_ns: int | None,
    source: str,
) -> ProspectiveSignalValidation:
    if proof_mode != PROOF_MODE_PROSPECTIVE:
        return ProspectiveSignalValidation(ok=True)
    if signal_time_ns is not None:
        return ProspectiveSignalValidation(ok=False, reason_code=REASON_PROSPECTIVE_EXPLICIT_SIGNAL)
    if source != "moomoo-opend":
        return ProspectiveSignalValidation(ok=False, reason_code=REASON_PROSPECTIVE_WRONG_SOURCE)
    if signal_established_at_ns is None:
        return ProspectiveSignalValidation(ok=False, reason_code=REASON_PROSPECTIVE_RETROSPECTIVE_SIGNAL)
    return ProspectiveSignalValidation(ok=True)


def validate_prospective_signal_vs_bar(
    *,
    signal_time_ns: int,
    signal_established_at_ns: int,
    bar_available_time_ns: int,
) -> ProspectiveSignalValidation:
    if signal_established_at_ns >= bar_available_time_ns:
        return ProspectiveSignalValidation(
            ok=False,
            reason_code=REASON_PROSPECTIVE_RETROSPECTIVE_SIGNAL,
        )
    if signal_time_ns >= bar_available_time_ns:
        return ProspectiveSignalValidation(
            ok=False,
            reason_code=REASON_PROSPECTIVE_RETROSPECTIVE_SIGNAL,
        )
    return ProspectiveSignalValidation(ok=True)


def item9_prospective_readiness(*, now_ns: int) -> dict[str, Any]:
    rth_active = is_within_us_equity_rth(now_ns)
    return {
        "readiness": READINESS_TOOL_READY,
        "empirical_status": READINESS_RTH_REQUIRED if not rth_active else "RTH_ACTIVE_AWAITING_OPERATOR",
        "rth_active": rth_active,
        "calibrated": False,
        "orders_placed": False,
        "empirical_active": False,
        "item9_status": "PARTIAL_NOT_CALIBRATED",
        "receipt_contract_version": RECEIPT_CONTRACT_VERSION,
    }


def prospective_run_without_poll_outcome(
    *,
    now_ns: int,
    signal_time_ns: int,
    signal_established_at_ns: int,
) -> dict[str, Any]:
    """Operator hint when Mode B is started without ``--poll`` (no OpenD polling)."""

    readiness = item9_prospective_readiness(now_ns=now_ns)
    if readiness["rth_active"]:
        return {
            "ok": False,
            "reason_code": REASON_POLL_REQUIRED,
            "readiness": readiness,
            "signal_time_ns": signal_time_ns,
            "signal_established_at_ns": signal_established_at_ns,
            "receipt": None,
            "message": "RTH active: re-run with --poll to wait for the first post-signal bar.",
        }
    return {
        "ok": False,
        "reason_code": READINESS_RTH_REQUIRED,
        "readiness": readiness,
        "signal_time_ns": signal_time_ns,
        "signal_established_at_ns": signal_established_at_ns,
        "receipt": None,
        "message": "US equity RTH is closed; use --poll during RTH to wait for the first post-signal bar.",
    }


def build_bar_display_rows(
    *,
    bars: Sequence[Mapping[str, Any]],
    provenance: Mapping[str, Any],
    fetch_time_ns: int,
    raw_rows: Sequence[Mapping[str, Any]] | None = None,
    limit: int = 10,
) -> list[BarDisplayRow]:
    row_hash = hash_raw_kline_rows(raw_rows) if raw_rows is not None else ""
    provider_id = str(provenance.get("provider_id") or "moomoo.opend")
    visible = list(bars)[-limit:]
    rows: list[BarDisplayRow] = []
    for bar in visible:
        rows.append(
            BarDisplayRow(
                instrument_id=str(bar.get("instrument_id") or ""),
                bar_start_ns=int(bar.get("event_time") or 0),
                bar_end_ns=int(bar.get("available_time") or 0),
                available_time_ns=int(bar["available_time"]),
                fetch_time_ns=fetch_time_ns,
                provider_id=provider_id,
                source_instance_id=str(bar.get("source_instance_id") or SOURCE_MOOMOO_OPEND_KLINE_1M),
                normalized_event_id=str(bar.get("normalized_event_id") or ""),
                raw_row_hash=row_hash,
            )
        )
    return rows


def build_evidence_receipt(
    *,
    experiment_id: str,
    proof_mode: str,
    experiment: BarOhlcvExperimentResult,
    runtime_git_sha: str,
    raw_provenance_hash: str,
    signal_established_at_ns: int | None = None,
) -> dict[str, Any]:
    first = experiment.first_post_signal_bar
    not_prospective = proof_mode == PROOF_MODE_RETROSPECTIVE
    bar_event_ns = None if first is None else int(first.get("event_time") or 0)
    bar_available_ns = None if first is None else int(first["available_time"])
    bar_id = None if first is None else str(first.get("normalized_event_id") or "")
    first_post_signal_proof = build_first_post_signal_proof(
        signal_time_ns=experiment.signal_time_ns,
        signal_established_at_ns=signal_established_at_ns,
        bar=first,
        observation_time_ns=experiment.observation_time_ns,
    )
    receipt: dict[str, Any] = {
        "receipt_contract_version": RECEIPT_CONTRACT_VERSION,
        "experiment_id": experiment_id,
        "proof_mode": proof_mode,
        "evidence_class": NOT_PROSPECTIVE_EVIDENCE if not_prospective else "PROSPECTIVE_BAR_OHLCV_1M",
        "not_prospective_evidence": not_prospective,
        "instrument_id": experiment.instrument_id,
        "signal_time_ns": experiment.signal_time_ns,
        "signal_established_at_ns": signal_established_at_ns,
        "observation_time_ns": experiment.observation_time_ns,
        "bar_id": bar_id,
        "bar_event_time_ns": bar_event_ns,
        "bar_start_ns": bar_event_ns,
        "bar_end_ns": bar_available_ns,
        "bar_available_time_ns": bar_available_ns,
        "provider_id": str(experiment.bar_provenance.get("provider_id") or "moomoo.opend"),
        "bar_source_id": experiment.bar_source_id,
        "raw_provenance_hash": raw_provenance_hash,
        "bar_provenance": dict(experiment.bar_provenance),
        "first_post_signal_bar": experiment.to_dict().get("first_post_signal_bar"),
        "first_post_signal_proof": first_post_signal_proof,
        "simulator_version": experiment.simulator_version,
        "sim_order_state": experiment.sim_order_state,
        "sim_reason_codes": list(experiment.sim_reason_codes),
        "simulator_decision": experiment.sim_order_state,
        "simulator_output": {
            "classification": experiment.classification,
            "sim_order_state": experiment.sim_order_state,
            "sim_reason_codes": list(experiment.sim_reason_codes),
            "sim_fill": experiment.sim_fill,
        },
        "orders_placed": False,
        "calibrated": False,
        "empirical_active": False,
        "item9_status": "PARTIAL_NOT_CALIBRATED",
        "runtime_git_sha": runtime_git_sha,
        "classification": experiment.classification,
        "comparator_harness_status": experiment.comparator_harness_status,
    }
    return receipt


def run_transport_proof(
    *,
    signal_time_ns: int,
    observation_time_ns: int,
    instrument_id: str,
    source: str,
    collection_root: Path,
    env: Mapping[str, str] | None,
    experiment_id: str | None = None,
    kline_rows: tuple[Mapping[str, Any], ...] | None = None,
    runtime_git_sha: str | None = None,
) -> dict[str, Any]:
    exp_id = experiment_id or f"item9-transport-{uuid.uuid4().hex[:12]}"
    sha = runtime_git_sha or resolve_runtime_git_sha()
    raw_hash = hash_raw_kline_rows(kline_rows or ())
    result = run_bounded_bar_ohlcv_experiment(
        signal_time_ns=signal_time_ns,
        observation_time_ns=observation_time_ns,
        instrument_id=instrument_id,
        source=source,
        collection_root=collection_root,
        env=env,
        kline_rows=kline_rows,
    )
    receipt = build_evidence_receipt(
        experiment_id=exp_id,
        proof_mode=PROOF_MODE_RETROSPECTIVE,
        experiment=result,
        runtime_git_sha=sha,
        raw_provenance_hash=raw_hash,
        signal_established_at_ns=None,
    )
    return {"result": result.to_dict(), "receipt": receipt}


def kline_fetch_diagnostics(loaded: BarLoadResult) -> dict[str, Any]:
    """Last kline-fetch stats for timeout/protocol outcomes (no PIT change)."""

    provenance = loaded.provenance
    return {
        "raw_row_count": provenance.get("raw_row_count"),
        "first_raw_time_key": provenance.get("first_raw_time_key"),
        "last_raw_time_key": provenance.get("last_raw_time_key"),
        "vendor_ret": provenance.get("vendor_ret"),
        "vendor_ret_msg": provenance.get("vendor_ret_msg"),
        "kline_session_date": provenance.get("kline_session_date"),
        "load_reason_code": loaded.reason_code,
    }


def run_prospective_proof(
    *,
    instrument_id: str,
    collection_root: Path,
    env: Mapping[str, str] | None,
    signal_time_ns: int,
    signal_established_at_ns: int,
    observation_time_ns: int,
    experiment_id: str | None = None,
    kline_rows: tuple[Mapping[str, Any], ...] | None = None,
    runtime_git_sha: str | None = None,
) -> dict[str, Any]:
    exp_id = experiment_id or f"item9-prospective-{uuid.uuid4().hex[:12]}"
    sha = runtime_git_sha or resolve_runtime_git_sha()
    raw_hash = hash_raw_kline_rows(kline_rows or ())
    loaded = load_moomoo_opend_kline_bars(
        instrument_id=instrument_id,
        observation_time_ns=observation_time_ns,
        fetched_at_ns=observation_time_ns,
        kline_rows=kline_rows,
    )
    kline_fetch = kline_fetch_diagnostics(loaded)
    if not loaded.ok:
        reason = loaded.reason_code or REASON_PROVIDER_UNAVAILABLE
        return {
            "ok": False,
            "reason_code": reason,
            "receipt": None,
            "kline_fetch": kline_fetch,
        }
    first = first_admissible_post_signal_bar(loaded.bars, signal_time_ns=signal_time_ns)
    if first is None:
        return {
            "ok": False,
            "reason_code": REASON_NO_POST_SIGNAL_BAR,
            "receipt": None,
            "kline_fetch": kline_fetch,
        }
    bar_available = int(first["available_time"])
    gate = validate_prospective_signal_vs_bar(
        signal_time_ns=signal_time_ns,
        signal_established_at_ns=signal_established_at_ns,
        bar_available_time_ns=bar_available,
    )
    if not gate.ok:
        return {
            "ok": False,
            "reason_code": gate.reason_code,
            "receipt": None,
            "kline_fetch": kline_fetch,
        }
    result = run_bounded_bar_ohlcv_experiment(
        signal_time_ns=signal_time_ns,
        observation_time_ns=observation_time_ns,
        instrument_id=instrument_id,
        source="moomoo-opend",
        collection_root=collection_root,
        env=env,
        kline_rows=kline_rows,
    )
    receipt = build_evidence_receipt(
        experiment_id=exp_id,
        proof_mode=PROOF_MODE_PROSPECTIVE,
        experiment=result,
        runtime_git_sha=sha,
        raw_provenance_hash=raw_hash,
        signal_established_at_ns=signal_established_at_ns,
    )
    return {
        "ok": True,
        "reason_code": None,
        "result": result.to_dict(),
        "receipt": receipt,
        "kline_fetch": kline_fetch,
    }


def poll_prospective_proof(
    *,
    instrument_id: str,
    collection_root: Path,
    env: Mapping[str, str] | None,
    signal_time_ns: int,
    signal_established_at_ns: int,
    max_wait_s: float,
    poll_interval_s: float,
    experiment_id: str | None = None,
    runtime_git_sha: str | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
    now_fn: Callable[[], int] | None = None,
    loader: Callable[..., BarLoadResult] | None = None,
) -> dict[str, Any]:
    from ...clock import monotonic_wall_ns

    clock = now_fn or monotonic_wall_ns
    load = loader or load_moomoo_opend_kline_bars
    deadline = time.monotonic() + max_wait_s
    rth_gate = item9_prospective_readiness(now_ns=clock())
    if not rth_gate["rth_active"]:
        return {
            "ok": False,
            "reason_code": REASON_PROSPECTIVE_RTH_REQUIRED,
            "readiness": rth_gate,
            "receipt": None,
        }
    last_kline_fetch: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        observation_ns = clock()
        outcome = run_prospective_proof(
            instrument_id=instrument_id,
            collection_root=collection_root,
            env=env,
            signal_time_ns=signal_time_ns,
            signal_established_at_ns=signal_established_at_ns,
            observation_time_ns=observation_ns,
            kline_rows=None,
            experiment_id=experiment_id,
            runtime_git_sha=runtime_git_sha,
        )
        fetch = outcome.get("kline_fetch")
        if isinstance(fetch, dict):
            last_kline_fetch = fetch
        if outcome.get("ok"):
            outcome["readiness"] = item9_prospective_readiness(now_ns=observation_ns)
            return outcome
        reason = outcome.get("reason_code")
        if reason not in {REASON_NO_POST_SIGNAL_BAR, "EXPERIMENT_CONTRACT_MISMATCH"}:
            outcome["readiness"] = item9_prospective_readiness(now_ns=observation_ns)
            return outcome
        sleep_fn(poll_interval_s)
    return {
        "ok": False,
        "reason_code": REASON_NO_POST_SIGNAL_BAR,
        "readiness": item9_prospective_readiness(now_ns=clock()),
        "receipt": None,
        "kline_fetch": last_kline_fetch,
    }


def persist_receipt(receipt: Mapping[str, Any], *, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    experiment_id = str(receipt.get("experiment_id") or uuid.uuid4().hex)
    path = out_dir / f"{experiment_id}.json"
    path.write_text(json.dumps(dict(receipt), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def load_latest_completed_bars_for_display(
    *,
    instrument_id: str,
    observation_time_ns: int,
    kline_rows: Sequence[Mapping[str, Any]] | None = None,
    max_count: int = 120,
) -> tuple[BarLoadResult, list[BarDisplayRow]]:
    loaded = load_moomoo_opend_kline_bars(
        instrument_id=instrument_id,
        observation_time_ns=observation_time_ns,
        fetched_at_ns=observation_time_ns,
        max_count=max_count,
        kline_rows=kline_rows,
    )
    raw_rows = kline_rows if kline_rows is not None else ()
    display = build_bar_display_rows(
        bars=loaded.bars,
        provenance=loaded.provenance,
        fetch_time_ns=observation_time_ns,
        raw_rows=raw_rows if raw_rows else None,
        limit=10,
    )
    return loaded, display


__all__ = [
    "BarDisplayRow",
    "DEFAULT_RECEIPT_DIR",
    "NOT_PROSPECTIVE_EVIDENCE",
    "PROOF_MODE_PROSPECTIVE",
    "PROOF_MODE_RETROSPECTIVE",
    "ProspectiveSignalValidation",
    "READINESS_RTH_REQUIRED",
    "READINESS_TOOL_READY",
    "RECEIPT_CONTRACT_VERSION",
    "build_bar_display_rows",
    "build_evidence_receipt",
    "build_first_post_signal_proof",
    "hash_raw_kline_rows",
    "imp_package_root",
    "REASON_POLL_REQUIRED",
    "item9_prospective_readiness",
    "kline_fetch_diagnostics",
    "load_latest_completed_bars_for_display",
    "prospective_run_without_poll_outcome",
    "persist_receipt",
    "poll_prospective_proof",
    "resolve_runtime_git_sha",
    "run_prospective_proof",
    "run_transport_proof",
    "validate_prospective_signal_request",
    "validate_prospective_signal_vs_bar",
]
