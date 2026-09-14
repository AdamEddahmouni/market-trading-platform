"""Frozen Wave 1 registry loading (Track E). Hypothesis prose lives at ``hypothesis_ref`` only."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ...canonical import canonical_bytes, sha256_bytes, load_json_strict
from .errors import Wave1ConfigError

WAVE1_REGISTRY_SCHEMA_VERSION = "1.0.0"
DEFAULT_REGISTRY_PATH = (
    Path(__file__).resolve().parents[4] / "config" / "wave1" / "frozen_registry.json"
)

REQUIRED_FAMILY_KEYS = (
    "family_id",
    "hypothesis_ref",
    "baseline_id",
    "adapter_kind",
    "primary_metric",
    "min_sample_oos",
    "evaluation_window",
    "negative_controls",
)


@dataclass(frozen=True, slots=True)
class Wave1FamilyConfig:
    family_id: str
    hypothesis_ref: str
    baseline_id: str
    adapter_kind: str
    primary_metric: str
    min_sample_oos: int
    evaluation_window: dict[str, Any]
    negative_controls: tuple[str, ...]
    primary_metric_threshold_bps: float = 0.0
    title: str = ""

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Wave1FamilyConfig:
        missing = [k for k in REQUIRED_FAMILY_KEYS if k not in payload]
        if missing:
            raise Wave1ConfigError("W1_FAMILY_CONFIG_INCOMPLETE", details={"missing": missing})
        controls = payload.get("negative_controls") or []
        if not isinstance(controls, list):
            raise Wave1ConfigError("W1_NEGATIVE_CONTROLS_INVALID")
        return cls(
            family_id=str(payload["family_id"]),
            hypothesis_ref=str(payload["hypothesis_ref"]),
            baseline_id=str(payload["baseline_id"]),
            adapter_kind=str(payload["adapter_kind"]),
            primary_metric=str(payload["primary_metric"]),
            min_sample_oos=int(payload["min_sample_oos"]),
            evaluation_window=dict(payload["evaluation_window"]),
            negative_controls=tuple(str(c) for c in controls),
            primary_metric_threshold_bps=float(payload.get("primary_metric_threshold_bps", 0.0)),
            title=str(payload.get("title", "")),
        )


@dataclass(frozen=True, slots=True)
class Wave1FrozenRegistry:
    schema_version: str
    program_track: str
    wave: int
    implementation_version: str
    families: tuple[Wave1FamilyConfig, ...]
    registry_fingerprint: str
    source_path: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def family_by_id(self, family_id: str) -> Wave1FamilyConfig:
        for family in self.families:
            if family.family_id == family_id:
                return family
        raise Wave1ConfigError("W1_UNKNOWN_FAMILY", details={"family_id": family_id})


def registry_body_fingerprint(body: dict[str, Any]) -> str:
    payload = dict(body)
    payload.pop("registry_fingerprint", None)
    payload.pop("frozen_registry_hash", None)
    return sha256_bytes(canonical_bytes(payload))


def load_frozen_registry(path: Path | None = None) -> Wave1FrozenRegistry:
    registry_path = path or DEFAULT_REGISTRY_PATH
    if not registry_path.is_file():
        raise Wave1ConfigError("W1_REGISTRY_NOT_FOUND", details={"path": str(registry_path)})
    raw = load_json_strict(registry_path)
    if str(raw.get("schema_version")) != WAVE1_REGISTRY_SCHEMA_VERSION:
        raise Wave1ConfigError(
            "W1_REGISTRY_SCHEMA_MISMATCH",
            details={"expected": WAVE1_REGISTRY_SCHEMA_VERSION, "actual": raw.get("schema_version")},
        )
    if str(raw.get("program_track")) != "TRACK_E":
        raise Wave1ConfigError("W1_PROGRAM_TRACK_INVALID")
    families_raw = raw.get("families")
    if not isinstance(families_raw, list) or len(families_raw) != 8:
        raise Wave1ConfigError(
            "W1_FAMILY_COUNT_INVALID",
            details={"expected": 8, "actual": len(families_raw) if isinstance(families_raw, list) else None},
        )
    families = tuple(Wave1FamilyConfig.from_dict(dict(item)) for item in families_raw)
    ids = [f.family_id for f in families]
    if len(set(ids)) != len(ids):
        raise Wave1ConfigError("W1_DUPLICATE_FAMILY_ID")
    fingerprint = registry_body_fingerprint(raw)
    expected = raw.get("registry_fingerprint") or raw.get("frozen_registry_hash")
    if expected is not None and str(expected).upper() != fingerprint:
        raise Wave1ConfigError(
            "W1_REGISTRY_FINGERPRINT_MISMATCH",
            details={"expected": str(expected).upper(), "computed": fingerprint},
        )
    return Wave1FrozenRegistry(
        schema_version=str(raw["schema_version"]),
        program_track=str(raw["program_track"]),
        wave=int(raw["wave"]),
        implementation_version=str(raw.get("implementation_version", "wave1-harness-v1")),
        families=families,
        registry_fingerprint=fingerprint,
        source_path=str(registry_path),
        metadata={k: v for k, v in raw.items() if k not in {"families", "schema_version", "program_track", "wave"}},
    )


def attach_registry_fingerprint(path: Path) -> str:
    """Compute fingerprint for a registry file (operator/tooling helper)."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    return registry_body_fingerprint(raw)
