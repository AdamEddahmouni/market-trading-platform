"""Frozen Item 9 calibration protocol (no fitting).

Executable companion to ``ITEM9_CALIBRATION_PROTOCOL_V1``. Rebuilds a derived
dataset from immutable prospective receipts. Does not calibrate, search
parameters, or mutate source receipts.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence
from zoneinfo import ZoneInfo

from ...execution.simulator import SIMULATOR_VERSION, SOURCE_CAPABILITY
from ...intelligence.fusion.calibration_data import MINIMUM_CALIBRATION_SAMPLES, MINIMUM_CLASS_COUNT
from ...intelligence.outcomes.policy import DIRECTION_UP_DOWN_5M_POLICY
from ...intelligence.paper_forward_bridge.session_policy import is_within_us_equity_rth
from ...intelligence.production.identity import PATH_A_HORIZON_NS, PATH_A_TARGET_KIND
from .bar_ohlcv_prospective_proof import (
    DEFAULT_RECEIPT_DIR,
    EMPTY_RAW_KLINE_HASH,
    PROOF_MODE_PROSPECTIVE,
    hash_raw_kline_rows,
)
from .bar_ohlcv_sources import BAR_CAPABILITY, ONE_MINUTE_NS, SOURCE_MOOMOO_OPEND_KLINE_1M
from .dual_corpus.admission import (
    ITEM9_ADMISSION_ACCEPTED,
    evaluate_item9_prospective_corpus_admission,
)
from .dual_corpus.discovery import (
    ITEM9_DISCOVERY_REFUSED_HISTORICAL_ROOT,
    is_historical_development_storage_path,
    iter_item9_prospective_receipt_paths,
)
from ...intelligence.outcomes.path_a_label_linker import (
    PathALabelLinkageError,
    link_path_a_label_evidence,
    prospective_source_observation_from_item9_receipt,
)
from .thresholds import THRESHOLD_UNSET_BLOCKING, default_unset_threshold_config

PROTOCOL_VERSION = "item9.calibration-protocol/1.0.0"
DATASET_SCHEMA_VERSION = "item9.calibration-dataset/1.0.0"
ITEM9_STATUS_NOT_CALIBRATED = "PARTIAL_NOT_CALIBRATED"
CALIBRATION_STATE = "NOT_CALIBRATED"
INSUFFICIENT_CALIBRATION_EVIDENCE = "INSUFFICIENT_CALIBRATION_EVIDENCE"
PATH_A_LABEL_SOURCE_KIND = "TRADE"
FEATURE_BAR_FIELD = "available_time"
FEATURE_PRICE_FIELD_LONG = "high"
FEATURE_PRICE_FIELD_SHORT = "low"
US_EQUITY_TZ = ZoneInfo("America/New_York")
GOVERNED_RECEIPT_GLOB = "*.json"

EVIDENCE_PROSPECTIVE = "PROSPECTIVE_BAR_OHLCV_1M"
EVIDENCE_PROSPECTIVE_OPEND = "PROSPECTIVE_OPEND_KLINE"
EVIDENCE_RETROSPECTIVE = "NOT_PROSPECTIVE_EVIDENCE"
EVIDENCE_HISTORICAL_FIXTURE = "ADMITTED_HISTORICAL_FIXTURE"
EVIDENCE_UNKNOWN = "UNKNOWN_PROVENANCE"

INCLUSION_INCLUDED = "INCLUDED"
INCLUSION_PATH_PROOF_ONLY = "PATH_PROOF_ONLY"
INCLUSION_EXCLUDED = "EXCLUDED"
INCLUSION_INVALID = "INVALID"
INCLUSION_DUPLICATE = "DUPLICATE"
INCLUSION_AWAITING = "AWAITING_HORIZON"

EXCL_EMPTY_RAW_HASH = "EMPTY_RAW_PROVENANCE_HASH"
EXCL_NOT_PROSPECTIVE = "NOT_PROSPECTIVE_EVIDENCE"
EXCL_CALIBRATED_CLAIM = "RECEIPT_CLAIMS_CALIBRATED"
EXCL_EXTENDED_HOURS = "EXTENDED_HOURS_OR_NON_RTH"
EXCL_PATH_A_BAR_LABEL = "PATH_A_LABEL_REQUIRES_TRADE"
EXCL_SIM_FILL_NOT_MARKET = "SIMULATOR_FILL_NOT_MARKET_TRUTH"
EXCL_MISSING_TERMINAL = "MISSING_PATH_A_TRADE_TERMINAL"
EXCL_INCOMPLETE_BAR = "INCOMPLETE_OR_PARTIAL_BAR"
EXCL_FUTURE_LEAK = "FEATURE_USES_FUTURE_INFORMATION"
EXCL_AMBIGUOUS = "AMBIGUOUS_PROVENANCE"
EXCL_NON_UTF8 = "NON_UTF8_RECEIPT"
EXCL_SCHEMA = "RECEIPT_SCHEMA_INVALID"

SPLIT_DEVELOPMENT = "DEVELOPMENT"
SPLIT_SELECTION = "CALIBRATION_SELECTION"
SPLIT_EVALUATION = "UNTOUCHED_EVALUATION"

# v1 freezes the fill model. Numeric gates stay UNSET/BLOCKING until a later
# justification increment. No parameter grid is legal under this protocol.
FIXED_PARAMETERS = {
    "simulator_version": SIMULATOR_VERSION,
    "source_capability": SOURCE_CAPABILITY,
    "bar_interval": "1_MINUTE",
    "timing_basis": "available_time_at_bar_end",
    "first_post_signal_rule": "available_time > signal_time_ns",
    "fill_price_long": FEATURE_PRICE_FIELD_LONG,
    "fill_price_short": FEATURE_PRICE_FIELD_SHORT,
    "participation_cap": "1/100",
    "limit_price_constraint": False,
    "stop_orders": False,
    "path_a_label_event_kind": PATH_A_LABEL_SOURCE_KIND,
    "path_a_horizon_ns": PATH_A_HORIZON_NS,
    "path_a_target_kind": PATH_A_TARGET_KIND,
    "path_a_terminal_window_ns": DIRECTION_UP_DOWN_5M_POLICY.target_window_tolerance_ns,
}

FORBIDDEN_SEARCH_DEGREES = (
    "fill_price_field",
    "bar_available_time_semantics",
    "partial_bar_admission",
    "composing_path_a_labels_from_bar_close",
    "score_weights",
    "logistic_or_isotonic_fit",
    "post_hoc_exclusion_after_seeing_labels",
)

CALIBRATABLE_LATER = (
    "fill_no_fill_disagreement_rate_max",
    "fill_price_slippage_error_max",
    "timing_error_max_ns",
    "position_pnl_reconciliation_tolerance",
    "unexplained_divergence_rate_max",
)

MINIMUM_DISTINCT_RTH_DATES = 3
MINIMUM_EVALUATION_ROWS = MINIMUM_CLASS_COUNT
SPLIT_FRACTIONS = (0.6, 0.2, 0.2)


def empty_raw_hash() -> str:
    return EMPTY_RAW_KLINE_HASH


def is_empty_raw_provenance_hash(value: str | None) -> bool:
    text = str(value or "").strip().lower()
    return text == EMPTY_RAW_KLINE_HASH or text == hash_raw_kline_rows(())


def feature_cutoff_ns(*, signal_time_ns: int, first_bar_available_ns: int) -> int:
    """Information cutoff for features: first completed bar after the signal."""

    return int(first_bar_available_ns)


def overlapping_signal_bar_is_feature_eligible(
    *,
    signal_time_ns: int,
    bar_start_ns: int,
    bar_available_ns: int,
) -> bool:
    """PIT: a bar that starts before the signal may be the feature bar if it completes after."""

    return bar_start_ns <= signal_time_ns < bar_available_ns and bar_available_ns > signal_time_ns


def path_a_target_time_ns(signal_time_ns: int) -> int:
    return int(signal_time_ns) + PATH_A_HORIZON_NS


def path_a_terminal_window(signal_time_ns: int) -> tuple[int, int]:
    target = path_a_target_time_ns(signal_time_ns)
    start, end = DIRECTION_UP_DOWN_5M_POLICY.target_window(target_time_ns=target)
    return start, end


def bar_may_compose_path_a_label() -> bool:
    """True only if BUILD 15 Path A settlement lists BAR_OHLCV_1M. Currently false."""

    return BAR_CAPABILITY in DIRECTION_UP_DOWN_5M_POLICY.observation_kinds


def reject_incomplete_bar(*, bar_end_ns: int, fetched_at_ns: int) -> bool:
    return int(bar_end_ns) > int(fetched_at_ns)


def session_date_et(ts_ns: int) -> str:
    return datetime.fromtimestamp(int(ts_ns) / 1_000_000_000, tz=US_EQUITY_TZ).strftime("%Y-%m-%d")


def _receipt_evidence_class(receipt: Mapping[str, Any]) -> str:
    proof_mode = str(receipt.get("proof_mode") or "")
    declared = str(receipt.get("evidence_class") or "")
    nested = str((receipt.get("bar_provenance") or {}).get("evidence_class") or "")
    if proof_mode != PROOF_MODE_PROSPECTIVE or receipt.get("not_prospective_evidence"):
        return EVIDENCE_RETROSPECTIVE
    if declared == EVIDENCE_PROSPECTIVE and nested == EVIDENCE_PROSPECTIVE_OPEND:
        return EVIDENCE_PROSPECTIVE
    if nested == EVIDENCE_HISTORICAL_FIXTURE or declared == EVIDENCE_HISTORICAL_FIXTURE:
        return EVIDENCE_HISTORICAL_FIXTURE
    if declared and nested and declared != nested and nested != EVIDENCE_PROSPECTIVE_OPEND:
        return EVIDENCE_UNKNOWN
    if declared:
        return declared
    return EVIDENCE_UNKNOWN


@dataclass(frozen=True, slots=True)
class Item9ObservationClassification:
    observation_id: str
    evidence_class: str
    inclusion_state: str
    exclusion_reason: str | None
    path_a_label_state: str
    simulator_fill_is_market_truth: bool
    labelable_path_a_now: bool
    corpus_admissible: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "observation_id": self.observation_id,
            "evidence_class": self.evidence_class,
            "inclusion_state": self.inclusion_state,
            "exclusion_reason": self.exclusion_reason,
            "path_a_label_state": self.path_a_label_state,
            "simulator_fill_is_market_truth": self.simulator_fill_is_market_truth,
            "labelable_path_a_now": self.labelable_path_a_now,
            "corpus_admissible": self.corpus_admissible,
        }


def classify_item9_receipt(receipt: Mapping[str, Any]) -> Item9ObservationClassification:
    observation_id = str(receipt.get("experiment_id") or "").strip()
    evidence = _receipt_evidence_class(receipt)
    first = receipt.get("first_post_signal_bar") or {}
    signal_ns = int(receipt.get("signal_time_ns") or 0)
    bar_available = int(receipt.get("bar_available_time_ns") or first.get("available_time_ns") or 0)
    bar_start = int(receipt.get("bar_start_ns") or first.get("event_time_ns") or 0)
    fetched = int((receipt.get("bar_provenance") or {}).get("fetched_at_ns") or receipt.get("observation_time_ns") or 0)

    if not observation_id:
        return Item9ObservationClassification(
            observation_id="",
            evidence_class=evidence,
            inclusion_state=INCLUSION_INVALID,
            exclusion_reason=EXCL_SCHEMA,
            path_a_label_state=EXCL_SCHEMA,
            simulator_fill_is_market_truth=False,
            labelable_path_a_now=False,
            corpus_admissible=False,
        )
    if receipt.get("calibrated") or receipt.get("empirical_active"):
        return Item9ObservationClassification(
            observation_id=observation_id,
            evidence_class=evidence,
            inclusion_state=INCLUSION_INVALID,
            exclusion_reason=EXCL_CALIBRATED_CLAIM,
            path_a_label_state=EXCL_CALIBRATED_CLAIM,
            simulator_fill_is_market_truth=False,
            labelable_path_a_now=False,
            corpus_admissible=False,
        )
    if evidence in {EVIDENCE_RETROSPECTIVE, EVIDENCE_HISTORICAL_FIXTURE}:
        return Item9ObservationClassification(
            observation_id=observation_id,
            evidence_class=evidence,
            inclusion_state=INCLUSION_EXCLUDED,
            exclusion_reason=EXCL_NOT_PROSPECTIVE,
            path_a_label_state=EXCL_NOT_PROSPECTIVE,
            simulator_fill_is_market_truth=False,
            labelable_path_a_now=False,
            corpus_admissible=False,
        )
    if evidence == EVIDENCE_UNKNOWN:
        return Item9ObservationClassification(
            observation_id=observation_id,
            evidence_class=evidence,
            inclusion_state=INCLUSION_EXCLUDED,
            exclusion_reason=EXCL_AMBIGUOUS,
            path_a_label_state=EXCL_AMBIGUOUS,
            simulator_fill_is_market_truth=False,
            labelable_path_a_now=False,
            corpus_admissible=False,
        )
    if fetched and bar_available and reject_incomplete_bar(bar_end_ns=bar_available, fetched_at_ns=fetched):
        return Item9ObservationClassification(
            observation_id=observation_id,
            evidence_class=evidence,
            inclusion_state=INCLUSION_INVALID,
            exclusion_reason=EXCL_INCOMPLETE_BAR,
            path_a_label_state=EXCL_INCOMPLETE_BAR,
            simulator_fill_is_market_truth=False,
            labelable_path_a_now=False,
            corpus_admissible=False,
        )
    if bar_available and signal_ns and bar_available <= signal_ns:
        return Item9ObservationClassification(
            observation_id=observation_id,
            evidence_class=evidence,
            inclusion_state=INCLUSION_INVALID,
            exclusion_reason=EXCL_FUTURE_LEAK,
            path_a_label_state=EXCL_FUTURE_LEAK,
            simulator_fill_is_market_truth=False,
            labelable_path_a_now=False,
            corpus_admissible=False,
        )
    if signal_ns and not is_within_us_equity_rth(signal_ns):
        return Item9ObservationClassification(
            observation_id=observation_id,
            evidence_class=evidence,
            inclusion_state=INCLUSION_EXCLUDED,
            exclusion_reason=EXCL_EXTENDED_HOURS,
            path_a_label_state=EXCL_EXTENDED_HOURS,
            simulator_fill_is_market_truth=False,
            labelable_path_a_now=False,
            corpus_admissible=False,
        )

    path_a_state = EXCL_PATH_A_BAR_LABEL
    if bar_may_compose_path_a_label():
        path_a_state = EXCL_MISSING_TERMINAL
    else:
        path_a_state = EXCL_PATH_A_BAR_LABEL

    empty_hash = is_empty_raw_provenance_hash(str(receipt.get("raw_provenance_hash") or ""))
    if empty_hash:
        return Item9ObservationClassification(
            observation_id=observation_id,
            evidence_class=evidence,
            inclusion_state=INCLUSION_PATH_PROOF_ONLY,
            exclusion_reason=EXCL_EMPTY_RAW_HASH,
            path_a_label_state=path_a_state,
            simulator_fill_is_market_truth=False,
            labelable_path_a_now=False,
            corpus_admissible=False,
        )

    _ = overlapping_signal_bar_is_feature_eligible(
        signal_time_ns=signal_ns,
        bar_start_ns=bar_start,
        bar_available_ns=bar_available,
    )
    admission = evaluate_item9_prospective_corpus_admission(payload=receipt)
    if admission.get("disposition") != ITEM9_ADMISSION_ACCEPTED:
        return Item9ObservationClassification(
            observation_id=observation_id,
            evidence_class=evidence,
            inclusion_state=INCLUSION_EXCLUDED,
            exclusion_reason=str(admission.get("reason_code") or EXCL_AMBIGUOUS),
            path_a_label_state=path_a_state,
            simulator_fill_is_market_truth=False,
            labelable_path_a_now=False,
            corpus_admissible=False,
        )
    return Item9ObservationClassification(
        observation_id=observation_id,
        evidence_class=evidence,
        inclusion_state=INCLUSION_INCLUDED,
        exclusion_reason=None,
        path_a_label_state=path_a_state,
        simulator_fill_is_market_truth=False,
        labelable_path_a_now=False,
        corpus_admissible=True,
    )


def build_dataset_row(
    receipt: Mapping[str, Any],
    *,
    protocol_version: str = PROTOCOL_VERSION,
    classification: Item9ObservationClassification | None = None,
    label_evidences: Sequence[Mapping[str, Any]] | None = None,
    prospective_p0: Mapping[str, Any] | None = None,
    linkage_evaluation_time_ns: int | None = None,
) -> dict[str, Any]:
    classified = classification or classify_item9_receipt(receipt)
    first = receipt.get("first_post_signal_bar") or {}
    signal_ns = int(receipt.get("signal_time_ns") or 0)
    bar_available = int(receipt.get("bar_available_time_ns") or first.get("available_time_ns") or 0)
    target_ns = path_a_target_time_ns(signal_ns) if signal_ns else None
    window = path_a_terminal_window(signal_ns) if signal_ns else (None, None)
    path_a_label_evidence_ids: list[str] = []
    path_a_label_value: str | None = None
    path_a_label_availability_ns: int | None = None
    if label_evidences:
        if prospective_p0 is None:
            raise PathALabelLinkageError(
                "LABEL_INVALID_PROVENANCE",
                details={"field": "prospective_p0"},
            )
        source = prospective_source_observation_from_item9_receipt(
            receipt,
            p0=prospective_p0,
        )
        linkage = link_path_a_label_evidence(
            source,
            label_evidences,
            evaluation_time_ns=linkage_evaluation_time_ns,
        )
        path_a_label_evidence_ids = list(linkage.path_a_label_evidence_ids)
        path_a_label_value = linkage.path_a_label_value
        path_a_label_availability_ns = linkage.path_a_label_availability_ns
    return {
        "schema_version": DATASET_SCHEMA_VERSION,
        "protocol_version": protocol_version,
        "observation_id": classified.observation_id,
        "instrument_id": receipt.get("instrument_id"),
        "signal_timestamp_ns": receipt.get("signal_time_ns"),
        "signal_established_timestamp_ns": receipt.get("signal_established_at_ns"),
        "feature_cutoff_ns": feature_cutoff_ns(
            signal_time_ns=signal_ns,
            first_bar_available_ns=bar_available,
        )
        if bar_available
        else None,
        "feature_ref": {
            "bar_id": receipt.get("bar_id"),
            "bar_source_id": receipt.get("bar_source_id") or SOURCE_MOOMOO_OPEND_KLINE_1M,
            "normalized_event_id": first.get("normalized_event_id"),
            "bar_payload_ref": first.get("bar_payload"),
        },
        "feature_provenance": receipt.get("bar_provenance"),
        "provider_id": receipt.get("provider_id"),
        "source": receipt.get("bar_source_id"),
        "evidence_class": classified.evidence_class,
        "label_horizon_ns": PATH_A_HORIZON_NS,
        "path_a_target_kind": PATH_A_TARGET_KIND,
        "path_a_label_value": path_a_label_value,
        "path_a_label_state": classified.path_a_label_state,
        "path_a_label_evidence_ids": path_a_label_evidence_ids,
        "path_a_label_availability_ns": path_a_label_availability_ns,
        "path_a_target_time_ns": target_ns,
        "path_a_target_window_start_ns": window[0],
        "path_a_target_window_end_ns": window[1],
        "simulator_fill_state": receipt.get("sim_order_state"),
        "simulator_fill_is_market_truth": False,
        "inclusion_state": classified.inclusion_state,
        "exclusion_reason": classified.exclusion_reason,
        "runtime_git_sha": receipt.get("runtime_git_sha"),
        "raw_provenance_hash": receipt.get("raw_provenance_hash"),
        "receipt_contract_version": receipt.get("receipt_contract_version"),
        "item9_status": receipt.get("item9_status") or ITEM9_STATUS_NOT_CALIBRATED,
        "calibrated": False,
        "empirical_active": False,
        "orders_placed": False,
    }


def governed_receipt_paths(receipt_dir: Path) -> tuple[Path, ...]:
    """Scan only lawful Item 9 prospective receipt roots (never historical development)."""

    if not receipt_dir.is_dir():
        return ()
    if is_historical_development_storage_path(receipt_dir):
        return ()
    return iter_item9_prospective_receipt_paths(receipt_dir)


def load_governed_receipt(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None, EXCL_NON_UTF8
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None, EXCL_SCHEMA
    if not isinstance(payload, dict):
        return None, EXCL_SCHEMA
    return payload, None


def audit_receipt_directory(receipt_dir: Path) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    seen: dict[str, str] = {}
    counts: Counter[str] = Counter()
    discovery_refusal: str | None = None
    if is_historical_development_storage_path(receipt_dir):
        discovery_refusal = ITEM9_DISCOVERY_REFUSED_HISTORICAL_ROOT
    scan_paths = governed_receipt_paths(receipt_dir)
    for path in scan_paths:
        payload, load_error = load_governed_receipt(path)
        if payload is None:
            counts["invalid"] += 1
            rows.append(
                {
                    "path": str(path),
                    "inclusion_state": INCLUSION_INVALID,
                    "exclusion_reason": load_error,
                    "evidence_class": EVIDENCE_UNKNOWN,
                    "corpus_admissible": False,
                    "labelable_path_a_now": False,
                }
            )
            continue
        classified = classify_item9_receipt(payload)
        obs_id = classified.observation_id
        if obs_id and obs_id in seen:
            classified = Item9ObservationClassification(
                observation_id=obs_id,
                evidence_class=classified.evidence_class,
                inclusion_state=INCLUSION_DUPLICATE,
                exclusion_reason="DUPLICATE_OBSERVATION_ID",
                path_a_label_state=classified.path_a_label_state,
                simulator_fill_is_market_truth=False,
                labelable_path_a_now=False,
                corpus_admissible=False,
            )
        elif obs_id:
            seen[obs_id] = str(path)
        if classified.evidence_class == EVIDENCE_PROSPECTIVE:
            counts["prospective_observations"] += 1
        elif classified.evidence_class in {EVIDENCE_RETROSPECTIVE, EVIDENCE_HISTORICAL_FIXTURE}:
            counts["historical_or_replay"] += 1
        elif classified.evidence_class == EVIDENCE_UNKNOWN:
            counts["unknown_provenance"] += 1
        if classified.labelable_path_a_now:
            counts["labelable_path_a_now"] += 1
        if classified.path_a_label_state in {EXCL_MISSING_TERMINAL, EXCL_PATH_A_BAR_LABEL}:
            counts["awaiting_or_missing_path_a_terminal"] += 1
        if classified.inclusion_state == INCLUSION_INVALID:
            counts["invalid"] += 1
        if classified.inclusion_state == INCLUSION_DUPLICATE:
            counts["duplicate"] += 1
        if classified.inclusion_state == INCLUSION_EXCLUDED:
            counts["excluded"] += 1
        if classified.inclusion_state == INCLUSION_PATH_PROOF_ONLY:
            counts["path_proof_only"] += 1
        if classified.corpus_admissible:
            counts["corpus_admissible"] += 1
        rows.append({"path": str(path), **classified.to_dict()})
    result: dict[str, Any] = {
        "protocol_version": PROTOCOL_VERSION,
        "receipt_dir": str(receipt_dir),
        "calibration_state": CALIBRATION_STATE,
        "item9_status": ITEM9_STATUS_NOT_CALIBRATED,
        "counts": dict(counts),
        "observations": rows,
        "path_a_bars_are_approved_label_source": False,
        "bar_may_compose_path_a_label": False,
        "empty_raw_kline_hash": EMPTY_RAW_KLINE_HASH,
    }
    if discovery_refusal is not None:
        result["discovery_refusal"] = discovery_refusal
    return result


def chronological_split(rows: Sequence[Mapping[str, Any]]) -> dict[str, tuple[str, ...]]:
    """60/20/20 by signal time. Never shuffle. Evaluation is untouched."""

    ordered = sorted(
        (row for row in rows if row.get("corpus_admissible") or row.get("inclusion_state") == INCLUSION_INCLUDED),
        key=lambda row: (
            int(row.get("signal_timestamp_ns") or row.get("signal_time_ns") or 0),
            str(row.get("observation_id") or ""),
        ),
    )
    n = len(ordered)
    if n == 0:
        return {SPLIT_DEVELOPMENT: (), SPLIT_SELECTION: (), SPLIT_EVALUATION: ()}
    n_dev = max(int(n * SPLIT_FRACTIONS[0]), 1 if n >= 1 else 0)
    n_sel = max(int(n * SPLIT_FRACTIONS[1]), 1 if n >= 3 else 0)
    if n_dev + n_sel >= n:
        n_sel = max(n - n_dev - 1, 0)
    n_eval = n - n_dev - n_sel
    ids = [str(row.get("observation_id") or "") for row in ordered]
    return {
        SPLIT_DEVELOPMENT: tuple(ids[:n_dev]),
        SPLIT_SELECTION: tuple(ids[n_dev : n_dev + n_sel]),
        SPLIT_EVALUATION: tuple(ids[n_dev + n_sel : n_dev + n_sel + n_eval]),
    }


ITEM9_CORPUS_STATUS_ARTIFACT_KIND = "item9_corpus_status_v1"
ITEM9_CORPUS_VALIDATION_ARTIFACT_KIND = "item9_corpus_validation_v1"


def _included_dataset_rows_for_gate(receipt_dir: Path) -> list[dict[str, Any]]:
    """Unique corpus-admissible rows for sample-gate evaluation (read-only)."""

    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    for path in governed_receipt_paths(receipt_dir):
        payload, _load_error = load_governed_receipt(path)
        if payload is None:
            continue
        classified = classify_item9_receipt(payload)
        obs_id = classified.observation_id
        if obs_id and obs_id in seen:
            continue
        if obs_id:
            seen.add(obs_id)
        if classified.corpus_admissible or classified.inclusion_state == INCLUSION_INCLUDED:
            rows.append(build_dataset_row(payload, classification=classified))
    return rows


def build_item9_corpus_status_report(receipt_dir: Path) -> dict[str, Any]:
    """Read-only governed receipt scan; never fits or mutates receipts."""

    audit = audit_receipt_directory(receipt_dir)
    counts = audit["counts"]
    included_rows = _included_dataset_rows_for_gate(receipt_dir)
    gate = evaluate_sample_gate(included_rows)
    dates = sorted(
        {
            session_date_et(int(row["signal_timestamp_ns"]))
            for row in included_rows
            if row.get("signal_timestamp_ns")
        }
    )
    eval_size = len(gate["split"][SPLIT_EVALUATION])
    return {
        "artifact_kind": ITEM9_CORPUS_STATUS_ARTIFACT_KIND,
        "protocol_version": PROTOCOL_VERSION,
        "receipt_dir": str(receipt_dir.resolve()),
        "calibration_state": CALIBRATION_STATE,
        "item9_status": ITEM9_STATUS_NOT_CALIBRATED,
        "calibrated": False,
        "empirical_active": False,
        "fitting_allowed": False,
        "counts": {
            "corpus_admissible": int(counts.get("corpus_admissible", 0)),
            "path_proof_only": int(counts.get("path_proof_only", 0)),
            "invalid": int(counts.get("invalid", 0)),
            "duplicate": int(counts.get("duplicate", 0)),
            "excluded": int(counts.get("excluded", 0)),
        },
        "session_dates_rth": dates,
        "evaluation_split_size": eval_size,
        "sample_gate": gate,
        "sample_gate_progress": {
            "admissible": f"{gate['included_count']}/{gate['minimum_included']}",
            "distinct_rth_dates": f"{gate['distinct_rth_dates']}/{gate['minimum_distinct_rth_dates']}",
            "evaluation_rows": f"{gate['evaluation_count']}/{gate['minimum_evaluation_rows']}",
        },
    }


def validate_item9_governed_receipt_dir(receipt_dir: Path) -> dict[str, Any]:
    """Classifier/validator pass over governed receipts only (read-only)."""

    audit = audit_receipt_directory(receipt_dir)
    counts = audit["counts"]
    invalid = int(counts.get("invalid", 0))
    calibrated_claims = sum(
        1
        for obs in audit["observations"]
        if obs.get("exclusion_reason") == EXCL_CALIBRATED_CLAIM
    )
    blockers: list[str] = []
    if invalid:
        blockers.append(f"INVALID_RECEIPTS:{invalid}")
    if calibrated_claims:
        blockers.append(f"CALIBRATED_CLAIM_IN_RECEIPT:{calibrated_claims}")
    return {
        "artifact_kind": ITEM9_CORPUS_VALIDATION_ARTIFACT_KIND,
        "protocol_version": PROTOCOL_VERSION,
        "receipt_dir": str(receipt_dir.resolve()),
        "verdict": "VALID" if not blockers else "INVALID",
        "blockers": blockers,
        "counts": dict(counts),
        "calibration_state": CALIBRATION_STATE,
        "item9_status": ITEM9_STATUS_NOT_CALIBRATED,
        "calibrated": False,
        "empirical_active": False,
        "fitting_allowed": False,
    }


def evaluate_sample_gate(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    included = [
        row
        for row in rows
        if row.get("corpus_admissible") or row.get("inclusion_state") == INCLUSION_INCLUDED
    ]
    dates = {session_date_et(int(row["signal_timestamp_ns"])) for row in included if row.get("signal_timestamp_ns")}
    split = chronological_split(included)
    ok = (
        len(included) >= MINIMUM_CALIBRATION_SAMPLES
        and len(dates) >= MINIMUM_DISTINCT_RTH_DATES
        and len(split[SPLIT_EVALUATION]) >= MINIMUM_EVALUATION_ROWS
    )
    thresholds = default_unset_threshold_config(campaign_slug="item9-bar-ohlcv")
    return {
        "status": "SAMPLE_GATE_MET" if ok else INSUFFICIENT_CALIBRATION_EVIDENCE,
        "included_count": len(included),
        "minimum_included": MINIMUM_CALIBRATION_SAMPLES,
        "distinct_rth_dates": len(dates),
        "minimum_distinct_rth_dates": MINIMUM_DISTINCT_RTH_DATES,
        "evaluation_count": len(split[SPLIT_EVALUATION]),
        "minimum_evaluation_rows": MINIMUM_EVALUATION_ROWS,
        "thresholds_status": THRESHOLD_UNSET_BLOCKING,
        "execution_claims_blocked": thresholds.execution_claims_blocked,
        "fitting_allowed": False,
        "calibrated": False,
        "split": {key: list(value) for key, value in split.items()},
        "justification": (
            "MINIMUM_CALIBRATION_SAMPLES and MINIMUM_CLASS_COUNT are the existing BUILD 14 "
            "calibration floors; three distinct RTH dates are required so the chronological "
            "60/20/20 split is not a single-session artifact."
        ),
    }


def protocol_freeze_record() -> dict[str, Any]:
    return {
        "protocol_version": PROTOCOL_VERSION,
        "dataset_schema_version": DATASET_SCHEMA_VERSION,
        "item9_status": ITEM9_STATUS_NOT_CALIBRATED,
        "calibration_state": CALIBRATION_STATE,
        "unit_of_observation": "one Mode B prospective BAR_OHLCV_1M receipt (experiment_id)",
        "feature_timestamp": "first completed 1m bar with available_time > signal_time",
        "information_cutoff": "feature bar available_time (bar end)",
        "path_a_horizon_ns": PATH_A_HORIZON_NS,
        "path_a_label_event_kind": PATH_A_LABEL_SOURCE_KIND,
        "path_a_bars_approved_label_source": False,
        "one_minute_ns": ONE_MINUTE_NS,
        "fixed_parameters": dict(FIXED_PARAMETERS),
        "forbidden_search_degrees": list(FORBIDDEN_SEARCH_DEGREES),
        "calibratable_later_numeric_gates": list(CALIBRATABLE_LATER),
        "search_complexity_max": 0,
        "comparator_required_for_corpus": False,
        "comparator_required_for_execution_claim": True,
        "ftep_not_implied": True,
        "production_forecast_not_implied": True,
        "governed_receipt_dir": str(DEFAULT_RECEIPT_DIR),
        "scan_local_jsonl": False,
        "empty_raw_kline_hash": EMPTY_RAW_KLINE_HASH,
    }


__all__ = [
    "CALIBRATION_STATE",
    "DATASET_SCHEMA_VERSION",
    "EMPTY_RAW_KLINE_HASH",
    "INSUFFICIENT_CALIBRATION_EVIDENCE",
    "ITEM9_STATUS_NOT_CALIBRATED",
    "PROTOCOL_VERSION",
    "ITEM9_CORPUS_STATUS_ARTIFACT_KIND",
    "ITEM9_CORPUS_VALIDATION_ARTIFACT_KIND",
    "audit_receipt_directory",
    "bar_may_compose_path_a_label",
    "build_dataset_row",
    "build_item9_corpus_status_report",
    "chronological_split",
    "classify_item9_receipt",
    "evaluate_sample_gate",
    "feature_cutoff_ns",
    "governed_receipt_paths",
    "is_empty_raw_provenance_hash",
    "overlapping_signal_bar_is_feature_eligible",
    "path_a_target_time_ns",
    "path_a_terminal_window",
    "protocol_freeze_record",
    "reject_incomplete_bar",
    "validate_item9_governed_receipt_dir",
]
