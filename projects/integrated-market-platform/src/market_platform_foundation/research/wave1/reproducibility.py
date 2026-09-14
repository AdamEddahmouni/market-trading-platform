"""Deterministic run fingerprints for Wave 1 harness replays."""

from __future__ import annotations

import uuid
from typing import Any

from ...canonical import canonical_bytes, sha256_bytes

RUN_NAMESPACE = uuid.UUID("f47ac10b-58cc-4372-a567-0e02b2c3d479")


def examples_fingerprint(examples: list[dict[str, Any]]) -> str:
    ordered = sorted(
        examples,
        key=lambda ex: (int(ex.get("decision_time_ns", 0)), str(ex.get("example_id", ""))),
    )
    return sha256_bytes(canonical_bytes({"examples": ordered}))


def run_fingerprint(
    *,
    registry_fingerprint: str,
    export_fingerprint: str | None,
    examples_fingerprint_value: str,
    family_ids: tuple[str, ...],
    oos_mode: str,
) -> str:
    body = {
        "export_fingerprint": export_fingerprint,
        "family_ids": list(family_ids),
        "examples_fingerprint": examples_fingerprint_value,
        "oos_mode": oos_mode,
        "registry_fingerprint": registry_fingerprint,
    }
    return sha256_bytes(canonical_bytes(body))


def deterministic_run_id(run_fingerprint_value: str) -> str:
    return "W1RUN-" + str(uuid.uuid5(RUN_NAMESPACE, run_fingerprint_value))
