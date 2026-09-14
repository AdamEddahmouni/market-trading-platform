"""Deterministic identity for quantitative factor contract records."""

from __future__ import annotations

from typing import Any

from ...canonical import canonical_bytes, sha256_bytes

CONSTRUCTION_ID_PREFIX = "FCSPEC-"
OBSERVATION_ID_PREFIX = "FOBS-"
EXPERIMENT_ID_PREFIX = "FEXP-"
SECURITY_BINDING_ID_PREFIX = "FSEC-"
IDENTITY_VERSION = "quant-factor-content-sha256-v1"


def factor_hash(payload: dict[str, Any], *, prefix: str) -> str:
    return f"{prefix}{sha256_bytes(canonical_bytes(payload))}"


__all__ = [
    "CONSTRUCTION_ID_PREFIX",
    "EXPERIMENT_ID_PREFIX",
    "IDENTITY_VERSION",
    "OBSERVATION_ID_PREFIX",
    "SECURITY_BINDING_ID_PREFIX",
    "factor_hash",
]
