"""Loading a validation case from a declarative, offline case spec.

The spec is data, not code: it names artifacts, original field states, rule
classifications, and a replay operation. It cannot introduce a value the models would
otherwise reject -- in particular it cannot give a value to an unrecovered original
field, because OriginalFieldValue forbids that at construction.
"""

import json
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from squeeze_core.contracts import Observation

from .case_builder import build_validation_case
from .detection_time import build_detection_time_evidence, replay_boundaries
from .models import (
    ArtifactAvailability,
    ArtifactReliabilityClass,
    OriginalFieldValue,
    OriginalValueState,
    RuleValidationState,
    ValidationArtifact,
    ValidationCase,
)
from .original_rules import ORIGINAL_RULES
from .original_snapshot import build_original_snapshot
from .outcomes import unobserved_outcome
from .replay import build_boundary_replays
from .rule_validation import build_rule_validation


def _parse_time(value: Any) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"timestamp must be an ISO-8601 string, got {type(value).__name__}")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _artifact(raw: dict[str, Any]) -> ValidationArtifact:
    return ValidationArtifact(
        artifact_id=raw["artifact_id"],
        artifact_type=raw["artifact_type"],
        repository_or_source=raw["repository_or_source"],
        relative_path=raw["relative_path"],
        content_hash=raw.get("content_hash"),
        availability=ArtifactAvailability(raw.get("availability", "AVAILABLE")),
        created_time_if_known=_parse_time(raw.get("created_time_if_known")),
        modified_time_if_known=_parse_time(raw.get("modified_time_if_known")),
        embedded_event_time_if_known=_parse_time(raw.get("embedded_event_time_if_known")),
        timezone_if_known=raw.get("timezone_if_known"),
        reliability_class=ArtifactReliabilityClass(raw.get("reliability_class", "UNKNOWN")),
        limitations=tuple(raw.get("limitations", ())),
        sensitive=bool(raw.get("sensitive", False)),
        included_in_public_demo=bool(raw.get("included_in_public_demo", False)),
        bounds_detection_event=bool(raw.get("bounds_detection_event", True)),
    )


def _original_field(raw: dict[str, Any]) -> OriginalFieldValue:
    return OriginalFieldValue(
        field_id=raw["field_id"],
        display_label=raw.get("display_label"),
        internal_field_name=raw.get("internal_field_name"),
        state=OriginalValueState(raw.get("state", "UNKNOWN")),
        value=raw.get("value"),
        unit=raw.get("unit"),
        provider=raw.get("provider"),
        source_timestamp=_parse_time(raw.get("source_timestamp")),
        substituted_default=raw.get("substituted_default"),
        ambiguity_note=raw.get("ambiguity_note"),
        source_artifact_ids=tuple(raw.get("source_artifact_ids", ())),
    )


def load_case_spec(path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError("case spec must be a JSON object")
    for required in ("case_id", "symbol"):
        if required not in document:
            raise ValueError(f"case spec is missing required field: {required}")
    return document


def build_case_from_spec(
    spec: dict[str, Any],
    observations: Sequence[Observation] = (),
) -> ValidationCase:
    artifacts = tuple(_artifact(raw) for raw in spec.get("artifacts", ()))

    detection_spec = spec.get("detection_time", {})
    detection = build_detection_time_evidence(
        spec["symbol"],
        artifacts,
        timezone_label=detection_spec.get("timezone_label"),
        confidence_basis=detection_spec.get("confidence_basis"),
        evidence_notes=tuple(detection_spec.get("evidence_notes", ())),
    )

    fields = tuple(_original_field(raw) for raw in spec.get("original_fields", ()))
    snapshot = build_original_snapshot(
        spec["symbol"],
        fields,
        detection_time_evidence_id=detection.deterministic_id,
        source_artifact_ids=tuple(spec.get("snapshot_source_artifact_ids", ())),
    )

    replay_spec = spec.get("replay", {})
    replays = build_boundary_replays(
        spec["symbol"],
        observations,
        replay_boundaries(detection),
        operation=replay_spec.get("operation"),
        policy_version=replay_spec.get("policy_version"),
    )

    validations = tuple(
        build_rule_validation(
            raw["rule_id"],
            RuleValidationState(raw["state"]),
            raw["rationale"],
            corrections_required=tuple(raw.get("corrections_required", ())),
            supporting_artifact_ids=tuple(raw.get("supporting_artifact_ids", ())),
            supporting_field_ids=tuple(raw.get("supporting_field_ids", ())),
        )
        for raw in spec.get("rule_validations", ())
    )

    outcome_spec = spec.get("outcome", {})
    if outcome_spec.get("mode", "unobserved") == "unobserved":
        outcome = unobserved_outcome(
            spec["symbol"],
            detection_time_evidence_id=detection.deterministic_id,
            limitations=tuple(outcome_spec.get("limitations", ())),
        )
    else:
        raise ValueError(
            "only the 'unobserved' outcome mode is supported offline; measuring an outcome "
            "requires acquiring market data (see the acquisition manifest)"
        )

    return build_validation_case(
        spec["case_id"],
        spec["symbol"],
        artifacts=artifacts,
        detection_time=detection,
        original_rules=ORIGINAL_RULES,
        original_snapshot=snapshot,
        replays=replays,
        rule_validations=validations,
        outcome=outcome,
        limitations=tuple(spec.get("limitations", ())),
    )


__all__ = ["build_case_from_spec", "load_case_spec"]
