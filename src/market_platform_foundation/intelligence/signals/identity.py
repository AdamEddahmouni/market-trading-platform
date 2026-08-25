"""Deterministic signal identity (BUILD 06)."""

from __future__ import annotations

from typing import Any

from ...canonical import canonical_bytes, sha256_bytes
from ..contracts.common import IntelligenceScope, scope_to_dict

SIGNAL_ID_PREFIX = "SIG-"
IDENTITY_VERSION = "signal-content-sha256-v1"


def semantic_identity_payload(
  *,
  source_snapshot_id: str,
  signal_type: str,
  scope: IntelligenceScope,
  window_ns: int | None,
  calculator_id: str,
  calculator_version: str,
  parameters: dict[str, str] | None = None,
) -> dict[str, Any]:
  """Canonical semantic payload for signal identity — excludes computed value."""
  payload: dict[str, Any] = {
    "identity_version": IDENTITY_VERSION,
    "schema_version": "1",
    "source_snapshot_id": source_snapshot_id,
    "signal_type": signal_type,
    "scope": scope_to_dict(scope),
    "calculator_id": calculator_id,
    "calculator_version": calculator_version,
  }
  if window_ns is not None:
    payload["window_ns"] = window_ns
  if parameters:
    payload["parameters"] = {key: parameters[key] for key in sorted(parameters)}
  return payload


def signal_id_from_payload(payload: dict[str, Any]) -> str:
  return f"{SIGNAL_ID_PREFIX}{sha256_bytes(canonical_bytes(payload))}"


def derive_signal_id(
  *,
  source_snapshot_id: str,
  signal_type: str,
  scope: IntelligenceScope,
  window_ns: int | None,
  calculator_id: str,
  calculator_version: str,
  parameters: dict[str, str] | None = None,
) -> str:
  payload = semantic_identity_payload(
    source_snapshot_id=source_snapshot_id,
    signal_type=signal_type,
    scope=scope,
    window_ns=window_ns,
    calculator_id=calculator_id,
    calculator_version=calculator_version,
    parameters=parameters,
  )
  return signal_id_from_payload(payload)


__all__ = [
  "IDENTITY_VERSION",
  "SIGNAL_ID_PREFIX",
  "derive_signal_id",
  "semantic_identity_payload",
  "signal_id_from_payload",
]
