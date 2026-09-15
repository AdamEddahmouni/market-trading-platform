"""Item 7 Phase 5.5B — machine review for corpus status/export artifacts.

Validates operator-exported Item 7 JSON without minting governed rows, promoting
production models, or asserting ``ITEM7_COMPLETE``.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Mapping

from ..contracts.common import IntelligenceScope, QualityState, QualitySummary, TimeHorizonNs
from .identity import path_a_horizon
from ..contracts.signal import SignalV1
from ..contracts.snapshot import SnapshotV1
from ..fusion.calibration_data import MINIMUM_CALIBRATION_SAMPLES, MINIMUM_CLASS_COUNT
from .corpus_collector import (
    LABEL_SOURCE_FIXTURE,
    LABEL_SOURCE_OUTCOME_V1,
    MANIFEST_CANDIDATE_KIND,
    PIT_VALIDATED_CORPUS_KIND,
    assert_not_governed_production_manifest,
    pit_validate_candidate,
)
from .identity import MINIMUM_SPECIALIST_CLASS_COUNT, MINIMUM_SPECIALIST_SAMPLES

VALIDATOR_VERSION = "1.0.0"
VALIDATOR_ARTIFACT_KIND = "item7_corpus_evidence_validation_v1"

STATUS_ARTIFACT_KIND = "item7_path_a_corpus_collection_report_v1"

CAPTURE_CONTEXT_SCHEMA_VERSION = "1.0.0"
CAPTURE_CONTEXT_ARTIFACT_KIND = "evidence_capture_context_v1"

FORBIDDEN_GATE_ASSERTIONS = frozenset(
    {
        "ITEM7_COMPLETE",
        "GOVERNED_PATH_A_TRAINING_CORPUS_READY",
        "PRODUCTION_FORECAST_ARTIFACT_READY",
    }
)


class CorpusEvidenceVerdict(StrEnum):
    VALID = "VALID"
    VALID_WITH_LIMITATIONS = "VALID_WITH_LIMITATIONS"
    INVALID = "INVALID"


@dataclass(frozen=True, slots=True)
class CorpusEvidenceValidationReport:
    verdict: CorpusEvidenceVerdict
    reasons: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    gate_signals: tuple[str, ...] = ()
    evidence_class: str = "SOFTWARE"
    item7_status: str = "PARTIAL"
    governed_candidate_rows: int | None = None
    pit_valid_governed_rows: int | None = None
    fixture_only_rows: int | None = None
    class_counts_governed: dict[str, int | None] | None = None
    pit_export_row_count: int | None = None
    pit_export_governed_row_count: int | None = None
    specialist_floor_met: bool | None = None
    calibration_floor_met: bool | None = None
    manifest_state: str | None = None
    production_artifact_status: str | None = None
    capture_context_verified: bool | None = None
    validator_version: str = VALIDATOR_VERSION

    def to_dict(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "artifact_kind": VALIDATOR_ARTIFACT_KIND,
            "validator_version": self.validator_version,
            "verdict": self.verdict.value,
            "reasons": list(self.reasons),
            "limitations": list(self.limitations),
            "gate_signals": list(self.gate_signals),
            "evidence_class": self.evidence_class,
            "item7_status": self.item7_status,
        }
        if self.governed_candidate_rows is not None:
            body["governed_candidate_rows"] = self.governed_candidate_rows
        if self.pit_valid_governed_rows is not None:
            body["pit_valid_governed_rows"] = self.pit_valid_governed_rows
        if self.fixture_only_rows is not None:
            body["fixture_only_rows"] = self.fixture_only_rows
        if self.class_counts_governed is not None:
            body["class_counts_governed"] = self.class_counts_governed
        if self.pit_export_row_count is not None:
            body["pit_export_row_count"] = self.pit_export_row_count
        if self.pit_export_governed_row_count is not None:
            body["pit_export_governed_row_count"] = self.pit_export_governed_row_count
        if self.specialist_floor_met is not None:
            body["specialist_floor_met"] = self.specialist_floor_met
        if self.calibration_floor_met is not None:
            body["calibration_floor_met"] = self.calibration_floor_met
        if self.manifest_state is not None:
            body["manifest_state"] = self.manifest_state
        if self.production_artifact_status is not None:
            body["production_artifact_status"] = self.production_artifact_status
        if self.capture_context_verified is not None:
            body["capture_context_verified"] = self.capture_context_verified
        return body


def _load_json(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _optional_int(payload: Mapping[str, Any], key: str) -> int | None:
    if key not in payload:
        return None
    value = payload.get(key)
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _present_int(payload: Mapping[str, Any], key: str) -> int | None:
    if key not in payload:
        return None
    return _optional_int(payload, key)


def _optional_class_counts(payload: Mapping[str, Any]) -> dict[str, int | None] | None:
    raw = payload.get("class_counts_governed")
    if raw is None:
        return None
    if not isinstance(raw, dict):
        return {"0": None, "1": None}
    return {
        "0": _optional_int(raw, "0"),
        "1": _optional_int(raw, "1"),
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_capture_context(
    *,
    context: Mapping[str, Any],
    artifact_paths: dict[str, Path],
) -> tuple[bool, tuple[str, ...], tuple[str, ...]]:
    reasons: list[str] = []
    limitations: list[str] = []
    kind = str(context.get("artifact_kind") or "")
    if kind and kind != CAPTURE_CONTEXT_ARTIFACT_KIND:
        reasons.append("CAPTURE_CONTEXT_KIND_UNEXPECTED")
    schema = str(context.get("schema_version") or "")
    if schema and schema != CAPTURE_CONTEXT_SCHEMA_VERSION:
        limitations.append("CAPTURE_CONTEXT_SCHEMA_VERSION_UNRECOGNIZED")
    artifact_path_raw = context.get("artifact_path")
    artifact_sha = str(context.get("artifact_sha256") or "").lower()
    if artifact_path_raw and artifact_sha:
        resolved = Path(str(artifact_path_raw))
        if not resolved.is_file():
            for candidate in artifact_paths.values():
                if candidate.name == resolved.name:
                    resolved = candidate
                    break
        if resolved.is_file():
            actual = _sha256_file(resolved)
            if actual != artifact_sha:
                reasons.append("CAPTURE_CONTEXT_ARTIFACT_HASH_MISMATCH")
        else:
            reasons.append("CAPTURE_CONTEXT_ARTIFACT_PATH_MISSING")
    elif artifact_sha:
        limitations.append("CAPTURE_CONTEXT_ARTIFACT_PATH_MISSING")
    artifact_evidence = str(context.get("evidence_class") or "").upper()
    if artifact_evidence and artifact_evidence not in {"SOFTWARE", "FIXTURE", "REPLAY"}:
        limitations.append("CAPTURE_CONTEXT_EVIDENCE_CLASS_UNRECOGNIZED")
    if context.get("orders_placed") not in (None, 0, False):
        reasons.append("CAPTURE_CONTEXT_ORDERS_NONZERO")
    if context.get("empirical_lock_created") not in (None, 0, False, False):
        reasons.append("CAPTURE_CONTEXT_EMPIRICAL_LOCK_PRESENT")
    return (not reasons, tuple(dict.fromkeys(reasons)), tuple(dict.fromkeys(limitations)))


def _sidecar_would_upgrade_evidence(
    *,
    status: Mapping[str, Any] | None,
    pit_export: Mapping[str, Any] | None,
    context: Mapping[str, Any],
) -> bool:
    sidecar_class = str(context.get("evidence_class") or "").upper()
    if sidecar_class in {"", "SOFTWARE", "FIXTURE", "REPLAY"}:
        return False
    if sidecar_class not in {"PROSPECTIVE", "EMPIRICAL", "LIVE"}:
        return False
    if status is not None:
        fixture_rows = _optional_int(status, "fixture_only_rows")
        pit_governed = _optional_int(status, "pit_valid_governed_rows")
        if (fixture_rows or 0) > 0 and (pit_governed or 0) <= 0:
            return True
    production_claim = pit_export.get("production_claim") if pit_export else None
    if production_claim is True:
        return True
    return False


def _pit_inputs_from_export_row(row: Mapping[str, Any]) -> tuple[SnapshotV1, tuple[SignalV1, ...], int, str, int] | None:
    try:
        decision = int(row["decision_time_ns"])
        label = int(row["label"])
        label_source = str(row["label_source"])
        label_available = int(row["label_available_time_ns"])
        snapshot_id = str(row["snapshot_id"])
        momentum = float(row["momentum"])
        nss = float(row["net_signed_share"])
    except (KeyError, TypeError, ValueError):
        return None
    horizon_ns = int(row.get("horizon_duration_ns") or path_a_horizon().duration_ns)
    scope = IntelligenceScope(
        instrument_ids=("canonical:EQUITY:XNYS:AAPL",),
        context_id="item7-corpus-evidence-validator",
    )
    quality = QualitySummary(state=QualityState.GOOD)
    snapshot = SnapshotV1(
        snapshot_id=snapshot_id,
        schema_version="1",
        decision_time_ns=decision,
        scope=scope,
        quality=quality,
    )
    window = TimeHorizonNs(duration_ns=horizon_ns)
    lineage = row.get("feature_lineage")
    calc_mom = ("momentum-calculator", "1")
    calc_nss = ("cvd-calculator", "1")
    if isinstance(lineage, list):
        for item in lineage:
            if not isinstance(item, dict):
                continue
            signal_type = str(item.get("signal_type") or "")
            calc_id = str(item.get("calculator_id") or "")
            calc_ver = str(item.get("calculator_version") or "")
            if signal_type == "momentum_simple" and calc_id:
                calc_mom = (calc_id, calc_ver or "1")
            if signal_type == "net_signed_share" and calc_id:
                calc_nss = (calc_id, calc_ver or "1")
    from ..contracts.common import ContractKind, ContractReference

    ref = ContractReference(kind=ContractKind.SNAPSHOT.value, id=snapshot_id)
    signals = (
        SignalV1(
            signal_id=f"{snapshot_id}-mom",
            schema_version="1",
            signal_type="momentum_simple",
            scope=scope,
            as_of_time_ns=decision,
            value=momentum,
            quality=quality,
            source_snapshot_ref=ref,
            calculation_window=window,
            calculation_lineage={"calculator_id": calc_mom[0], "calculator_version": calc_mom[1]},
            unit="decimal_return",
        ),
        SignalV1(
            signal_id=f"{snapshot_id}-nss",
            schema_version="1",
            signal_type="net_signed_share",
            scope=scope,
            as_of_time_ns=decision,
            value=nss,
            quality=quality,
            source_snapshot_ref=ref,
            calculation_window=window,
            calculation_lineage={"calculator_id": calc_nss[0], "calculator_version": calc_nss[1]},
        ),
    )
    return snapshot, signals, label, label_source, label_available


def _validate_governed_row_requirements(row: Mapping[str, Any]) -> tuple[str, ...]:
    reasons: list[str] = []
    label_source = str(row.get("label_source") or "")
    if label_source != LABEL_SOURCE_OUTCOME_V1:
        reasons.append("GOVERNED_ROW_LABEL_SOURCE_INVALID")
    if label_source == LABEL_SOURCE_FIXTURE:
        reasons.append("FIXTURE_ROW_NOT_GOVERNED")
    if row.get("pit_passed") is not True:
        reasons.append("ROW_PIT_NOT_PASSED")
    decision = row.get("decision_time_ns")
    label_available = row.get("label_available_time_ns")
    if not isinstance(decision, int) or decision <= 0:
        reasons.append("DECISION_TIME_INVALID")
    if not isinstance(label_available, int) or label_available <= 0:
        reasons.append("LABEL_AVAILABLE_TIME_INVALID")
    horizon = row.get("horizon_duration_ns")
    if isinstance(decision, int) and isinstance(label_available, int) and isinstance(horizon, int):
        if label_available < decision + horizon:
            reasons.append("LABEL_BEFORE_HORIZON_COMPLETION")
    lineage = row.get("feature_lineage")
    if not isinstance(lineage, list) or not lineage:
        reasons.append("FEATURE_LINEAGE_MISSING")
    provider = str(row.get("provider_id") or "").strip()
    dataset = str(row.get("dataset_id") or "").strip()
    if not provider and not dataset:
        reasons.append("PROVIDER_OR_DATASET_IDENTITY_MISSING")
    if row.get("production_claim") is True:
        reasons.append("PRODUCTION_CLAIM_FORBIDDEN")
    return tuple(dict.fromkeys(reasons))


def _revalidate_row_with_pit_validate_candidate(
    row: Mapping[str, Any],
    *,
    training_cutoff_ns: int | None,
) -> tuple[bool, tuple[str, ...]]:
    parsed = _pit_inputs_from_export_row(row)
    if parsed is None:
        return False, ("PIT_REPLAY_INPUTS_INCOMPLETE",)
    snapshot, signals, label, label_source, label_available = parsed
    ok, pit_reasons = pit_validate_candidate(
        snapshot=snapshot,
        signals=signals,
        label=label,
        label_source=label_source,
        label_available_time_ns=label_available,
        training_cutoff_ns=training_cutoff_ns,
    )
    structural = _validate_governed_row_requirements(row)
    if structural:
        return False, tuple(dict.fromkeys((*structural, *pit_reasons)))
    if not ok:
        return False, pit_reasons
    if row.get("pit_passed") is True and pit_reasons:
        return False, ("EXPORT_PIT_FLAG_MISMATCH", *pit_reasons)
    return True, ()


def validate_item7_corpus_evidence_bundle(
    *,
    status: Mapping[str, Any] | None,
    collection_report: Mapping[str, Any] | None = None,
    pit_validated_export: Mapping[str, Any] | None = None,
    capture_context: Mapping[str, Any] | None = None,
    artifact_paths: dict[str, Path] | None = None,
) -> CorpusEvidenceValidationReport:
    """Validate Item 7 export artifacts for independent machine review."""

    reasons: list[str] = []
    limitations: list[str] = []
    gate_signals: list[str] = []
    paths = dict(artifact_paths or {})

    corpus_status = status if status is not None else collection_report
    if corpus_status is None and pit_validated_export is None:
        return CorpusEvidenceValidationReport(
            verdict=CorpusEvidenceVerdict.INVALID,
            reasons=("NO_INPUT_ARTIFACTS",),
        )

    governed_rows = _present_int(corpus_status or {}, "governed_candidate_rows") if corpus_status else None
    pit_valid_rows = _present_int(corpus_status or {}, "pit_valid_governed_rows") if corpus_status else None
    fixture_rows = _present_int(corpus_status or {}, "fixture_only_rows") if corpus_status else None
    class_counts = _optional_class_counts(corpus_status or {}) if corpus_status else None
    manifest_state = None
    production_status = None
    if corpus_status is not None:
        if str(corpus_status.get("artifact_kind") or "") not in {"", STATUS_ARTIFACT_KIND}:
            reasons.append("STATUS_ARTIFACT_KIND_UNEXPECTED")
        acceptance = str(corpus_status.get("acceptance_label") or corpus_status.get("status") or "")
        if acceptance in FORBIDDEN_GATE_ASSERTIONS:
            reasons.append("FORBIDDEN_ACCEPTANCE_LABEL")
        if "ITEM7_COMPLETE" in acceptance.upper():
            reasons.append("ITEM7_COMPLETE_FORBIDDEN")
        manifest_state = str(corpus_status.get("governed_training_manifest_status") or "") or None
        production_status = str(corpus_status.get("production_artifact_status") or "") or None
        if production_status and production_status not in {
            "PRODUCTION_FORECAST_BLOCKED_NO_GOVERNED_PATH_A_TRAINING_CORPUS",
            "PRODUCTION_FORECAST_ARTIFACT_READY",
        }:
            limitations.append("PRODUCTION_ARTIFACT_STATUS_UNRECOGNIZED")

    pit_export_rows: list[Mapping[str, Any]] = []
    pit_export_governed = 0
    training_cutoff_ns: int | None = None
    if pit_validated_export is not None:
        kind = str(pit_validated_export.get("artifact_kind") or "")
        if kind != PIT_VALIDATED_CORPUS_KIND:
            reasons.append("PIT_EXPORT_KIND_UNEXPECTED")
        if pit_validated_export.get("production_claim") is True:
            reasons.append("PIT_EXPORT_PRODUCTION_CLAIM_FORBIDDEN")
        training_cutoff_ns = _optional_int(pit_validated_export, "training_cutoff_ns")
        raw_rows = pit_validated_export.get("rows")
        if isinstance(raw_rows, list):
            pit_export_rows = [row for row in raw_rows if isinstance(row, dict)]
        elif raw_rows is not None:
            reasons.append("PIT_EXPORT_ROWS_NOT_LIST")

    pit_export_row_count = len(pit_export_rows) if pit_validated_export is not None else None
    pit_export_governed_count: int | None = None
    if pit_validated_export is not None:
        pit_export_governed_count = 0
        for row in pit_export_rows:
            if str(row.get("label_source") or "") == LABEL_SOURCE_FIXTURE:
                reasons.append("FIXTURE_ROW_IN_PIT_EXPORT")
                continue
            pit_export_governed_count += 1
            row_ok, row_reasons = _revalidate_row_with_pit_validate_candidate(
                row,
                training_cutoff_ns=training_cutoff_ns,
            )
            if not row_ok:
                reasons.extend(row_reasons)

    if pit_valid_rows is not None and pit_export_governed_count is not None:
        if pit_valid_rows != pit_export_governed_count:
            reasons.append("PIT_ROW_COUNT_MISMATCH_STATUS_VS_EXPORT")

    specialist_floor_met: bool | None = None
    calibration_floor_met: bool | None = None
    if pit_export_rows:
        class_0 = sum(1 for row in pit_export_rows if row.get("label") == 0 and row.get("label_source") != LABEL_SOURCE_FIXTURE)
        class_1 = sum(1 for row in pit_export_rows if row.get("label") == 1 and row.get("label_source") != LABEL_SOURCE_FIXTURE)
        total = class_0 + class_1
        specialist_floor_met = (
            total >= MINIMUM_SPECIALIST_SAMPLES
            and class_0 >= MINIMUM_SPECIALIST_CLASS_COUNT
            and class_1 >= MINIMUM_SPECIALIST_CLASS_COUNT
        )
        calibration_floor_met = (
            total >= MINIMUM_CALIBRATION_SAMPLES
            and class_0 >= MINIMUM_CLASS_COUNT
            and class_1 >= MINIMUM_CLASS_COUNT
        )
        if class_counts is not None:
            reported_0 = class_counts.get("0")
            reported_1 = class_counts.get("1")
            if reported_0 is not None and reported_0 != class_0:
                reasons.append("CLASS_0_COUNT_MISMATCH")
            if reported_1 is not None and reported_1 != class_1:
                reasons.append("CLASS_1_COUNT_MISMATCH")

    if corpus_status is not None and "training_manifest_candidate.json" in paths:
        manifest_payload = _load_json(paths["training_manifest_candidate.json"])
        if manifest_payload is not None:
            manifest_reasons = assert_not_governed_production_manifest(manifest_payload)
            if not manifest_reasons:
                reasons.append("MANIFEST_CANDIDATE_APPEARS_GOVERNED")
            manifest_kind = str(manifest_payload.get("artifact_kind") or "")
            if manifest_kind == MANIFEST_CANDIDATE_KIND and manifest_payload.get("production_claim") is True:
                reasons.append("MANIFEST_CANDIDATE_PRODUCTION_CLAIM")

    capture_verified: bool | None = None
    if capture_context is not None:
        if _sidecar_would_upgrade_evidence(status=corpus_status, pit_export=pit_validated_export, context=capture_context):
            reasons.append("CAPTURE_CONTEXT_EVIDENCE_CLASS_UPGRADE_FORBIDDEN")
        verified, ctx_reasons, ctx_limits = _verify_capture_context(context=capture_context, artifact_paths=paths)
        capture_verified = verified
        reasons.extend(ctx_reasons)
        limitations.extend(ctx_limits)
    elif paths:
        limitations.append("CAPTURE_CONTEXT_ABSENT")

    if pit_valid_rows is not None and pit_valid_rows > 0:
        gate_signals.append("AT_LEAST_ONE_GOVERNED_PIT_VALID_ROW_PRESENT")
    elif pit_export_governed_count is not None and pit_export_governed_count > 0:
        gate_signals.append("AT_LEAST_ONE_GOVERNED_PIT_VALID_ROW_PRESENT")

    if "ITEM7_COMPLETE" in gate_signals:
        reasons.append("FORBIDDEN_GATE_SIGNAL")

    unique_reasons = tuple(dict.fromkeys(reasons))
    unique_limits = tuple(dict.fromkeys(limitations))
    if unique_reasons:
        verdict = CorpusEvidenceVerdict.INVALID
    elif unique_limits:
        verdict = CorpusEvidenceVerdict.VALID_WITH_LIMITATIONS
    else:
        verdict = CorpusEvidenceVerdict.VALID

    return CorpusEvidenceValidationReport(
        verdict=verdict,
        reasons=unique_reasons,
        limitations=unique_limits,
        gate_signals=tuple(dict.fromkeys(gate_signals)),
        governed_candidate_rows=governed_rows,
        pit_valid_governed_rows=pit_valid_rows,
        fixture_only_rows=fixture_rows,
        class_counts_governed=class_counts,
        pit_export_row_count=pit_export_row_count,
        pit_export_governed_row_count=pit_export_governed_count,
        specialist_floor_met=specialist_floor_met,
        calibration_floor_met=calibration_floor_met,
        manifest_state=manifest_state,
        production_artifact_status=production_status,
        capture_context_verified=capture_verified,
    )


def validate_item7_corpus_evidence_paths(
    *,
    status_path: Path | None = None,
    collection_report_path: Path | None = None,
    pit_validated_export_path: Path | None = None,
    capture_context_path: Path | None = None,
    export_dir: Path | None = None,
) -> CorpusEvidenceValidationReport:
    paths: dict[str, Path] = {}
    if export_dir is not None:
        for name in (
            "collection_report.json",
            "pit_validated_corpus.json",
            "candidate_corpus.json",
            "training_manifest_candidate.json",
        ):
            candidate = export_dir / name
            if candidate.is_file():
                paths[name] = candidate
    if status_path is not None:
        paths["status.json"] = status_path
    if collection_report_path is not None:
        paths["collection_report.json"] = collection_report_path
    if pit_validated_export_path is not None:
        paths["pit_validated_corpus.json"] = pit_validated_export_path
    context = _load_json(capture_context_path) if capture_context_path else None
    status = _load_json(status_path) if status_path else None
    collection = _load_json(collection_report_path) if collection_report_path else None
    if collection is None and "collection_report.json" in paths:
        collection = _load_json(paths["collection_report.json"])
    if status is None and collection is not None:
        status = collection
    pit_export = _load_json(pit_validated_export_path) if pit_validated_export_path else None
    if pit_export is None and "pit_validated_corpus.json" in paths:
        pit_export = _load_json(paths["pit_validated_corpus.json"])
    return validate_item7_corpus_evidence_bundle(
        status=status,
        collection_report=collection,
        pit_validated_export=pit_export,
        capture_context=context,
        artifact_paths=paths,
    )


__all__ = [
    "CAPTURE_CONTEXT_ARTIFACT_KIND",
    "CorpusEvidenceValidationReport",
    "CorpusEvidenceVerdict",
    "VALIDATOR_ARTIFACT_KIND",
    "validate_item7_corpus_evidence_bundle",
    "validate_item7_corpus_evidence_paths",
]
