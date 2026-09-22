"""Item 9 validation readiness snapshot (read-only; no fitting).

Builds a forensic disposition register, evaluation boundary map, corpus
fingerprints, and NOT_OBSERVED gap register binding. Never writes receipts,
never synthesizes gap bars, never sets calibrated=true.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

from ...execution.simulator import SIMULATOR_VERSION
from .bar_ohlcv_prospective_proof import DEFAULT_RECEIPT_DIR, RECEIPT_CONTRACT_VERSION, imp_package_root
from .dual_corpus.admission import (
    ITEM9_ADMISSION_REFUSED,
    evaluate_item9_prospective_corpus_admission,
)
from .dual_corpus.contamination_auditor import (
    ITEM9_EFFECT_PROSPECTIVE_INPUT,
    audit_research_contamination_run,
)
from .dual_corpus.consumption import (
    ProtectedCorpusConsumptionError,
    assert_corpus_consumable_for_selection_or_training,
)
from .dual_corpus.discovery import is_historical_development_storage_path
from .dual_corpus.evidence_authority import (
    CORPUS_EVIDENCE_AUTHORITY_PROSPECTIVE_FEATURE_EVIDENCE,
    CORPUS_EVIDENCE_AUTHORITY_UNTOUCHED_FORWARD_EVALUATION,
)
from .dual_corpus.run_manifest import (
    RESEARCH_CONTAMINATION_RUN_MANIFEST_KIND,
    RESEARCH_CONTAMINATION_RUN_SCHEMA_VERSION,
)
from .item9_calibration_protocol import (
    CALIBRATION_STATE,
    DATASET_SCHEMA_VERSION,
    INCLUSION_DUPLICATE,
    INCLUSION_EXCLUDED,
    INCLUSION_INCLUDED,
    INCLUSION_INVALID,
    INCLUSION_PATH_PROOF_ONLY,
    ITEM9_STATUS_NOT_CALIBRATED,
    MINIMUM_DISTINCT_RTH_DATES,
    MINIMUM_EVALUATION_ROWS,
    PROTOCOL_VERSION,
    SPLIT_DEVELOPMENT,
    SPLIT_EVALUATION,
    SPLIT_SELECTION,
    audit_receipt_directory,
    build_dataset_row,
    chronological_split,
    classify_item9_receipt,
    evaluate_sample_gate,
    governed_receipt_paths,
    is_empty_raw_provenance_hash,
    load_governed_receipt,
    protocol_freeze_record,
    reject_incomplete_bar,
    session_date_et,
)
from .item9_validation_readiness_contract import (
    AUTHORIZATION_ABSENT,
    BOUND_PROTOCOL_VERSION,
    CALIBRATED_DEFAULT,
    DISPOSITION_ADMISSIBLE,
    DISPOSITION_EVALUATION_ONLY,
    DISPOSITION_EXCLUDED_WITH_REASON,
    DISPOSITION_PATH_PROOF_ONLY,
    DISPOSITION_UNKNOWN_REQUIRES_REVIEW,
    FIELD_NOT_APPLICABLE,
    FIELD_NOT_OBSERVED,
    FIELD_NOT_RUN,
    FIELD_UNAVAILABLE,
    FITTING_ALLOWED_DEFAULT,
    ITEM9_CALIBRATION_RUN_FORBIDDEN,
    MODE_B_NOT_APPLICABLE_FIELDS,
    READINESS_SNAPSHOT_SCHEMA_ID,
    READINESS_STATE_UNSET,
    RULE_ADMISSION_PROSPECTIVE,
    RULE_DUAL_CORPUS_HOLDOUT,
    RULE_DUAL_CORPUS_LEAK,
    RULE_EVALUATION_LIFECYCLE_ROLE,
    RULE_FORENSIC_AUTHORITY_MIXING,
    RULE_FORENSIC_DUPLICATE_EXPERIMENT,
    RULE_FORENSIC_DUPLICATE_HASH,
    RULE_FORENSIC_EMPTY_RAW_HASH,
    RULE_FORENSIC_INSTRUMENT,
    RULE_FORENSIC_NON_RTH,
    RULE_FORENSIC_PIT,
    RULE_FORENSIC_TIMESTAMP_ORDER,
    RULE_FORENSIC_VERSION_DRIFT,
    RULE_FORENSIC_ZERO_PRICE_VOLUME,
    RULE_GAP_REGISTER_NOT_OBSERVED,
    RULE_MODE_B_STRATEGY_N_A,
    RULE_PROTOCOL_CHRONO_SPLIT,
    RULE_PROTOCOL_SAMPLE_FLOORS,
    RULE_PROTOCOL_SEARCH_COMPLEXITY_0,
    RULE_PROTOCOL_V1_FREEZE,
    RULE_UNTOUCHED_EVAL_SEAL,
    RULE_TOCTOU_FINGERPRINT,
    SEARCH_COMPLEXITY_MAX,
    contract_freeze_record,
)
from ...intelligence.fusion.calibration_data import MINIMUM_CALIBRATION_SAMPLES
from ...intelligence.paper_forward_bridge.session_policy import is_within_us_equity_rth

GAP_REGISTER_REL = Path("manifests/paper/item9_not_observed_intervals_v1.json")
SNAPSHOT_ARTIFACT_KIND = "item9_validation_readiness_snapshot_v1"


def _canonical_json_hash(payload: Any) -> str:
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_not_observed_gap_register(*, imp_root: Path | None = None) -> dict[str, Any]:
    """Load the governed NOT_OBSERVED interval register (never synthesizes bars)."""

    root = imp_root or imp_package_root()
    path = root / GAP_REGISTER_REL
    if not path.is_file():
        return {
            "loaded": False,
            "status": FIELD_UNAVAILABLE,
            "path": str(path),
            "intervals": [],
            "synthesize_bars_for_gaps": False,
            "governing_rule_id": RULE_GAP_REGISTER_NOT_OBSERVED,
        }
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return {
            "loaded": False,
            "status": "INVALID",
            "path": str(path),
            "intervals": [],
            "synthesize_bars_for_gaps": False,
            "governing_rule_id": RULE_GAP_REGISTER_NOT_OBSERVED,
        }
    return {
        "loaded": True,
        "status": "LOADED",
        "path": str(path.resolve()),
        "schema_id": payload.get("schema_id"),
        "schema_version": payload.get("schema_version"),
        "synthesize_bars_for_gaps": bool(payload.get("synthesize_bars_for_gaps", False)),
        "backfill_allowed": bool(payload.get("backfill_allowed", False)),
        "intervals": list(payload.get("intervals") or []),
        "governing_rule_id": RULE_GAP_REGISTER_NOT_OBSERVED,
    }


def refuse_gap_synthesis(gap_register: Mapping[str, Any]) -> dict[str, Any]:
    """Explicit refuse token: snapshot must never mint bars for NOT_OBSERVED gaps."""

    return {
        "synthesis_attempted": False,
        "synthesis_refused": True,
        "reason": "GAP_REGISTER_FORBIDS_SYNTHESIS",
        "governing_rule_id": RULE_GAP_REGISTER_NOT_OBSERVED,
        "gap_count": len(list(gap_register.get("intervals") or [])),
        "synthesize_bars_for_gaps": bool(gap_register.get("synthesize_bars_for_gaps", False)),
    }


def _compact_admission_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    bar_prov = payload.get("bar_provenance")
    nested = bar_prov.get("evidence_class") if isinstance(bar_prov, Mapping) else None
    return {
        "proof_mode": payload.get("proof_mode"),
        "not_prospective_evidence": payload.get("not_prospective_evidence"),
        "evidence_class": payload.get("evidence_class"),
        "bar_provenance": {"evidence_class": nested},
        "corpus_evidence_authority": payload.get("corpus_evidence_authority"),
        "experiment_id": payload.get("experiment_id"),
        "signal_time_ns": payload.get("signal_time_ns"),
    }


def _ns_bounds(rows: Sequence[Mapping[str, Any]], ids: set[str]) -> tuple[int, int] | None:
    times = [
        int(row["signal_timestamp_ns"])
        for row in rows
        if str(row.get("observation_id") or "") in ids and row.get("signal_timestamp_ns")
    ]
    if not times:
        return None
    return min(times), max(times) + 1


def build_item9_dual_corpus_audit(
    *,
    included_rows: Sequence[Mapping[str, Any]],
    compact_payloads: Sequence[Mapping[str, Any]],
    development_ids: set[str],
    selection_ids: set[str],
    evaluation_ids: set[str],
    corpus_fingerprint: str,
) -> dict[str, Any]:
    """Lane B: dual-corpus contamination + consumption guards (read-only)."""

    train_ids = development_ids | selection_ids
    train_bounds = _ns_bounds(included_rows, train_ids)
    eval_bounds = _ns_bounds(included_rows, evaluation_ids)
    if train_bounds is None:
        train_bounds = (0, 1)
    if eval_bounds is None:
        eval_bounds = (train_bounds[1], train_bounds[1] + 1)

    training_examples = [
        {
            "snapshot_id": str(row.get("observation_id") or ""),
            "decision_time_ns": int(row["signal_timestamp_ns"]),
        }
        for row in included_rows
        if str(row.get("observation_id") or "") in train_ids and row.get("signal_timestamp_ns")
    ]

    manifest: dict[str, Any] = {
        "artifact_kind": RESEARCH_CONTAMINATION_RUN_MANIFEST_KIND,
        "schema_version": RESEARCH_CONTAMINATION_RUN_SCHEMA_VERSION,
        "run_id": f"item9-readiness-{corpus_fingerprint[:16]}",
        "lineage_complete": True,
        "authority_context": {
            "primary_authority": CORPUS_EVIDENCE_AUTHORITY_PROSPECTIVE_FEATURE_EVIDENCE,
            "item9_effect": ITEM9_EFFECT_PROSPECTIVE_INPUT,
        },
        "splits": {
            "train": {"start_ns": train_bounds[0], "end_ns": train_bounds[1]},
            "test": {"start_ns": eval_bounds[0], "end_ns": eval_bounds[1]},
        },
        "holdout": {
            "holdout_start_ns": eval_bounds[0],
            "holdout_end_ns": eval_bounds[1],
        },
        "feature_lineage": [],
        "training_examples": training_examples,
        "corpus_inputs": [],
        "item9_prospective_inputs": list(compact_payloads),
        "target_leakage": [],
    }
    contamination = audit_research_contamination_run(manifest)

    admission_refused = 0
    for payload in compact_payloads:
        outcome = evaluate_item9_prospective_corpus_admission(payload=payload)
        if outcome.get("disposition") == ITEM9_ADMISSION_REFUSED:
            admission_refused += 1

    eval_refused = 0
    eval_leaked = 0
    for _obs_id in evaluation_ids:
        try:
            assert_corpus_consumable_for_selection_or_training(
                corpus_evidence_authority=CORPUS_EVIDENCE_AUTHORITY_UNTOUCHED_FORWARD_EVALUATION,
                purpose="selection_or_training",
            )
            eval_leaked += 1
        except ProtectedCorpusConsumptionError:
            eval_refused += 1

    train_consumable = 0
    train_refused = 0
    for _obs_id in train_ids:
        try:
            assert_corpus_consumable_for_selection_or_training(
                corpus_evidence_authority=CORPUS_EVIDENCE_AUTHORITY_PROSPECTIVE_FEATURE_EVIDENCE,
                purpose="selection_or_training",
            )
            train_consumable += 1
        except ProtectedCorpusConsumptionError:
            train_refused += 1

    role_map = {
        "TRAINING": {
            "aliases_to": SPLIT_DEVELOPMENT,
            "count": len(development_ids),
            "ids": sorted(development_ids),
        },
        "DEVELOPMENT": {
            "aliases_to": SPLIT_DEVELOPMENT,
            "count": len(development_ids),
            "ids": sorted(development_ids),
        },
        "CALIBRATION": {
            "aliases_to": SPLIT_SELECTION,
            "count": len(selection_ids),
            "ids": sorted(selection_ids),
        },
        "UNTOUCHED": {
            "aliases_to": SPLIT_EVALUATION,
            "count": len(evaluation_ids),
            "ids": sorted(evaluation_ids),
        },
    }

    return {
        "contamination_status": contamination.get("CONTAMINATION_STATUS"),
        "contamination_questions": contamination.get("questions") or {},
        "contamination_violation_count": len(list(contamination.get("violations") or [])),
        "contamination_violations": contamination.get("violations") or [],
        "item9_admission_refused_count": admission_refused,
        "untouched_consumption_guard": {
            "evaluation_rows": len(evaluation_ids),
            "refused_for_selection_or_training": eval_refused,
            "leaked_into_training": eval_leaked,
            "governing_rule_id": RULE_DUAL_CORPUS_HOLDOUT,
        },
        "training_consumption_guard": {
            "train_or_selection_rows": len(train_ids),
            "consumable": train_consumable,
            "refused": train_refused,
        },
        "dual_corpus_role_map": role_map,
        "governing_rule_id": RULE_DUAL_CORPUS_LEAK,
        "item9_effect": ITEM9_EFFECT_PROSPECTIVE_INPUT,
    }


def _mode_b_field_applicability() -> dict[str, str]:
    return {field: FIELD_NOT_APPLICABLE for field in sorted(MODE_B_NOT_APPLICABLE_FIELDS)}


def _forensic_flags(receipt: Mapping[str, Any], *, path: Path) -> list[dict[str, Any]]:
    """Additional fail-closed forensic checks beyond classify_item9_receipt."""

    flags: list[dict[str, Any]] = []
    first = receipt.get("first_post_signal_bar") or {}
    signal_ns = int(receipt.get("signal_time_ns") or 0)
    bar_available = int(receipt.get("bar_available_time_ns") or first.get("available_time_ns") or 0)
    bar_start = int(receipt.get("bar_start_ns") or first.get("event_time_ns") or 0)
    fetched = int(
        (receipt.get("bar_provenance") or {}).get("fetched_at_ns")
        or receipt.get("observation_time_ns")
        or 0
    )
    event_time = int(first.get("event_time_ns") or bar_start or 0)
    available_time = int(first.get("available_time_ns") or bar_available or 0)
    received_time = int(
        (receipt.get("bar_provenance") or {}).get("received_time_ns")
        or fetched
        or 0
    )

    if not signal_ns or not bar_available:
        flags.append(
            {
                "code": "MISSING_TIMESTAMPS",
                "severity": "CRITICAL",
                "rule": RULE_FORENSIC_TIMESTAMP_ORDER,
            }
        )
    if event_time and available_time and event_time > available_time:
        flags.append(
            {
                "code": "EVENT_AFTER_AVAILABLE",
                "severity": "CRITICAL",
                "rule": RULE_FORENSIC_TIMESTAMP_ORDER,
            }
        )
    if available_time and received_time and available_time > received_time:
        flags.append(
            {
                "code": "AVAILABLE_AFTER_RECEIVED",
                "severity": "CRITICAL",
                "rule": RULE_FORENSIC_TIMESTAMP_ORDER,
            }
        )
    if bar_available and signal_ns and bar_available <= signal_ns:
        flags.append(
            {
                "code": "FEATURE_LOOKAHEAD",
                "severity": "CRITICAL",
                "rule": RULE_FORENSIC_PIT,
            }
        )
    if fetched and bar_available and reject_incomplete_bar(
        bar_end_ns=bar_available, fetched_at_ns=fetched
    ):
        flags.append(
            {
                "code": "INCOMPLETE_BAR_VS_FETCHED",
                "severity": "CRITICAL",
                "rule": RULE_FORENSIC_PIT,
            }
        )
    if signal_ns and not is_within_us_equity_rth(signal_ns):
        flags.append(
            {
                "code": "NON_RTH",
                "severity": "CRITICAL",
                "rule": RULE_FORENSIC_NON_RTH,
            }
        )
    if is_empty_raw_provenance_hash(str(receipt.get("raw_provenance_hash") or "")):
        flags.append(
            {
                "code": "EMPTY_RAW_HASH",
                "severity": "INFO",
                "rule": RULE_FORENSIC_EMPTY_RAW_HASH,
            }
        )

    bar_payload = first.get("bar_payload") if isinstance(first, Mapping) else None
    if isinstance(bar_payload, Mapping):
        try:
            high = float(bar_payload.get("high") or 0)
            low = float(bar_payload.get("low") or 0)
            volume = float(bar_payload.get("volume") or 0)
        except (TypeError, ValueError):
            high = low = volume = 0.0
        if high <= 0 or low <= 0 or volume <= 0:
            flags.append(
                {
                    "code": "ZERO_PRICE_OR_VOLUME",
                    "severity": "CRITICAL",
                    "rule": RULE_FORENSIC_ZERO_PRICE_VOLUME,
                }
            )

    instrument = str(receipt.get("instrument_id") or "").strip()
    if not instrument:
        flags.append(
            {
                "code": "MISSING_INSTRUMENT",
                "severity": "CRITICAL",
                "rule": RULE_FORENSIC_INSTRUMENT,
            }
        )

    contract_ver = str(receipt.get("receipt_contract_version") or "")
    if contract_ver and contract_ver != RECEIPT_CONTRACT_VERSION:
        flags.append(
            {
                "code": "RECEIPT_CONTRACT_VERSION_DRIFT",
                "severity": "WARNING",
                "rule": RULE_FORENSIC_VERSION_DRIFT,
                "observed": contract_ver,
                "expected": RECEIPT_CONTRACT_VERSION,
            }
        )

    if is_historical_development_storage_path(path):
        flags.append(
            {
                "code": "HISTORICAL_DEVELOPMENT_PATH",
                "severity": "CRITICAL",
                "rule": RULE_FORENSIC_AUTHORITY_MIXING,
            }
        )

    freshness = str(receipt.get("freshness_status") or receipt.get("freshness") or "").upper()
    if freshness in {"STALE", "STALE_EVIDENCE"}:
        flags.append(
            {
                "code": "STALE",
                "severity": "CRITICAL",
                "rule": RULE_FORENSIC_TIMESTAMP_ORDER,
            }
        )
    if not isinstance(first, Mapping) or not first.get("bar_payload"):
        flags.append(
            {
                "code": "INCOMPLETE_OUTCOME",
                "severity": "CRITICAL",
                "rule": RULE_FORENSIC_PIT,
            }
        )

    return flags


def _map_disposition(
    *,
    inclusion_state: str,
    observation_id: str,
    evaluation_ids: set[str],
    critical_unknown: bool,
) -> tuple[str, str | None, str]:
    if critical_unknown:
        return (
            DISPOSITION_UNKNOWN_REQUIRES_REVIEW,
            "CRITICAL_FORENSIC_FLAG",
            RULE_FORENSIC_PIT,
        )
    if inclusion_state == INCLUSION_PATH_PROOF_ONLY:
        return (
            DISPOSITION_PATH_PROOF_ONLY,
            "EMPTY_RAW_PROVENANCE_HASH",
            RULE_FORENSIC_EMPTY_RAW_HASH,
        )
    if inclusion_state in {INCLUSION_EXCLUDED, INCLUSION_INVALID, INCLUSION_DUPLICATE}:
        return (
            DISPOSITION_EXCLUDED_WITH_REASON,
            inclusion_state,
            RULE_ADMISSION_PROSPECTIVE,
        )
    if inclusion_state == INCLUSION_INCLUDED or inclusion_state == "INCLUDED":
        if observation_id and observation_id in evaluation_ids:
            return (
                DISPOSITION_EVALUATION_ONLY,
                "UNTOUCHED_EVALUATION_LIFECYCLE_ROLE",
                RULE_EVALUATION_LIFECYCLE_ROLE,
            )
        return (DISPOSITION_ADMISSIBLE, None, RULE_ADMISSION_PROSPECTIVE)
    return (
        DISPOSITION_UNKNOWN_REQUIRES_REVIEW,
        f"UNMAPPED_INCLUSION:{inclusion_state}",
        RULE_FORENSIC_PIT,
    )


def build_item9_readiness_snapshot(
    receipt_dir: Path,
    *,
    imp_root: Path | None = None,
    authorization_state: str = AUTHORIZATION_ABSENT,
) -> dict[str, Any]:
    """Read-only readiness snapshot. Never fits; never mutates receipts."""

    root = imp_root or imp_package_root()
    gap_register = load_not_observed_gap_register(imp_root=root)
    gap_refuse = refuse_gap_synthesis(gap_register)

    if not receipt_dir.is_dir():
        return {
            "artifact_kind": SNAPSHOT_ARTIFACT_KIND,
            "schema_id": READINESS_SNAPSHOT_SCHEMA_ID,
            "protocol_version": PROTOCOL_VERSION,
            "bound_protocol_version": BOUND_PROTOCOL_VERSION,
            "receipt_dir": str(receipt_dir),
            "snapshot_status": FIELD_NOT_RUN,
            "receipt_dir_status": FIELD_UNAVAILABLE,
            "item9_status": ITEM9_STATUS_NOT_CALIBRATED,
            "calibration_state": CALIBRATION_STATE,
            "readiness_state": READINESS_STATE_UNSET,
            "calibrated": CALIBRATED_DEFAULT,
            "fitting_allowed": FITTING_ALLOWED_DEFAULT,
            "item9_calibration_run": ITEM9_CALIBRATION_RUN_FORBIDDEN,
            "authorization_state": authorization_state,
            "search_complexity_max": SEARCH_COMPLEXITY_MAX,
            "gap_register": gap_register,
            "gap_synthesis": gap_refuse,
            "mode_b_field_applicability": _mode_b_field_applicability(),
            "mode_b_field_applicability_rule": RULE_MODE_B_STRATEGY_N_A,
            "contract_freeze": contract_freeze_record(),
            "protocol_freeze": protocol_freeze_record(),
            "counts": {},
            "dispositions": [],
            "evaluation_boundary": {},
            "floors": {
                "minimum_calibration_samples": MINIMUM_CALIBRATION_SAMPLES,
                "minimum_distinct_rth_dates": MINIMUM_DISTINCT_RTH_DATES,
                "minimum_evaluation_rows": MINIMUM_EVALUATION_ROWS,
                "governing_rule_id": RULE_PROTOCOL_SAMPLE_FLOORS,
            },
        }

    audit = audit_receipt_directory(receipt_dir)
    paths = governed_receipt_paths(receipt_dir)

    # Duplicate file-content hashes (fail-closed accounting).
    hash_to_paths: dict[str, list[str]] = {}
    for path in paths:
        try:
            digest = _file_sha256(path)
        except OSError:
            continue
        hash_to_paths.setdefault(digest, []).append(str(path))
    duplicate_file_hashes = {
        digest: path_list
        for digest, path_list in hash_to_paths.items()
        if len(path_list) > 1
    }

    # Build admissible rows for split / fingerprints (unique experiment_id).
    seen_ids: set[str] = set()
    included_rows: list[dict[str, Any]] = []
    runtime_shas: Counter[str] = Counter()
    row_records: list[dict[str, Any]] = []
    compact_payloads: list[dict[str, Any]] = []

    for path in paths:
        payload, load_error = load_governed_receipt(path)
        if payload is None:
            row_records.append(
                {
                    "observation_id": "",
                    "path": str(path),
                    "disposition": DISPOSITION_EXCLUDED_WITH_REASON,
                    "reason": load_error or "LOAD_ERROR",
                    "rule": RULE_ADMISSION_PROSPECTIVE,
                    "inclusion_state": INCLUSION_INVALID,
                    "corpus_admissible": False,
                    "forensic_flags": [],
                    "lifecycle_role": None,
                }
            )
            continue

        classified = classify_item9_receipt(payload)
        obs_id = classified.observation_id
        forensic = _forensic_flags(payload, path=path)
        critical = any(f.get("severity") == "CRITICAL" for f in forensic)
        # Duplicate experiment_id after first seen → excluded
        duplicate_id = bool(obs_id and obs_id in seen_ids)
        if obs_id and not duplicate_id:
            seen_ids.add(obs_id)

        inclusion = classified.inclusion_state
        if duplicate_id:
            inclusion = INCLUSION_DUPLICATE
            forensic.append(
                {
                    "code": "DUPLICATE_EXPERIMENT_ID",
                    "severity": "CRITICAL",
                    "rule": RULE_FORENSIC_DUPLICATE_EXPERIMENT,
                }
            )
            critical = True

        sha = str(payload.get("runtime_git_sha") or "").strip()
        if sha and classified.corpus_admissible and not duplicate_id:
            runtime_shas[sha] += 1

        compact_payloads.append(_compact_admission_payload(payload))

        if (classified.corpus_admissible or classified.inclusion_state == INCLUSION_INCLUDED) and not duplicate_id:
            included_rows.append(build_dataset_row(payload, classification=classified))

        row_records.append(
            {
                "observation_id": obs_id,
                "path": str(path),
                "inclusion_state": inclusion,
                "exclusion_reason": classified.exclusion_reason,
                "corpus_admissible": bool(classified.corpus_admissible) and not duplicate_id,
                "forensic_flags": forensic,
                "critical_unknown": critical
                and classified.inclusion_state
                not in {INCLUSION_PATH_PROOF_ONLY, INCLUSION_EXCLUDED, INCLUSION_INVALID},
                "runtime_git_sha": sha or None,
                "signal_timestamp_ns": payload.get("signal_time_ns"),
                "_pending_disposition": True,
            }
        )

    gate = evaluate_sample_gate(included_rows)
    split = chronological_split(included_rows)
    evaluation_ids = set(split[SPLIT_EVALUATION])
    development_ids = set(split[SPLIT_DEVELOPMENT])
    selection_ids = set(split[SPLIT_SELECTION])

    # Holdout seal: evaluation ids must be absent from development and selection.
    holdout_leak = sorted(
        (evaluation_ids & development_ids) | (evaluation_ids & selection_ids)
    )
    untouched_eval_sealed = len(holdout_leak) == 0

    dispositions: list[dict[str, Any]] = []
    disposition_counts: Counter[str] = Counter()
    critical_unknown_ids: list[str] = []

    for record in row_records:
        obs_id = str(record.get("observation_id") or "")
        critical = bool(record.get("critical_unknown"))
        # PATH_PROOF_ONLY / EXCLUDED keep their dispositions even with forensic INFO flags.
        if record.get("inclusion_state") == INCLUSION_PATH_PROOF_ONLY:
            critical = False
        if record.get("inclusion_state") in {
            INCLUSION_EXCLUDED,
            INCLUSION_INVALID,
            INCLUSION_DUPLICATE,
        }:
            # Keep CRITICAL flags that are integrity failures on non-admissible rows
            # only when severity is CRITICAL and code is not merely NON_RTH already
            # accounted as exclusion — still block if UNKNOWN on unmapped.
            pass

        disposition, reason, rule = _map_disposition(
            inclusion_state=str(record.get("inclusion_state") or ""),
            observation_id=obs_id,
            evaluation_ids=evaluation_ids,
            critical_unknown=critical
            and str(record.get("inclusion_state") or "") == INCLUSION_INCLUDED,
        )
        # If admissible row has critical forensic beyond classifier, force UNKNOWN.
        if (
            str(record.get("inclusion_state") or "") == INCLUSION_INCLUDED
            and any(
                f.get("severity") == "CRITICAL"
                for f in (record.get("forensic_flags") or [])
            )
        ):
            disposition = DISPOSITION_UNKNOWN_REQUIRES_REVIEW
            reason = "CRITICAL_FORENSIC_FLAG"
            rule = RULE_FORENSIC_PIT
            critical_unknown_ids.append(obs_id)

        lifecycle_role = None
        if disposition == DISPOSITION_EVALUATION_ONLY:
            lifecycle_role = SPLIT_EVALUATION
        elif obs_id in development_ids:
            lifecycle_role = SPLIT_DEVELOPMENT
        elif obs_id in selection_ids:
            lifecycle_role = SPLIT_SELECTION

        # EVALUATION_ONLY rows remain corpus-admissible; do not double-count as exclusion.
        admissible_flag = bool(record.get("corpus_admissible"))
        if disposition == DISPOSITION_EVALUATION_ONLY:
            admissible_flag = True

        entry = {
            "observation_id": obs_id,
            "path": record.get("path"),
            "disposition": disposition,
            "reason": reason or record.get("exclusion_reason"),
            "rule": rule,
            "inclusion_state": record.get("inclusion_state"),
            "corpus_admissible": admissible_flag,
            "lifecycle_role": lifecycle_role,
            "forensic_flags": record.get("forensic_flags") or [],
            "runtime_git_sha": record.get("runtime_git_sha"),
            "signal_timestamp_ns": record.get("signal_timestamp_ns"),
            "mode_b_strategy_fields": FIELD_NOT_APPLICABLE,
            "mode_b_strategy_fields_rule": RULE_MODE_B_STRATEGY_N_A,
        }
        dispositions.append(entry)
        disposition_counts[disposition] += 1

    dates = sorted(
        {
            session_date_et(int(row["signal_timestamp_ns"]))
            for row in included_rows
            if row.get("signal_timestamp_ns")
        }
    )

    # Fingerprints cover canonical row identity + split membership (not mtimes).
    corpus_identity = sorted(
        {
            str(row.get("observation_id") or "")
            for row in included_rows
            if row.get("observation_id")
        }
    )
    corpus_fingerprint = _canonical_json_hash(
        {
            "observation_ids": corpus_identity,
            "protocol_version": PROTOCOL_VERSION,
            "dataset_schema_version": DATASET_SCHEMA_VERSION,
        }
    )
    evaluation_fingerprint = _canonical_json_hash(
        {
            "evaluation_ids": sorted(evaluation_ids),
            "split_fractions": [0.6, 0.2, 0.2],
            "ordering": "chronological_signal_time_then_observation_id",
        }
    )
    protocol_fingerprint = _canonical_json_hash(protocol_freeze_record())

    dual_corpus = build_item9_dual_corpus_audit(
        included_rows=included_rows,
        compact_payloads=compact_payloads,
        development_ids=development_ids,
        selection_ids=selection_ids,
        evaluation_ids=evaluation_ids,
        corpus_fingerprint=corpus_fingerprint,
    )

    counts = dict(audit["counts"])
    counts["evaluation_rows"] = len(evaluation_ids)
    counts["development_rows"] = len(development_ids)
    counts["selection_rows"] = len(selection_ids)
    counts["critical_unknown_requires_review"] = len(critical_unknown_ids)
    counts["duplicate_file_hash_groups"] = len(duplicate_file_hashes)
    for key, value in disposition_counts.items():
        counts[f"disposition_{key.lower()}"] = int(value)

    evaluation_boundary = {
        SPLIT_DEVELOPMENT: sorted(development_ids),
        SPLIT_SELECTION: sorted(selection_ids),
        SPLIT_EVALUATION: sorted(evaluation_ids),
        "split_fractions": [0.6, 0.2, 0.2],
        "shuffle": False,
        "untouched_evaluation_sealed": untouched_eval_sealed,
        "holdout_leak_ids": holdout_leak,
        "protocol_freeze_provenance": {
            "fixed_in_protocol_v1": True,
            "pr": "#234",
            "commit_hint": "f47b449a",
            "chosen_from_this_corpus": False,
            "governing_rule_id": RULE_PROTOCOL_V1_FREEZE,
        },
        "governing_rule_id": RULE_PROTOCOL_CHRONO_SPLIT,
        "untouched_eval_rule": RULE_UNTOUCHED_EVAL_SEAL,
    }

    return {
        "artifact_kind": SNAPSHOT_ARTIFACT_KIND,
        "schema_id": READINESS_SNAPSHOT_SCHEMA_ID,
        "protocol_version": PROTOCOL_VERSION,
        "bound_protocol_version": BOUND_PROTOCOL_VERSION,
        "dataset_schema_version": DATASET_SCHEMA_VERSION,
        "receipt_contract_version": RECEIPT_CONTRACT_VERSION,
        "simulator_version": SIMULATOR_VERSION,
        "cost_model_version": FIELD_NOT_OBSERVED,
        "fill_model_version": SIMULATOR_VERSION,
        "settlement_model_version": FIELD_NOT_OBSERVED,
        "receipt_dir": str(receipt_dir.resolve()),
        "snapshot_status": "COMPUTED",
        "receipt_dir_status": "PRESENT",
        "item9_status": ITEM9_STATUS_NOT_CALIBRATED,
        "calibration_state": CALIBRATION_STATE,
        "readiness_state": READINESS_STATE_UNSET,
        "calibrated": CALIBRATED_DEFAULT,
        "fitting_allowed": FITTING_ALLOWED_DEFAULT,
        "item9_calibration_run": ITEM9_CALIBRATION_RUN_FORBIDDEN,
        "authorization_state": authorization_state,
        "search_complexity_max": SEARCH_COMPLEXITY_MAX,
        "session_dates_rth": dates,
        "counts": counts,
        "disposition_counts": dict(disposition_counts),
        "dispositions": dispositions,
        "critical_unknown_observation_ids": critical_unknown_ids,
        "duplicate_file_hashes": duplicate_file_hashes,
        "duplicate_file_hash_rule": RULE_FORENSIC_DUPLICATE_HASH,
        "runtime_git_sha_by_count": dict(runtime_shas),
        "evaluation_boundary": evaluation_boundary,
        "sample_gate": gate,
        "corpus_fingerprint": corpus_fingerprint,
        "evaluation_fingerprint": evaluation_fingerprint,
        "protocol_fingerprint": protocol_fingerprint,
        "floors": {
            "minimum_calibration_samples": MINIMUM_CALIBRATION_SAMPLES,
            "minimum_distinct_rth_dates": MINIMUM_DISTINCT_RTH_DATES,
            "minimum_evaluation_rows": MINIMUM_EVALUATION_ROWS,
            "governing_rule_id": RULE_PROTOCOL_SAMPLE_FLOORS,
        },
        "gap_register": gap_register,
        "gap_synthesis": gap_refuse,
        "mode_b_field_applicability": _mode_b_field_applicability(),
        "mode_b_field_applicability_rule": RULE_MODE_B_STRATEGY_N_A,
        "default_receipt_dir_rel": str(DEFAULT_RECEIPT_DIR),
        "contract_freeze": contract_freeze_record(),
        "protocol_freeze": protocol_freeze_record(),
        "search_complexity_rule": RULE_PROTOCOL_SEARCH_COMPLEXITY_0,
        "dual_corpus": dual_corpus,
        "dual_corpus_role_map": dual_corpus["dual_corpus_role_map"],
        "toctou_binding": {
            "corpus_fingerprint": corpus_fingerprint,
            "evaluation_fingerprint": evaluation_fingerprint,
            "protocol_fingerprint": protocol_fingerprint,
            "governing_rule_id": RULE_TOCTOU_FINGERPRINT,
        },
    }


def resolve_governed_receipt_dir(
    *,
    receipt_dir: Path | None = None,
    imp_root: Path | None = None,
    prefer_frozen_collector: bool = True,
) -> Path:
    """Resolve receipt dir; optionally prefer frozen collector checkout when present."""

    root = imp_root or imp_package_root()
    if receipt_dir is not None:
        path = receipt_dir
        if not path.is_absolute():
            path = root / path
        return path

    if prefer_frozen_collector:
        from .item9_next_rth_preflight import (
            monorepo_root_from_imp,
            resolve_frozen_collector_imp_root,
        )

        frozen = resolve_frozen_collector_imp_root(root)
        if frozen is not None:
            candidate = frozen / DEFAULT_RECEIPT_DIR
            if candidate.is_dir():
                return candidate.resolve()
        # Also try monorepo sibling even if phase0 lock check failed
        mono = monorepo_root_from_imp(root)
        sibling = mono / ".imp-actual-01-phase-d" / "projects" / "integrated-market-platform" / DEFAULT_RECEIPT_DIR
        if sibling.is_dir():
            return sibling.resolve()

    return (root / DEFAULT_RECEIPT_DIR).resolve()


__all__ = [
    "GAP_REGISTER_REL",
    "SNAPSHOT_ARTIFACT_KIND",
    "build_item9_dual_corpus_audit",
    "build_item9_readiness_snapshot",
    "load_not_observed_gap_register",
    "refuse_gap_synthesis",
    "resolve_governed_receipt_dir",
]
