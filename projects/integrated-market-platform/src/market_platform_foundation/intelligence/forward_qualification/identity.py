"""Deterministic forward qualification identities (BUILD 26)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .types import (
    FORWARD_QUALIFICATION_IMPLEMENTATION_VERSION,
    ForwardPredictionReceiptV1,
    ForwardQualificationRunV1,
    ForwardQualificationSpecV1,
)


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _sha256_prefix(prefix: str, payload: dict[str, Any]) -> str:
    digest = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    return f"{prefix}-{digest}"


def qualification_spec_identity_payload(spec: ForwardQualificationSpecV1) -> dict[str, Any]:
    return {
        "schema_version": spec.schema_version,
        "release_candidate_ref": spec.release_candidate_ref,
        "source_head": spec.source_head,
        "contract_inventory_hash": spec.contract_inventory_hash,
        "qualification_kind": spec.qualification_kind.value,
        "allowed_providers": list(spec.allowed_providers),
        "instrument_universe": list(spec.instrument_universe),
        "target_kind": spec.target_kind,
        "horizon_ns": spec.horizon_ns,
        "champion_scope": spec.champion_scope,
        "qualification_start_ns": spec.qualification_start_ns,
        "qualification_end_ns": spec.qualification_end_ns,
        "minimum_prediction_count": spec.minimum_prediction_count,
        "minimum_labelable_count": spec.minimum_labelable_count,
        "minimum_duration_ns": spec.minimum_duration_ns,
        "required_quality_states": list(spec.required_quality_states),
        "control_set": list(spec.control_set),
        "execution_mode_requirement": spec.execution_mode_requirement,
        "execution_authority_requirement": spec.execution_authority_requirement,
        "implementation_version": spec.implementation_version,
    }


def derive_qualification_spec_id(spec: ForwardQualificationSpecV1) -> str:
    return _sha256_prefix("FQSPEC", qualification_spec_identity_payload(spec))


def qualification_run_identity_payload(run: ForwardQualificationRunV1) -> dict[str, Any]:
    return {
        "schema_version": run.schema_version,
        "qualification_spec_ref": run.qualification_spec_ref,
        "release_candidate_ref": run.release_candidate_ref,
        "source_head": run.source_head,
        "runtime_activation_ref": run.runtime_activation_ref,
        "champion_assignment_ref": run.champion_assignment_ref,
        "provider_capability_snapshot": [entry.to_dict() for entry in run.provider_capability_snapshot],
        "instrument_universe": list(run.instrument_universe),
        "run_start_ns": run.run_start_ns,
        "data_mode": run.data_mode,
        "execution_mode": run.execution_mode,
        "execution_authority": run.execution_authority,
        "policy_stack_refs": list(run.policy_stack_refs),
        "implementation_version": run.implementation_version,
    }


def derive_qualification_run_id(run: ForwardQualificationRunV1) -> str:
    return _sha256_prefix("FQRUN", qualification_run_identity_payload(run))


def receipt_identity_payload(receipt: ForwardPredictionReceiptV1) -> dict[str, Any]:
    return {
        "schema_version": receipt.schema_version,
        "forecast_id": receipt.forecast_id,
        "ledger_entry_id": receipt.ledger_entry_id,
        "decision_time_ns": receipt.decision_time_ns,
        "target_time_ns": receipt.target_time_ns,
        "registered_at_ns": receipt.registered_at_ns,
        "recorded_at_ns": receipt.recorded_at_ns,
        "qualification_run_ref": receipt.qualification_run_ref,
        "evidence_class": receipt.evidence_class.value,
        "content_hash": receipt.content_hash,
        "implementation_version": FORWARD_QUALIFICATION_IMPLEMENTATION_VERSION,
    }


def derive_receipt_id(receipt: ForwardPredictionReceiptV1) -> str:
    return _sha256_prefix("FQPRCPT", receipt_identity_payload(receipt))


def derive_forward_cohort_fingerprint(
    *,
    forecast_ids: tuple[str, ...],
    ledger_entry_ids: tuple[str, ...],
    outcome_ids: tuple[str, ...],
) -> str:
    payload = {
        "forecast_ids": list(forecast_ids),
        "ledger_entry_ids": list(ledger_entry_ids),
        "outcome_ids": list(outcome_ids),
    }
    return _sha256_prefix("FQCOHORT", payload)


def derive_qualification_report_id(
    *,
    qualification_spec_id: str,
    qualification_run_id: str,
    cohort_fingerprint: str,
    evaluation_as_of_ns: int,
    implementation_version: str,
) -> str:
    payload = {
        "qualification_spec_id": qualification_spec_id,
        "qualification_run_id": qualification_run_id,
        "cohort_fingerprint": cohort_fingerprint,
        "evaluation_as_of_ns": evaluation_as_of_ns,
        "implementation_version": implementation_version,
    }
    return _sha256_prefix("FQREP", payload)


def derive_receipt_content_hash(
    *,
    forecast_id: str,
    ledger_entry_id: str,
    decision_time_ns: int,
    target_time_ns: int,
    registered_at_ns: int,
) -> str:
    payload = {
        "forecast_id": forecast_id,
        "ledger_entry_id": ledger_entry_id,
        "decision_time_ns": decision_time_ns,
        "target_time_ns": target_time_ns,
        "registered_at_ns": registered_at_ns,
    }
    digest = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    return digest
