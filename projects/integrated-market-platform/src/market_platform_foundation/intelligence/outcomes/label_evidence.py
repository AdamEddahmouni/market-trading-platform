"""Post-horizon historical label evidence (IMP-DUAL-CORPUS-01 Lane C).

Append-only label artifacts bound to immutable prospective source observations.
Path A semantics: TRADE-only P0/terminal, 5m horizon, BUILD 15 window policy.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from ...canonical import canonical_bytes, sha256_bytes
from ...paper.calibration.dual_corpus.evidence_authority import (
    CORPUS_EVIDENCE_AUTHORITY_POST_HORIZON_HISTORICAL_LABEL_EVIDENCE,
    CORPUS_EVIDENCE_AUTHORITY_PROSPECTIVE_FEATURE_EVIDENCE,
)
from ..contracts.common import Direction
from .p6_compat import p6_classify_return, p6_realized_return
from .policy import DIRECTION_UP_DOWN_5M_POLICY, OutcomeSettlementPolicy

POST_HORIZON_LABEL_EVIDENCE_KIND = "post_horizon_label_evidence_v1"
POST_HORIZON_LABEL_SCHEMA_VERSION = "dual_corpus.post-horizon-label-evidence/1.0.0"
LABEL_COMPUTATION_VERSION = "path_a_direction_up_down_5m_v1"
SOURCE_OBSERVATION_HASH_VERSION = "post-horizon-source-observation-sha256-v1"
LABEL_EVIDENCE_ID_VERSION = "post-horizon-label-evidence-sha256-v1"

RETRIEVAL_BEFORE_TERMINAL_WINDOW_END = "RETRIEVAL_BEFORE_TERMINAL_WINDOW_END"
BAR_OHLCV_REFUSED_FOR_PATH_A_LABEL = "BAR_OHLCV_REFUSED_FOR_PATH_A_LABEL"
NO_ELIGIBLE_TRADE = "NO_ELIGIBLE_TRADE"
INSTRUMENT_OR_HASH_MISMATCH = "INSTRUMENT_OR_HASH_MISMATCH"
MALFORMED_PROVIDER_TRADE_RECORD = "MALFORMED_PROVIDER_TRADE_RECORD"
HISTORICAL_EVENT_NOT_PROSPECTIVE = "HISTORICAL_EVENT_NOT_PROSPECTIVE"
IMPLICIT_LABEL_COLUMN_MERGE_REFUSED = "IMPLICIT_LABEL_COLUMN_MERGE_REFUSED"

_PATH_A_POLICY = DIRECTION_UP_DOWN_5M_POLICY
_FORBIDDEN_CAPABILITY_IDS = frozenset(
    {"BAR_OHLCV_1M", "BAR_OHLCV", "OHLCV", "HISTORICAL_BAR"}
)
_FORBIDDEN_OBSERVATION_KINDS = frozenset({"BAR_OHLCV", "OHLCV", "QUOTE"})

_SOURCE_HASH_EXCLUDED_KEYS = frozenset(
    {
        "source_observation_hash",
        "label_evidence_ids",
        "linkage",
        "attached_label_evidence_id",
    }
)


class LabelEvidenceError(ValueError):
    """Fail-closed label evidence contract violation."""

    def __init__(self, reason_code: str, *, details: Mapping[str, Any] | None = None) -> None:
        self.reason_code = reason_code
        self.details = dict(details or {})
        super().__init__(reason_code)


@dataclass(frozen=True, slots=True)
class LabelAttachResult:
    source_observation: dict[str, Any]
    label_evidence: dict[str, Any]
    linkage: dict[str, Any]
    source_hash_before: str
    source_hash_after: str


def derive_source_observation_hash(observation: Mapping[str, Any]) -> str:
    body = {
        key: observation[key]
        for key in sorted(observation.keys())
        if key not in _SOURCE_HASH_EXCLUDED_KEYS
    }
    payload = {
        "identity_version": SOURCE_OBSERVATION_HASH_VERSION,
        "body": body,
    }
    return sha256_bytes(canonical_bytes(payload))


def derive_label_evidence_id(body: Mapping[str, Any]) -> str:
    payload = {
        "identity_version": LABEL_EVIDENCE_ID_VERSION,
        "body": {key: body[key] for key in sorted(body.keys()) if key != "label_evidence_id"},
    }
    return f"PHLBL-{sha256_bytes(canonical_bytes(payload))}"


def assert_retrieval_not_before_terminal_window(
    *,
    request_time_ns: int,
    terminal_window_end_ns: int,
) -> None:
    if request_time_ns < terminal_window_end_ns:
        raise LabelEvidenceError(
            RETRIEVAL_BEFORE_TERMINAL_WINDOW_END,
            details={
                "request_time_ns": request_time_ns,
                "terminal_window_end_ns": terminal_window_end_ns,
            },
        )


def _terminal_sort_key(trade: Mapping[str, Any]) -> tuple[int, int, str]:
    return (
        int(trade["event_time_ns"]),
        int(trade.get("available_time_ns") or trade["event_time_ns"]),
        str(trade.get("trade_id") or trade.get("event_id") or ""),
    )


def select_terminal_trade(
    candidates: Sequence[Mapping[str, Any]],
    *,
    instrument_id: str,
    target_window_start_ns: int,
    target_window_end_ns: int,
    availability_cutoff_ns: int,
    policy: OutcomeSettlementPolicy = _PATH_A_POLICY,
) -> tuple[Mapping[str, Any] | None, tuple[Mapping[str, Any], ...]]:
    allowed_kinds = {kind.upper() for kind in policy.observation_kinds}
    filtered: list[Mapping[str, Any]] = []
    for row in candidates:
        if str(row.get("instrument_id") or "").upper() != instrument_id.upper():
            continue
        kind = str(row.get("observation_kind") or row.get("capability_id") or "").upper()
        if kind in _FORBIDDEN_OBSERVATION_KINDS or kind in _FORBIDDEN_CAPABILITY_IDS:
            raise LabelEvidenceError(BAR_OHLCV_REFUSED_FOR_PATH_A_LABEL, details={"kind": kind})
        if kind and kind not in allowed_kinds:
            continue
        event_time_ns = row.get("event_time_ns")
        if event_time_ns is None:
            raise LabelEvidenceError(MALFORMED_PROVIDER_TRADE_RECORD, details={"row": dict(row)})
        event_time_ns = int(event_time_ns)
        available_time_ns = int(row.get("available_time_ns") or event_time_ns)
        if not (target_window_start_ns <= event_time_ns <= target_window_end_ns):
            continue
        if available_time_ns > availability_cutoff_ns:
            continue
        price = row.get("price")
        try:
            price_f = float(price)
        except (TypeError, ValueError):
            raise LabelEvidenceError(MALFORMED_PROVIDER_TRADE_RECORD, details={"row": dict(row)})
        if price_f <= 0.0:
            raise LabelEvidenceError(MALFORMED_PROVIDER_TRADE_RECORD, details={"row": dict(row)})
        filtered.append(row)
    filtered.sort(key=_terminal_sort_key)
    if not filtered:
        return None, tuple(filtered)
    return filtered[0], tuple(filtered)


def compute_path_a_direction_label(
    *,
    p0_price: float,
    terminal_price: float,
) -> tuple[str | None, float, str | None]:
    realized_return = p6_realized_return(p0=p0_price, p_target=terminal_price)
    label_class = p6_classify_return(realized_return)
    if label_class == "ZERO_RETURN":
        return None, realized_return, "ZERO_RETURN"
    direction = Direction.LONG if label_class == "UP" else Direction.SHORT
    return direction.value, realized_return, None


def build_post_horizon_label_evidence(
    *,
    source_observation: Mapping[str, Any],
    source_observation_hash: str,
    signal_time_ns: int,
    feature_cutoff_ns: int,
    source_code_sha: str,
    p0: Mapping[str, Any],
    horizon_policy_version: str,
    target_time_ns: int,
    terminal_window_start_ns: int,
    terminal_window_end_ns: int,
    request_time_ns: int,
    actual_retrieval_time_ns: int,
    provider_id: str,
    capability_id: str,
    retrieval_params: Mapping[str, Any],
    raw_trade_ref: str,
    raw_trade_payload_sha256: str,
    returned_trade_count: int,
    terminal_candidates: Sequence[Mapping[str, Any]],
    selected_terminal_trade: Mapping[str, Any] | None,
    label_computation_version: str = LABEL_COMPUTATION_VERSION,
    labeler_code_sha: str,
    refusal_reason: str | None = None,
    direction_label: str | None = None,
    realized_return: float | None = None,
    label_availability_time_ns: int | None = None,
    availability_semantics: str = "post_terminal_window_retrieval",
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "artifact_kind": POST_HORIZON_LABEL_EVIDENCE_KIND,
        "schema_version": POST_HORIZON_LABEL_SCHEMA_VERSION,
        "corpus_evidence_authority": CORPUS_EVIDENCE_AUTHORITY_POST_HORIZON_HISTORICAL_LABEL_EVIDENCE,
        "source_observation_id": str(source_observation["source_observation_id"]),
        "source_observation_hash": source_observation_hash,
        "source_evidence_class": str(
            source_observation.get("source_evidence_class")
            or CORPUS_EVIDENCE_AUTHORITY_PROSPECTIVE_FEATURE_EVIDENCE
        ),
        "signal_time_ns": int(signal_time_ns),
        "feature_cutoff_ns": int(feature_cutoff_ns),
        "source_code_sha": str(source_code_sha),
        "p0": dict(p0),
        "horizon_policy_version": str(horizon_policy_version),
        "target_time_ns": int(target_time_ns),
        "terminal_window_start_ns": int(terminal_window_start_ns),
        "terminal_window_end_ns": int(terminal_window_end_ns),
        "request_time_ns": int(request_time_ns),
        "actual_retrieval_time_ns": int(actual_retrieval_time_ns),
        "provider_id": str(provider_id),
        "capability_id": str(capability_id),
        "retrieval_params": dict(retrieval_params),
        "raw_trade_ref": str(raw_trade_ref),
        "raw_trade_payload_sha256": str(raw_trade_payload_sha256),
        "returned_trade_count": int(returned_trade_count),
        "terminal_candidates": [dict(row) for row in terminal_candidates],
        "selected_terminal_trade": None
        if selected_terminal_trade is None
        else dict(selected_terminal_trade),
        "trade_event_time_ns": None
        if selected_terminal_trade is None
        else int(selected_terminal_trade["event_time_ns"]),
        "availability_semantics": availability_semantics,
        "label_computation_version": label_computation_version,
        "direction_label": direction_label,
        "realized_return": realized_return,
        "label_availability_time_ns": label_availability_time_ns,
        "refusal_reason": refusal_reason,
        "labeler_code_sha": str(labeler_code_sha),
    }
    body["label_evidence_id"] = derive_label_evidence_id(body)
    return body


def validate_prospective_source_observation(source: Mapping[str, Any]) -> None:
    authority = str(source.get("source_evidence_class") or "").upper()
    if authority != CORPUS_EVIDENCE_AUTHORITY_PROSPECTIVE_FEATURE_EVIDENCE:
        raise LabelEvidenceError(
            HISTORICAL_EVENT_NOT_PROSPECTIVE,
            details={"source_evidence_class": authority},
        )
    signal_time_ns = int(source["signal_time_ns"])
    p0_event_time_ns = int(source["p0"]["event_time_ns"])
    if p0_event_time_ns < signal_time_ns:
        raise LabelEvidenceError(
            HISTORICAL_EVENT_NOT_PROSPECTIVE,
            details={
                "p0_event_time_ns": p0_event_time_ns,
                "signal_time_ns": signal_time_ns,
            },
        )
    declared_hash = source.get("source_observation_hash")
    if declared_hash is not None:
        computed = derive_source_observation_hash(source)
        if str(declared_hash) != computed:
            raise LabelEvidenceError(
                INSTRUMENT_OR_HASH_MISMATCH,
                details={"declared_hash": declared_hash, "computed_hash": computed},
            )


def attach_label_evidence(
    source_observation: Mapping[str, Any],
    *,
    trades: Sequence[Mapping[str, Any]],
    request_time_ns: int,
    actual_retrieval_time_ns: int,
    provider_id: str,
    capability_id: str,
    retrieval_params: Mapping[str, Any],
    raw_trade_ref: str,
    raw_trade_payload_sha256: str,
    source_code_sha: str,
    labeler_code_sha: str,
    horizon_policy: OutcomeSettlementPolicy = _PATH_A_POLICY,
) -> LabelAttachResult:
    if capability_id.upper() in _FORBIDDEN_CAPABILITY_IDS:
        raise LabelEvidenceError(BAR_OHLCV_REFUSED_FOR_PATH_A_LABEL, details={"capability_id": capability_id})

    source_copy = copy.deepcopy(dict(source_observation))
    source_hash_before = derive_source_observation_hash(source_copy)
    validate_prospective_source_observation(source_copy)

    instrument_id = str(source_copy["instrument_id"])
    declared_hash = source_copy.get("source_observation_hash")
    if declared_hash is not None and str(declared_hash) != source_hash_before:
        raise LabelEvidenceError(INSTRUMENT_OR_HASH_MISMATCH)

    signal_time_ns = int(source_copy["signal_time_ns"])
    feature_cutoff_ns = int(source_copy.get("feature_cutoff_ns") or signal_time_ns)
    horizon_ns = int(source_copy.get("horizon_ns") or 300_000_000_000)
    target_time_ns = signal_time_ns + horizon_ns
    window_start, window_end = horizon_policy.target_window(target_time_ns=target_time_ns)
    cutoff_ns = horizon_policy.availability_cutoff(target_window_end_ns=window_end)

    assert_retrieval_not_before_terminal_window(
        request_time_ns=request_time_ns,
        terminal_window_end_ns=window_end,
    )

    p0 = dict(source_copy["p0"])
    if str(p0.get("observation_kind") or "").upper() != "TRADE":
        raise LabelEvidenceError(BAR_OHLCV_REFUSED_FOR_PATH_A_LABEL, details={"p0_kind": p0.get("observation_kind")})

    selected, candidates = select_terminal_trade(
        trades,
        instrument_id=instrument_id,
        target_window_start_ns=window_start,
        target_window_end_ns=window_end,
        availability_cutoff_ns=cutoff_ns,
        policy=horizon_policy,
    )

    direction_label: str | None = None
    realized_return: float | None = None
    refusal_reason: str | None = None
    label_availability_time_ns: int | None = None

    if selected is None:
        refusal_reason = NO_ELIGIBLE_TRADE
    else:
        direction_label, realized_return, refusal_reason = compute_path_a_direction_label(
            p0_price=float(p0["price"]),
            terminal_price=float(selected["price"]),
        )
        if direction_label is not None:
            label_availability_time_ns = cutoff_ns

    label_body = build_post_horizon_label_evidence(
        source_observation=source_copy,
        source_observation_hash=source_hash_before,
        signal_time_ns=signal_time_ns,
        feature_cutoff_ns=feature_cutoff_ns,
        source_code_sha=source_code_sha,
        p0=p0,
        horizon_policy_version=horizon_policy.policy_version,
        target_time_ns=target_time_ns,
        terminal_window_start_ns=window_start,
        terminal_window_end_ns=window_end,
        request_time_ns=request_time_ns,
        actual_retrieval_time_ns=actual_retrieval_time_ns,
        provider_id=provider_id,
        capability_id=capability_id,
        retrieval_params=retrieval_params,
        raw_trade_ref=raw_trade_ref,
        raw_trade_payload_sha256=raw_trade_payload_sha256,
        returned_trade_count=len(trades),
        terminal_candidates=candidates,
        selected_terminal_trade=selected,
        labeler_code_sha=labeler_code_sha,
        refusal_reason=refusal_reason,
        direction_label=direction_label,
        realized_return=realized_return,
        label_availability_time_ns=label_availability_time_ns,
    )

    source_hash_after = derive_source_observation_hash(source_copy)
    if source_hash_before != source_hash_after:
        raise LabelEvidenceError(
            INSTRUMENT_OR_HASH_MISMATCH,
            details={"before": source_hash_before, "after": source_hash_after},
        )

    linkage = {
        "source_observation_id": source_copy["source_observation_id"],
        "source_observation_hash": source_hash_before,
        "label_evidence_id": label_body["label_evidence_id"],
        "label_evidence_hash": derive_label_evidence_id(label_body),
    }
    return LabelAttachResult(
        source_observation=source_copy,
        label_evidence=label_body,
        linkage=linkage,
        source_hash_before=source_hash_before,
        source_hash_after=source_hash_after,
    )


def assert_feature_constructor_corpus_safe(
    feature_columns: Sequence[str],
    *,
    label_columns: Sequence[str] | None = None,
    explicit_approved_join: bool = False,
) -> None:
    """Block accidental post-horizon label merge into feature constructors."""
    if explicit_approved_join:
        return
    label_cols = set(label_columns or ())
    post_horizon_tokens = (
        "direction_label",
        "realized_return",
        "label_availability",
        "terminal_trade",
        "post_horizon",
    )
    for column in feature_columns:
        lowered = column.lower()
        if column in label_cols or any(token in lowered for token in post_horizon_tokens):
            raise LabelEvidenceError(
                IMPLICIT_LABEL_COLUMN_MERGE_REFUSED,
                details={"column": column},
            )


__all__ = [
    "BAR_OHLCV_REFUSED_FOR_PATH_A_LABEL",
    "HISTORICAL_EVENT_NOT_PROSPECTIVE",
    "IMPLICIT_LABEL_COLUMN_MERGE_REFUSED",
    "INSTRUMENT_OR_HASH_MISMATCH",
    "LABEL_COMPUTATION_VERSION",
    "LabelAttachResult",
    "LabelEvidenceError",
    "MALFORMED_PROVIDER_TRADE_RECORD",
    "NO_ELIGIBLE_TRADE",
    "POST_HORIZON_LABEL_EVIDENCE_KIND",
    "POST_HORIZON_LABEL_SCHEMA_VERSION",
    "RETRIEVAL_BEFORE_TERMINAL_WINDOW_END",
    "assert_feature_constructor_corpus_safe",
    "assert_retrieval_not_before_terminal_window",
    "attach_label_evidence",
    "build_post_horizon_label_evidence",
    "compute_path_a_direction_label",
    "derive_label_evidence_id",
    "derive_source_observation_hash",
    "select_terminal_trade",
    "validate_prospective_source_observation",
]
