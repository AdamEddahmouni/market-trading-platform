"""Deterministic acceptance spec/report identities (BUILD 25)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .types import SYSTEM_ACCEPTANCE_IMPLEMENTATION_VERSION, SystemAcceptanceSpecV1


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _sha256_prefix(prefix: str, payload: dict[str, Any]) -> str:
    digest = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    return f"{prefix}-{digest}"


def acceptance_spec_identity_payload(spec: SystemAcceptanceSpecV1) -> dict[str, Any]:
    return {
        "schema_version": spec.schema_version,
        "source_build_head": spec.source_build_head,
        "required_build_range": list(spec.required_build_range),
        "required_suites": list(spec.required_suites),
        "required_lifecycle_scenarios": list(spec.required_lifecycle_scenarios),
        "required_adversarial_scenarios": list(spec.required_adversarial_scenarios),
        "required_invariants": list(spec.required_invariants),
        "required_persistence_checks": list(spec.required_persistence_checks),
        "required_replay_checks": list(spec.required_replay_checks),
        "required_determinism_checks": list(spec.required_determinism_checks),
        "required_security_checks": list(spec.required_security_checks),
        "allowed_known_limitations": list(spec.allowed_known_limitations),
        "blocking_failure_classes": [c.value for c in spec.blocking_failure_classes],
        "implementation_version": spec.implementation_version,
    }


def derive_acceptance_spec_id(spec: SystemAcceptanceSpecV1) -> str:
    return _sha256_prefix("ACCSPEC", acceptance_spec_identity_payload(spec))


def derive_acceptance_report_id(
    *,
    acceptance_spec_id: str,
    source_head: str,
    candidate_head: str,
    fixture_identities: tuple[str, ...],
    implementation_version: str,
) -> str:
    payload = {
        "acceptance_spec_id": acceptance_spec_id,
        "source_head": source_head,
        "candidate_head": candidate_head,
        "fixture_identities": list(fixture_identities),
        "implementation_version": implementation_version,
    }
    return _sha256_prefix("ACCREP", payload)


def derive_contract_inventory_hash(inventory: dict[str, Any]) -> str:
    return _sha256_prefix("CTRINV", inventory)


def derive_policy_inventory_hash(inventory: dict[str, Any]) -> str:
    return _sha256_prefix("POLINV", inventory)


def derive_fixture_inventory_hash(inventory: dict[str, Any]) -> str:
    return _sha256_prefix("FIXINV", inventory)
