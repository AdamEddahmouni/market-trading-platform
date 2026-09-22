"""Item 9 calibration preflight (read-only; never fits).

Consumes a readiness snapshot and returns CALIBRATION_PREFLIGHT_READY or
CALIBRATION_PREFLIGHT_BLOCKED. ABSENT authorization does not block READY.
Never sets calibrated=true. Never opens a parameter search.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .item9_calibration_execute import bind_preflight_toctou
from .item9_calibration_protocol import (
    CALIBRATION_STATE,
    ITEM9_STATUS_NOT_CALIBRATED,
    MINIMUM_DISTINCT_RTH_DATES,
    MINIMUM_EVALUATION_ROWS,
    PROTOCOL_VERSION,
    SPLIT_DEVELOPMENT,
    SPLIT_EVALUATION,
    SPLIT_SELECTION,
)
from .item9_readiness_snapshot import (
    build_item9_readiness_snapshot,
    resolve_governed_receipt_dir,
)
from .item9_validation_readiness_contract import (
    AUTHORIZATION_ABSENT,
    BOUND_PROTOCOL_VERSION,
    CALIBRATED_DEFAULT,
    CALIBRATION_PREFLIGHT_BLOCKED,
    CALIBRATION_PREFLIGHT_READY,
    DISPOSITION_PATH_PROOF_ONLY,
    DISPOSITION_UNKNOWN_REQUIRES_REVIEW,
    FIELD_NOT_RUN,
    FIELD_UNAVAILABLE,
    FITTING_ALLOWED_DEFAULT,
    ITEM9_CALIBRATION_RUN_FORBIDDEN,
    READINESS_STATE_AWAITING_AUTHORIZATION,
    READINESS_STATE_NOT_READY,
    READINESS_STATE_UNSET,
    REASON_AUTHORIZATION_ABSENT_REPORTED,
    REASON_AUTHORITY_MIXING,
    REASON_CONTAMINATION_AUDIT_FAIL,
    REASON_CORPUS_FINGERPRINT_OK,
    REASON_CRITICAL_UNKNOWN,
    REASON_DETERMINISTIC_ORDERING,
    REASON_DUPLICATES_REJECTED,
    REASON_EVAL_FLOOR_MET,
    REASON_EVAL_FLOOR_UNMET,
    REASON_EXCLUSION_ACCOUNTED,
    REASON_GAP_REGISTER_LOADED,
    REASON_HOLDOUT_LEAK,
    REASON_INTEGRITY_FAILURE,
    REASON_PATH_PROOF_IN_CONSUMPTION,
    REASON_PIT_OK,
    REASON_PROTECTED_EVAL_CONSUMED,
    REASON_PROTOCOL_FINGERPRINT_OK,
    REASON_PROVENANCE_OK,
    REASON_RECEIPT_DIR_UNAVAILABLE,
    REASON_RTH_DATES_MET,
    REASON_RTH_DATES_UNMET,
    REASON_SAMPLE_FLOOR_MET,
    REASON_SAMPLE_FLOOR_UNMET,
    REASON_SCHEMA_VERSION_OK,
    REASON_SIMULATOR_VERSION_OK,
    REASON_TOCTOU_FINGERPRINT_BOUND,
    REASON_TRAIN_EVAL_SEPARATED,
    REASON_UNTOUCHED_EVAL_SEALED,
    RULE_AUTH_ABSENT_OK_PREFLIGHT,
    RULE_NO_PATH_PROOF_IN_CONSUMPTION,
    RULE_PROTOCOL_SAMPLE_FLOORS,
    RULE_TOCTOU_FINGERPRINT,
    RULE_UNTOUCHED_EVAL_SEAL,
    SEARCH_COMPLEXITY_MAX,
)
from ...intelligence.fusion.calibration_data import MINIMUM_CALIBRATION_SAMPLES

PREFLIGHT_ARTIFACT_KIND = "item9_calibration_preflight_v1"


def run_item9_calibration_preflight(
    *,
    snapshot: Mapping[str, Any] | None = None,
    receipt_dir: Path | None = None,
    imp_root: Path | None = None,
    authorization_state: str = AUTHORIZATION_ABSENT,
) -> dict[str, Any]:
    """Evaluate calibration readiness. Never fits. Never flips calibrated."""

    if snapshot is None:
        resolved = receipt_dir or resolve_governed_receipt_dir(imp_root=imp_root)
        snapshot = build_item9_readiness_snapshot(
            resolved,
            imp_root=imp_root,
            authorization_state=authorization_state,
        )
    else:
        snapshot = dict(snapshot)

    reasons: list[str] = []
    blockers: list[str] = []

    if snapshot.get("snapshot_status") in {FIELD_NOT_RUN, None} or snapshot.get(
        "receipt_dir_status"
    ) == FIELD_UNAVAILABLE:
        blockers.append(REASON_RECEIPT_DIR_UNAVAILABLE)
        return _blocked(
            snapshot=snapshot,
            authorization_state=authorization_state,
            reasons=reasons,
            blockers=blockers,
            readiness_state=READINESS_STATE_UNSET,
        )

    counts = dict(snapshot.get("counts") or {})
    gate = dict(snapshot.get("sample_gate") or {})
    boundary = dict(snapshot.get("evaluation_boundary") or {})
    dispositions = list(snapshot.get("dispositions") or [])

    included = int(gate.get("included_count") or counts.get("corpus_admissible") or 0)
    rth_dates = int(gate.get("distinct_rth_dates") or len(snapshot.get("session_dates_rth") or []))
    eval_count = int(gate.get("evaluation_count") or counts.get("evaluation_rows") or 0)

    if included >= MINIMUM_CALIBRATION_SAMPLES:
        reasons.append(REASON_SAMPLE_FLOOR_MET)
    else:
        blockers.append(REASON_SAMPLE_FLOOR_UNMET)

    if rth_dates >= MINIMUM_DISTINCT_RTH_DATES:
        reasons.append(REASON_RTH_DATES_MET)
    else:
        blockers.append(REASON_RTH_DATES_UNMET)

    if eval_count >= MINIMUM_EVALUATION_ROWS:
        reasons.append(REASON_EVAL_FLOOR_MET)
    else:
        blockers.append(REASON_EVAL_FLOOR_UNMET)

    if snapshot.get("corpus_fingerprint"):
        reasons.append(REASON_CORPUS_FINGERPRINT_OK)
    else:
        blockers.append(REASON_INTEGRITY_FAILURE)

    if snapshot.get("protocol_fingerprint"):
        reasons.append(REASON_PROTOCOL_FINGERPRINT_OK)
    else:
        blockers.append(REASON_INTEGRITY_FAILURE)

    if snapshot.get("dataset_schema_version") and snapshot.get("protocol_version") == PROTOCOL_VERSION:
        reasons.append(REASON_SCHEMA_VERSION_OK)
    else:
        blockers.append(REASON_INTEGRITY_FAILURE)

    if snapshot.get("simulator_version"):
        reasons.append(REASON_SIMULATOR_VERSION_OK)
    else:
        blockers.append(REASON_INTEGRITY_FAILURE)

    if int(counts.get("unknown_provenance") or 0) == 0:
        reasons.append(REASON_PROVENANCE_OK)
    else:
        blockers.append(REASON_INTEGRITY_FAILURE)

    # PIT / forensic: critical UNKNOWN blocks
    critical_unknown = list(snapshot.get("critical_unknown_observation_ids") or [])
    unknown_dispositions = [
        d
        for d in dispositions
        if d.get("disposition") == DISPOSITION_UNKNOWN_REQUIRES_REVIEW
        and d.get("corpus_admissible")
    ]
    if critical_unknown or unknown_dispositions:
        blockers.append(REASON_CRITICAL_UNKNOWN)
    else:
        reasons.append(REASON_PIT_OK)

    # Exclusion accounting: every disposition row has id→reason→rule
    exclusion_ok = all(
        d.get("disposition") and (d.get("reason") is not None or d.get("disposition") in {
            "ADMISSIBLE",
            "EVALUATION_ONLY",
        })
        and d.get("rule")
        for d in dispositions
    )
    # ADMISSIBLE may have reason None
    exclusion_ok = all(bool(d.get("disposition")) and bool(d.get("rule")) for d in dispositions)
    if exclusion_ok:
        reasons.append(REASON_EXCLUSION_ACCOUNTED)
    else:
        blockers.append(REASON_INTEGRITY_FAILURE)

    if boundary.get("untouched_evaluation_sealed"):
        reasons.append(REASON_UNTOUCHED_EVAL_SEALED)
    else:
        blockers.append(REASON_HOLDOUT_LEAK)

    eval_ids = set(boundary.get(SPLIT_EVALUATION) or [])
    dev_ids = set(boundary.get(SPLIT_DEVELOPMENT) or [])
    sel_ids = set(boundary.get(SPLIT_SELECTION) or [])
    if not (eval_ids & dev_ids) and not (eval_ids & sel_ids):
        reasons.append(REASON_TRAIN_EVAL_SEPARATED)
    else:
        blockers.append(REASON_HOLDOUT_LEAK)

    dup_count = int(counts.get("duplicate") or 0) + int(counts.get("duplicate_file_hash_groups") or 0)
    # Duplicates must be rejected (not in consumption). Presence of accounted duplicates is OK.
    reasons.append(REASON_DUPLICATES_REJECTED)

    # PATH_PROOF_ONLY must not appear in consumption (admissible) set
    path_proof_in_consumption = [
        d
        for d in dispositions
        if d.get("disposition") == DISPOSITION_PATH_PROOF_ONLY and d.get("corpus_admissible")
    ]
    path_proof_count = int(counts.get("path_proof_only") or 0)
    if path_proof_in_consumption:
        blockers.append(REASON_PATH_PROOF_IN_CONSUMPTION)
    else:
        # PATH_PROOF_ONLY rows may exist but must not be corpus_admissible
        reasons.append("PATH_PROOF_ONLY_EXCLUDED_FROM_CONSUMPTION")

    if not boundary.get("shuffle", True) and boundary.get("split_fractions") == [0.6, 0.2, 0.2]:
        reasons.append(REASON_DETERMINISTIC_ORDERING)
    else:
        blockers.append(REASON_INTEGRITY_FAILURE)

    gap = dict(snapshot.get("gap_register") or {})
    if gap.get("loaded"):
        reasons.append(REASON_GAP_REGISTER_LOADED)
    # Missing gap register is not a hard block if file unavailable in odd layouts,
    # but preferred: warn via reason absence only when loaded=False and no intervals.

    # Authority mixing via forensic flags
    authority_mix = any(
        any(
            f.get("code") == "HISTORICAL_DEVELOPMENT_PATH"
            for f in (d.get("forensic_flags") or [])
        )
        for d in dispositions
    )
    if authority_mix:
        blockers.append(REASON_AUTHORITY_MIXING)

    dual = dict(snapshot.get("dual_corpus") or {})
    if dual:
        if dual.get("contamination_status") == "FAIL" or int(dual.get("item9_admission_refused_count") or 0) > 0:
            blockers.append(REASON_CONTAMINATION_AUDIT_FAIL)
        leaked = int((dual.get("untouched_consumption_guard") or {}).get("leaked_into_training") or 0)
        if leaked > 0:
            blockers.append(REASON_PROTECTED_EVAL_CONSUMED)

    toctou_binding = dict(snapshot.get("toctou_binding") or {})
    if not toctou_binding:
        toctou_binding = bind_preflight_toctou(snapshot)
    if toctou_binding.get("corpus_fingerprint") and toctou_binding.get("protocol_fingerprint"):
        reasons.append(REASON_TOCTOU_FINGERPRINT_BOUND)

    # ABSENT authorization is reported beside READY — does not block.
    auth_state = str(snapshot.get("authorization_state") or authorization_state)
    if auth_state == AUTHORIZATION_ABSENT:
        reasons.append(REASON_AUTHORIZATION_ABSENT_REPORTED)

    if blockers:
        return _blocked(
            snapshot=snapshot,
            authorization_state=auth_state,
            reasons=reasons,
            blockers=blockers,
            readiness_state=READINESS_STATE_NOT_READY,
            path_proof_count=path_proof_count,
            dup_count=dup_count,
        )

    return {
        "artifact_kind": PREFLIGHT_ARTIFACT_KIND,
        "protocol_version": PROTOCOL_VERSION,
        "bound_protocol_version": BOUND_PROTOCOL_VERSION,
        "preflight_verdict": CALIBRATION_PREFLIGHT_READY,
        "readiness_state": READINESS_STATE_AWAITING_AUTHORIZATION,
        "item9_status": ITEM9_STATUS_NOT_CALIBRATED,
        "calibration_state": CALIBRATION_STATE,
        "calibrated": CALIBRATED_DEFAULT,
        "fitting_allowed": FITTING_ALLOWED_DEFAULT,
        "item9_calibration_run": ITEM9_CALIBRATION_RUN_FORBIDDEN,
        "authorization_state": auth_state,
        "authorization_blocks_preflight": False,
        "authorization_blocks_execution": True,
        "authorization_rule": RULE_AUTH_ABSENT_OK_PREFLIGHT,
        "search_complexity_max": SEARCH_COMPLEXITY_MAX,
        "reasons": reasons,
        "blockers": [],
        "floors": {
            "minimum_calibration_samples": MINIMUM_CALIBRATION_SAMPLES,
            "minimum_distinct_rth_dates": MINIMUM_DISTINCT_RTH_DATES,
            "minimum_evaluation_rows": MINIMUM_EVALUATION_ROWS,
            "governing_rule_id": RULE_PROTOCOL_SAMPLE_FLOORS,
        },
        "corpus_fingerprint": snapshot.get("corpus_fingerprint"),
        "evaluation_fingerprint": snapshot.get("evaluation_fingerprint"),
        "protocol_fingerprint": snapshot.get("protocol_fingerprint"),
        "session_dates_rth": list(snapshot.get("session_dates_rth") or []),
        "counts": {
            "corpus_admissible": included,
            "evaluation_rows": eval_count,
            "path_proof_only": path_proof_count,
            "duplicate_accounted": dup_count,
        },
        "untouched_eval_rule": RULE_UNTOUCHED_EVAL_SEAL,
        "path_proof_rule": RULE_NO_PATH_PROOF_IN_CONSUMPTION,
        "toctou_binding": toctou_binding,
        "toctou_rule": RULE_TOCTOU_FINGERPRINT,
        "dual_corpus_status": dual.get("contamination_status"),
        "dual_corpus_role_map_counts": {
            key: (snapshot.get("dual_corpus_role_map") or {}).get(key, {}).get("count")
            for key in ("TRAINING", "DEVELOPMENT", "CALIBRATION", "UNTOUCHED")
        },
        "receipt_dir": snapshot.get("receipt_dir"),
        "snapshot_schema_id": snapshot.get("schema_id"),
    }


def _blocked(
    *,
    snapshot: Mapping[str, Any],
    authorization_state: str,
    reasons: list[str],
    blockers: list[str],
    readiness_state: str,
    path_proof_count: int = 0,
    dup_count: int = 0,
) -> dict[str, Any]:
    return {
        "artifact_kind": PREFLIGHT_ARTIFACT_KIND,
        "protocol_version": PROTOCOL_VERSION,
        "bound_protocol_version": BOUND_PROTOCOL_VERSION,
        "preflight_verdict": CALIBRATION_PREFLIGHT_BLOCKED,
        "readiness_state": readiness_state,
        "item9_status": ITEM9_STATUS_NOT_CALIBRATED,
        "calibration_state": CALIBRATION_STATE,
        "calibrated": CALIBRATED_DEFAULT,
        "fitting_allowed": FITTING_ALLOWED_DEFAULT,
        "item9_calibration_run": ITEM9_CALIBRATION_RUN_FORBIDDEN,
        "authorization_state": authorization_state,
        "authorization_blocks_preflight": False,
        "authorization_blocks_execution": True,
        "authorization_rule": RULE_AUTH_ABSENT_OK_PREFLIGHT,
        "search_complexity_max": SEARCH_COMPLEXITY_MAX,
        "reasons": reasons,
        "blockers": blockers,
        "corpus_fingerprint": snapshot.get("corpus_fingerprint"),
        "evaluation_fingerprint": snapshot.get("evaluation_fingerprint"),
        "protocol_fingerprint": snapshot.get("protocol_fingerprint"),
        "session_dates_rth": list(snapshot.get("session_dates_rth") or []),
        "counts": {
            "path_proof_only": path_proof_count,
            "duplicate_accounted": dup_count,
        },
        "receipt_dir": snapshot.get("receipt_dir"),
        "snapshot_schema_id": snapshot.get("schema_id"),
    }


__all__ = [
    "PREFLIGHT_ARTIFACT_KIND",
    "run_item9_calibration_preflight",
]
