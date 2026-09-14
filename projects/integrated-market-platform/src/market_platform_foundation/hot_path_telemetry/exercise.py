"""Derive honest MEASURED vs NOT_EXERCISED from observed presence."""

from __future__ import annotations

from typing import Any

from .models import HOT_PATH_TIMESTAMP_NAMES, TimestampExerciseClass

_ALWAYS_NOT_EXERCISED = frozenset({"opportunity_created_at", "operator_surfaced_at"})


def derive_timestamp_exercise(
    presence: dict[str, dict[str, int]],
) -> dict[str, str]:
    exercise: dict[str, str] = {}
    for name in HOT_PATH_TIMESTAMP_NAMES:
        if name in _ALWAYS_NOT_EXERCISED:
            exercise[name] = TimestampExerciseClass.NOT_EXERCISED.value
            continue
        present = int((presence.get(name) or {}).get("present_count", 0))
        if present > 0:
            exercise[name] = TimestampExerciseClass.MEASURED.value
        else:
            exercise[name] = TimestampExerciseClass.NOT_EXERCISED.value
    return exercise


def assert_timestamp_exercise_honest(
    exercise: dict[str, str],
    presence: dict[str, dict[str, int]],
) -> None:
    for name, klass in exercise.items():
        if klass == TimestampExerciseClass.MEASURED.value:
            present = int((presence.get(name) or {}).get("present_count", 0))
            if present <= 0:
                raise ValueError(f"HOT_PATH_TELEMETRY_EXERCISE_MISMATCH:{name}")


def validate_baseline_document(body: dict[str, Any]) -> None:
    assert_timestamp_exercise_honest(
        body.get("timestamp_exercise") or {},
        body.get("timestamp_presence") or {},
    )


__all__ = [
    "assert_timestamp_exercise_honest",
    "derive_timestamp_exercise",
    "validate_baseline_document",
]
