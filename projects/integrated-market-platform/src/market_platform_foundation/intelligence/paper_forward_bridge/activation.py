"""FTEP-V1 activation manifest loading, validation, and state machine."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from market_platform_foundation.canonical import canonical_bytes, load_json_strict, sha256_bytes

from ...local_state.paths import REPO_ROOT
from .protocol_ref import ProtocolRefError, assert_protocol_ref_valid, write_test_protocol_ref

MANIFEST_SCHEMA_VERSION = "intelligence/paper_forward_bridge/activation_manifest/1.0.0"
MANIFEST_FILENAME = "ACTIVATION_MANIFEST.json"
DEFAULT_CAMPAIGN_SLUG = "FTEP-V1-001"

_FINGERPRINT_EXCLUDED_KEYS = frozenset(
    {
        "fingerprint",
        "manifest_fingerprint",
        "manifest_sha256",
        "status",
        "activation_status",
        "frozen_at",
        "frozen_at_ns",
        "owner_signed_at",
        "operator_attestation",
        "campaign_id",
    }
)


class ActivationManifestStatus(StrEnum):
    DRAFT = "DRAFT"
    PENDING_OWNER_DECISIONS = "PENDING_OWNER_DECISIONS"
    FROZEN = "FROZEN"
    ACTIVE = "ACTIVE"
    RETIRED = "RETIRED"


class ActivationManifestError(ValueError):
    """Activation manifest boundary failure."""


@dataclass(frozen=True, slots=True)
class ActivationManifest:
    raw: dict[str, Any]
    path: Path

    @property
    def campaign_slug(self) -> str:
        return str(self.raw.get("campaign_slug") or self.raw.get("campaign_id") or "")

    @property
    def campaign_id(self) -> str | None:
        value = self.raw.get("campaign_id")
        return str(value) if value else None

    @property
    def protocol_id(self) -> str:
        return str(self.raw.get("protocol_id") or "")

    @property
    def activation_version(self) -> str:
        return str(
            self.raw.get("activation_version")
            or self.raw.get("manifest_schema_version")
            or "1.0.0"
        )

    @property
    def status(self) -> ActivationManifestStatus:
        raw_status = self.raw.get("activation_status") or self.raw.get("status")
        return ActivationManifestStatus(str(raw_status))

    @property
    def manifest_fingerprint(self) -> str:
        return str(
            self.raw.get("manifest_fingerprint")
            or self.raw.get("manifest_sha256")
            or self.raw.get("fingerprint")
            or ""
        )

    @property
    def binding(self) -> dict[str, Any]:
        binding = self.raw.get("binding")
        if isinstance(binding, dict):
            return dict(binding)
        return _synthetic_binding(self.raw)

    @property
    def owner_decisions_pending(self) -> tuple[str, ...]:
        pending = (
            self.raw.get("owner_decisions_required")
            or self.raw.get("owner_decisions_pending")
            or self.raw.get("unresolved_fields")
            or ()
        )
        return tuple(str(item) for item in pending)

    @property
    def paper_account_id(self) -> str | None:
        value = self.raw.get("paper_account_id")
        if value is None:
            account_scope = self.raw.get("account_scope")
            if isinstance(account_scope, dict):
                account = account_scope.get("account_id")
                return str(account) if account else None
            return None
        return str(value)

    def to_dict(self) -> dict[str, Any]:
        return dict(self.raw)


def campaigns_root() -> Path:
    override = os.environ.get("IMP_FORWARD_TEST_CAMPAIGNS_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return REPO_ROOT / "artifacts" / "forward-test-campaigns"


def manifest_path(campaign_slug: str, *, campaigns_root_override: Path | None = None) -> Path:
    root = campaigns_root_override or campaigns_root()
    return root / campaign_slug / MANIFEST_FILENAME


def fingerprint_body(manifest: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in manifest.items() if key not in _FINGERPRINT_EXCLUDED_KEYS}


def compute_manifest_fingerprint(manifest: dict[str, Any]) -> str:
    return sha256_bytes(canonical_bytes(fingerprint_body(manifest)))


manifest_fingerprint = compute_manifest_fingerprint


def derive_campaign_id(manifest: dict[str, Any]) -> str:
    fingerprint = compute_manifest_fingerprint(manifest)
    return f"FTCAMP-{fingerprint.lower()}"


def is_derived_campaign_id(value: str) -> bool:
    return value.strip().upper().startswith("FTCAMP-")


def resolve_campaign_manifest_slug(
    *,
    campaign_id: str | None,
    campaign_slug: str | None = None,
    config: dict[str, Any] | None = None,
) -> str | None:
    """Resolve filesystem campaign slug for manifest reload (CG-01)."""
    if campaign_slug and str(campaign_slug).strip():
        return str(campaign_slug).strip()
    if config:
        stored = config.get("campaign_slug")
        if isinstance(stored, str) and stored.strip():
            return stored.strip()
    if campaign_id and not is_derived_campaign_id(campaign_id):
        return str(campaign_id).strip()
    return None


def _split_policy_ref(ref: str) -> tuple[str, str]:
    if "@" in ref:
        policy_id, policy_version = ref.split("@", 1)
        return policy_id, policy_version
    return ref, "1.0.0"


def _synthetic_binding(raw: dict[str, Any]) -> dict[str, Any]:
    recommended = raw.get("recommended_not_binding")
    rec = dict(recommended) if isinstance(recommended, dict) else {}
    safety = raw.get("safety_constraints")
    safety_dict = dict(safety) if isinstance(safety, dict) else {}
    horizons = raw.get("horizons_ns") or [1_800_000_000_000]
    horizon = int(horizons[0]) if horizons else 1_800_000_000_000
    universe_symbols = rec.get("universe") or raw.get("universe") or ["ES"]
    baseline = rec.get("baseline_policy_id") or "news_deterministic_baseline@1.0.0"
    ai_policy = rec.get("ai_policy_id") or "news_ai_enhanced@1.0.0"
    baseline_id, baseline_version = _split_policy_ref(str(baseline))
    ai_id, ai_version = _split_policy_ref(str(ai_policy))
    persistence_required = True
    resolved_fields = raw.get("resolved_fields")
    if isinstance(resolved_fields, dict):
        act05 = resolved_fields.get("FTEP-ACT-05")
        if isinstance(act05, dict):
            persistence_required = act05.get("resolution") == "IMP_PERSIST_STATE_REQUIRED"
    return {
        "run_kind": "FORWARD_TEST",
        "mode": "PAPER",
        "test_mode": str(
            raw.get("test_mode_phase_1") or rec.get("test_mode_phase_1") or "SIGNAL_ONLY"
        ),
        "universe": {
            "symbols": list(universe_symbols),
            "asset_class": rec.get("lane_id") or raw.get("lane_id") or "FUTURES_EQUITY_INDEX",
        },
        "cohort_arms": {
            "baseline": {"policy_id": baseline_id, "policy_version": baseline_version},
            "ai_enhanced": {"policy_id": ai_id, "policy_version": ai_version},
        },
        "evaluation_horizon_ns": horizon,
        "persistence_required": persistence_required,
        "execution_mode": str(safety_dict.get("mode") or "INTERNAL_SIMULATION"),
    }


def normalize_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(manifest)
    if "status" not in normalized and "activation_status" in normalized:
        normalized["status"] = normalized["activation_status"]
    if "activation_status" not in normalized and "status" in normalized:
        normalized["activation_status"] = normalized["status"]
    if "schema_version" not in normalized:
        schema_version = normalized.get("manifest_schema_version")
        if schema_version is not None:
            normalized["schema_version"] = str(schema_version)
    if "campaign_slug" not in normalized:
        slug = normalized.get("campaign_slug") or normalized.get("campaign_id")
        if slug:
            normalized["campaign_slug"] = str(slug)
    if "binding" not in normalized or not isinstance(normalized.get("binding"), dict):
        normalized["binding"] = _synthetic_binding(normalized)
    pending = (
        normalized.get("owner_decisions_pending")
        or normalized.get("owner_decisions_required")
        or normalized.get("unresolved_fields")
        or []
    )
    normalized["owner_decisions_pending"] = list(pending)
    return normalized


def validate_manifest_schema(
    manifest: dict[str, Any],
    *,
    campaigns_root_override: Path | None = None,
) -> None:
    normalized = normalize_manifest(manifest)
    status_raw = normalized.get("activation_status") or normalized.get("status")
    if status_raw is None:
        raise ActivationManifestError("ACTIVATION_MANIFEST_MISSING:activation_status")
    try:
        status = ActivationManifestStatus(str(status_raw))
    except ValueError as exc:
        raise ActivationManifestError("ACTIVATION_MANIFEST_STATUS_INVALID") from exc
    if not normalized.get("protocol_id"):
        raise ActivationManifestError("ACTIVATION_MANIFEST_MISSING:protocol_id")
    schema_version = normalized.get("schema_version") or normalized.get("manifest_schema_version")
    if schema_version is None:
        raise ActivationManifestError("ACTIVATION_MANIFEST_MISSING:schema_version")
    slug = normalized.get("campaign_slug")
    if not slug:
        raise ActivationManifestError("ACTIVATION_MANIFEST_MISSING:campaign_slug")
    binding = normalized.get("binding")
    if isinstance(binding, dict):
        _validate_binding(binding)
    stored = (
        normalized.get("manifest_fingerprint")
        or normalized.get("manifest_sha256")
        or normalized.get("fingerprint")
    )
    if stored is not None and stored != compute_manifest_fingerprint(normalized):
        raise ActivationManifestError("ACTIVATION_MANIFEST_FINGERPRINT_MISMATCH")
    if status in {
        ActivationManifestStatus.FROZEN,
        ActivationManifestStatus.ACTIVE,
    }:
        try:
            assert_protocol_ref_valid(
                str(slug),
                campaigns_root_override=campaigns_root_override,
            )
        except ProtocolRefError as exc:
            raise ActivationManifestError(str(exc)) from exc


def _validate_binding(binding: dict[str, Any]) -> None:
    if binding.get("run_kind") != "FORWARD_TEST":
        raise ActivationManifestError("ACTIVATION_MANIFEST_RUN_KIND_INVALID")
    if str(binding.get("mode", "")).upper() != "PAPER":
        raise ActivationManifestError("ACTIVATION_MANIFEST_MODE_INVALID")
    universe = binding.get("universe")
    if not isinstance(universe, dict) or not universe.get("symbols"):
        raise ActivationManifestError("ACTIVATION_MANIFEST_UNIVERSE_INVALID")
    cohort_arms = binding.get("cohort_arms")
    if not isinstance(cohort_arms, dict) or "baseline" not in cohort_arms:
        raise ActivationManifestError("ACTIVATION_MANIFEST_COHORT_ARMS_INVALID")
    horizon = binding.get("evaluation_horizon_ns")
    if not isinstance(horizon, int) or horizon <= 0:
        raise ActivationManifestError("ACTIVATION_MANIFEST_HORIZON_INVALID")


def load_activation_manifest(
    campaign_slug: str,
    *,
    campaigns_root_override: Path | None = None,
) -> ActivationManifest:
    path = manifest_path(campaign_slug, campaigns_root_override=campaigns_root_override)
    if not path.is_file():
        raise ActivationManifestError("ACTIVATION_MANIFEST_NOT_FOUND")
    loaded = load_json_strict(path)
    if not isinstance(loaded, dict):
        raise ActivationManifestError("ACTIVATION_MANIFEST_INVALID")
    normalized = normalize_manifest(loaded)
    validate_manifest_schema(normalized, campaigns_root_override=campaigns_root_override)
    return ActivationManifest(raw=normalized, path=path)


def assert_manifest_session_eligible(manifest: ActivationManifest) -> None:
    if manifest.status not in {
        ActivationManifestStatus.FROZEN,
        ActivationManifestStatus.ACTIVE,
    }:
        raise ActivationManifestError("ACTIVATION_MANIFEST_NOT_FROZEN")
    if manifest.owner_decisions_pending:
        raise ActivationManifestError("ACTIVATION_MANIFEST_OWNER_DECISIONS_PENDING")


def assert_manifest_immutable_for_freeze(manifest: ActivationManifest) -> None:
    if manifest.status in {ActivationManifestStatus.FROZEN, ActivationManifestStatus.ACTIVE}:
        raise ActivationManifestError("ACTIVATION_MANIFEST_ALREADY_FROZEN")
    if manifest.status == ActivationManifestStatus.RETIRED:
        raise ActivationManifestError("ACTIVATION_MANIFEST_RETIRED")


def transition_manifest_status(
    manifest: ActivationManifest,
    target: ActivationManifestStatus,
) -> dict[str, Any]:
    current = manifest.status
    allowed: dict[ActivationManifestStatus, set[ActivationManifestStatus]] = {
        ActivationManifestStatus.DRAFT: {
            ActivationManifestStatus.PENDING_OWNER_DECISIONS,
            ActivationManifestStatus.FROZEN,
        },
        ActivationManifestStatus.PENDING_OWNER_DECISIONS: {
            ActivationManifestStatus.FROZEN,
            ActivationManifestStatus.DRAFT,
        },
        ActivationManifestStatus.FROZEN: {ActivationManifestStatus.ACTIVE},
        ActivationManifestStatus.ACTIVE: {ActivationManifestStatus.RETIRED},
        ActivationManifestStatus.RETIRED: set(),
    }
    if target not in allowed.get(current, set()):
        raise ActivationManifestError(f"ACTIVATION_MANIFEST_TRANSITION_FORBIDDEN:{current}->{target}")
    updated = normalize_manifest(dict(manifest.raw))
    updated["activation_status"] = target.value
    updated["status"] = target.value
    return updated


def freeze_manifest(manifest: ActivationManifest, *, frozen_at: str) -> dict[str, Any]:
    assert_manifest_immutable_for_freeze(manifest)
    if manifest.owner_decisions_pending:
        raise ActivationManifestError("ACTIVATION_MANIFEST_OWNER_DECISIONS_PENDING")
    try:
        campaigns_root = (
            manifest.path.parent.parent if manifest.path.name == MANIFEST_FILENAME else None
        )
        assert_protocol_ref_valid(
            manifest.campaign_slug,
            campaigns_root_override=campaigns_root,
        )
    except ProtocolRefError as exc:
        raise ActivationManifestError(str(exc)) from exc
    updated = transition_manifest_status(manifest, ActivationManifestStatus.FROZEN)
    updated["schema_version"] = updated.get("schema_version") or MANIFEST_SCHEMA_VERSION
    updated["frozen_at"] = frozen_at
    fingerprint = compute_manifest_fingerprint(updated)
    updated["manifest_fingerprint"] = fingerprint
    updated["fingerprint"] = fingerprint
    updated["campaign_id"] = derive_campaign_id(updated)
    validate_manifest_schema(
        updated,
        campaigns_root_override=(
            manifest.path.parent.parent if manifest.path.name == MANIFEST_FILENAME else None
        ),
    )
    return updated


def write_activation_manifest(
    path: Path,
    manifest: dict[str, Any],
    *,
    campaigns_root_override: Path | None = None,
) -> None:
    normalized = normalize_manifest(manifest)
    root_override = campaigns_root_override
    if root_override is None and path.name == MANIFEST_FILENAME:
        root_override = path.parent.parent
    validate_manifest_schema(normalized, campaigns_root_override=root_override)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(normalized, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def cohort_arm_policy(manifest: ActivationManifest, cohort_arm: str) -> tuple[str, str]:
    arms = manifest.binding.get("cohort_arms") or {}
    key = cohort_arm.lower()
    if key == "baseline":
        arm = arms.get("baseline")
    elif key in {"ai_enhanced", "ai-enhanced", "ai"}:
        arm = arms.get("ai_enhanced")
    else:
        raise ActivationManifestError("ACTIVATION_MANIFEST_COHORT_ARM_UNKNOWN")
    if not isinstance(arm, dict):
        raise ActivationManifestError("ACTIVATION_MANIFEST_COHORT_ARM_UNKNOWN")
    policy_id = str(arm.get("policy_id") or "")
    policy_version = str(arm.get("policy_version") or "")
    if not policy_id or not policy_version:
        raise ActivationManifestError("ACTIVATION_MANIFEST_COHORT_ARM_INCOMPLETE")
    return policy_id, policy_version


def manifest_universe_symbols(manifest: ActivationManifest) -> tuple[str, ...]:
    universe = manifest.binding.get("universe") or {}
    symbols = universe.get("symbols") or []
    return tuple(str(item).upper() for item in symbols)


def seed_test_frozen_manifest(
    campaigns_root: Path,
    *,
    campaign_slug: str = DEFAULT_CAMPAIGN_SLUG,
    paper_account_id: str = "paper-a",
    universe_symbols: tuple[str, ...] = ("ES", "ACME"),
    evaluation_horizon_ns: int = 3_600_000_000_000,
) -> ActivationManifest:
    manifest: dict[str, Any] = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "campaign_slug": campaign_slug,
        "protocol_id": "FTEP-V1/0.1.0-PREREG",
        "activation_version": "1.0.0",
        "status": ActivationManifestStatus.FROZEN.value,
        "activation_status": ActivationManifestStatus.FROZEN.value,
        "frozen_at": "2026-09-11T00:00:00Z",
        "owner_decisions_pending": [],
        "paper_account_id": paper_account_id,
        "binding": {
            "run_kind": "FORWARD_TEST",
            "mode": "PAPER",
            "test_mode": "SIGNAL_ONLY",
            "universe": {
                "symbols": list(universe_symbols),
                "asset_class": "FUTURES_EQUITY_INDEX",
            },
            "cohort_arms": {
                "baseline": {
                    "policy_id": "news_deterministic_baseline",
                    "policy_version": "1.0.0",
                },
                "ai_enhanced": {
                    "policy_id": "news_ai_enhanced",
                    "policy_version": "1.0.0",
                },
            },
            "evaluation_horizon_ns": evaluation_horizon_ns,
            "persistence_required": False,
        },
    }
    fingerprint = compute_manifest_fingerprint(manifest)
    manifest["manifest_fingerprint"] = fingerprint
    manifest["fingerprint"] = fingerprint
    manifest["campaign_id"] = derive_campaign_id(manifest)
    path = manifest_path(campaign_slug, campaigns_root_override=campaigns_root)
    write_test_protocol_ref(campaigns_root, campaign_slug=campaign_slug)
    write_activation_manifest(path, manifest, campaigns_root_override=campaigns_root)
    return load_activation_manifest(campaign_slug, campaigns_root_override=campaigns_root)
