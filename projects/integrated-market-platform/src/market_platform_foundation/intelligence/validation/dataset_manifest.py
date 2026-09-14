"""PIT dataset-manifest wrap over BUILD 19 walk-forward / locked holdout.

Wraps scored fold and holdout rows into ``ValidationDatasetManifestV1`` with a
declared temporal cutoff bundle. This is not a second backtester and must not
bind FTEP campaigns.
"""

from __future__ import annotations

from typing import Any

from ..contracts.common import INTELLIGENCE_SCHEMA_VERSION
from .errors import ValidationError
from .identity import derive_validation_dataset_fingerprint, derive_validation_dataset_id
from .types import ValidationDatasetManifestV1, ValidationExample, ValidationPlanV1

_FTEP_BINDING_KEYS = (
    "campaign_slug",
    "ftep_campaign_id",
    "forward_test_session_id",
    "ftep_protocol_ref",
)
_FTEP_BINDING_KINDS = {"FTEP", "FORWARD_TEST_CAMPAIGN", "FTEP_CAMPAIGN"}


def reject_ftep_dataset_binding(metadata: dict[str, Any] | None) -> None:
    """Fail closed if a validation dataset tries to attach a FTEP campaign."""
    payload = dict(metadata or {})
    binding = payload.get("experiment_binding")
    if isinstance(binding, dict):
        kind = str(binding.get("binding_kind", "")).upper()
        if kind in _FTEP_BINDING_KINDS or "FTEP" in kind:
            raise ValidationError("FTEP_BINDING_FORBIDDEN", details={"binding_kind": kind})
        for key in _FTEP_BINDING_KEYS:
            if binding.get(key):
                raise ValidationError("FTEP_BINDING_FORBIDDEN", details={"key": key})
    for key in _FTEP_BINDING_KEYS:
        if payload.get(key):
            raise ValidationError("FTEP_BINDING_FORBIDDEN", details={"key": key})


def assess_validation_dataset_pit(
    examples: tuple[ValidationExample, ...],
    *,
    decision_start_ns: int,
    decision_end_ns: int,
) -> tuple[str, ...]:
    """Return leak codes for rows that violate the declared decision window."""
    if decision_start_ns >= decision_end_ns:
        raise ValidationError(
            "VALIDATION_DATASET_WINDOW_INVALID",
            details={"decision_start_ns": decision_start_ns, "decision_end_ns": decision_end_ns},
        )
    codes: list[str] = []
    for example in examples:
        if example.label_available_time_ns <= example.decision_time_ns:
            codes.append("FUTURE_LABEL_ACCESS")
        elif not (decision_start_ns <= example.decision_time_ns < decision_end_ns):
            codes.append("VALIDATION_WINDOW_MISMATCH")
    return tuple(codes)


def build_validation_dataset_manifest(
    plan: ValidationPlanV1,
    *,
    fold_or_holdout_ref: str,
    examples: tuple[ValidationExample, ...],
    decision_start_ns: int,
    decision_end_ns: int,
    training_cutoff_ns: int | None = None,
    training_start_ns: int | None = None,
    extra_metadata: dict[str, Any] | None = None,
) -> ValidationDatasetManifestV1:
    """Bind scored examples to a hash-stable PIT dataset wrap.

    Membership fingerprint (``VALDS``) stays the existing fold/holdout
    identity. ``VALSET`` additionally binds the temporal cutoff bundle and
    BUILD-07 scenario identity without executing replay.
    """
    if not fold_or_holdout_ref:
        raise ValidationError("VALIDATION_DATASET_REF_REQUIRED")
    metadata = dict(extra_metadata or {})
    reject_ftep_dataset_binding(metadata)
    reject_ftep_dataset_binding(plan.metadata)

    pit_violations = assess_validation_dataset_pit(
        examples,
        decision_start_ns=decision_start_ns,
        decision_end_ns=decision_end_ns,
    )
    forecast_ids = tuple(ex.forecast_id for ex in examples if ex.forecast_id)
    outcome_ids = tuple(ex.outcome_id for ex in examples if ex.outcome_id)
    fingerprint = derive_validation_dataset_fingerprint(
        validation_plan_id=plan.validation_plan_id,
        fold_or_holdout_ref=fold_or_holdout_ref,
        forecast_ids=forecast_ids,
        outcome_ids=outcome_ids,
        decision_start_ns=decision_start_ns,
        decision_end_ns=decision_end_ns,
    )
    walk_forward_mode = (
        plan.walk_forward_spec.mode.value if plan.walk_forward_spec is not None else None
    )
    dataset_id = derive_validation_dataset_id(
        dataset_fingerprint=fingerprint,
        training_cutoff_ns=training_cutoff_ns,
        training_start_ns=training_start_ns,
        purge_ns=plan.purge_ns,
        embargo_ns=plan.embargo_ns,
        scenario_id=plan.scenario_id,
        walk_forward_mode=walk_forward_mode,
    )
    wrap_metadata: dict[str, Any] = {
        "source_kind": "LOCKED_HOLDOUT" if fold_or_holdout_ref == "holdout" else "WALK_FORWARD_FOLD",
        "purge_ns": plan.purge_ns,
        "embargo_ns": plan.embargo_ns,
        "training_cutoff_ns": training_cutoff_ns,
        "training_start_ns": training_start_ns,
        "walk_forward_mode": walk_forward_mode,
        "replay_scenario_id": plan.scenario_id,
        "replay_mode": plan.mode,
        "pit_violations": list(pit_violations),
        "example_count": len(examples),
    }
    wrap_metadata.update(metadata)
    return ValidationDatasetManifestV1(
        validation_dataset_id=dataset_id,
        schema_version=INTELLIGENCE_SCHEMA_VERSION,
        validation_plan_id=plan.validation_plan_id,
        fold_or_holdout_ref=fold_or_holdout_ref,
        decision_start_ns=decision_start_ns,
        decision_end_ns=decision_end_ns,
        forecast_ids=forecast_ids,
        outcome_ids=outcome_ids,
        dataset_fingerprint=fingerprint,
        target_kind=plan.target_kind,
        horizon_ns=plan.horizon_ns,
        mode=plan.mode,
        scenario_id=plan.scenario_id,
        metadata=wrap_metadata,
    )


def require_clean_validation_dataset_manifest(manifest: ValidationDatasetManifestV1) -> None:
    reject_ftep_dataset_binding(manifest.metadata)
    violations = tuple(manifest.metadata.get("pit_violations") or ())
    if violations:
        raise ValidationError(
            "INVALID_TEMPORAL_LEAKAGE",
            details={
                "fold_or_holdout_ref": manifest.fold_or_holdout_ref,
                "pit_violations": list(violations),
            },
        )


__all__ = [
    "assess_validation_dataset_pit",
    "build_validation_dataset_manifest",
    "reject_ftep_dataset_binding",
    "require_clean_validation_dataset_manifest",
]
