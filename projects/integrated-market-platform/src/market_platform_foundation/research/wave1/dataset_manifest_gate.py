"""ValidationDatasetManifestV1 dict gate without importing intelligence.validation (sklearn)."""

from __future__ import annotations

from typing import Any

from .errors import Wave1ExportGateError

_FTEP_BINDING_KEYS = (
    "campaign_slug",
    "ftep_campaign_id",
    "forward_test_session_id",
    "ftep_protocol_ref",
)
_FTEP_BINDING_KINDS = {"FTEP", "FORWARD_TEST_CAMPAIGN", "FTEP_CAMPAIGN"}


def require_clean_validation_dataset_manifest_dict(payload: dict[str, Any]) -> None:
    metadata = dict(payload.get("metadata") or {})
    reject_ftep_dataset_binding(metadata)
    violations = tuple(metadata.get("pit_violations") or ())
    if violations:
        raise Wave1ExportGateError(
            "W1_VALIDATION_DATASET_PIT_VIOLATION",
            details={"pit_violations": list(violations)},
        )
    for key in (
        "validation_dataset_id",
        "validation_plan_id",
        "fold_or_holdout_ref",
        "dataset_fingerprint",
        "target_kind",
        "horizon_ns",
        "mode",
    ):
        if not payload.get(key):
            raise Wave1ExportGateError("W1_VALIDATION_DATASET_FIELD_MISSING", details={"field": key})


def reject_ftep_dataset_binding(metadata: dict[str, Any] | None) -> None:
    payload = dict(metadata or {})
    binding = payload.get("experiment_binding")
    if isinstance(binding, dict):
        kind = str(binding.get("binding_kind", "")).upper()
        if kind in _FTEP_BINDING_KINDS or "FTEP" in kind:
            raise Wave1ExportGateError("W1_FTEP_BINDING_FORBIDDEN", details={"binding_kind": kind})
        for key in _FTEP_BINDING_KEYS:
            if binding.get(key):
                raise Wave1ExportGateError("W1_FTEP_BINDING_FORBIDDEN", details={"key": key})
    for key in _FTEP_BINDING_KEYS:
        if payload.get(key):
            raise Wave1ExportGateError("W1_FTEP_BINDING_FORBIDDEN", details={"key": key})
