"""Deterministic preflight for FTEP-V1 empirical forward-test sessions."""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from ...local_state.paths import persistence_enabled
from .activation import (
    ActivationManifest,
    ActivationManifestError,
    ActivationManifestStatus,
    cohort_arm_policy,
    compute_manifest_fingerprint,
    load_activation_manifest,
)
from .protocol_ref import ProtocolRefError, verify_protocol_ref


class PreflightDisposition(StrEnum):
    READY = "READY"
    NOT_READY = "NOT_READY"


@dataclass(frozen=True, slots=True)
class ForwardTestPreflightResult:
    disposition: PreflightDisposition
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    campaign_id: str
    protocol_id: str
    activation_version: str
    manifest_fingerprint: str
    manifest_status: str
    metadata: dict[str, Any]


def run_forward_test_preflight(
    *,
    campaign_slug: str | None = None,
    campaign_id: str | None = None,
    mode: str,
    run_kind: str = "FORWARD_TEST",
    manifest_fingerprint: str | None = None,
    manifest_fingerprint_expected: str | None = None,
    cohort_arm: str | None = None,
    campaigns_root_override: Path | None = None,
    now_ns: int | None = None,
) -> ForwardTestPreflightResult:
    slug = campaign_slug or campaign_id
    if not slug:
        raise ValueError("FORWARD_TEST_CAMPAIGN_ID_REQUIRED")

    blockers: list[str] = []
    warnings: list[str] = []
    manifest: ActivationManifest | None = None
    fingerprint = ""

    mode_upper = str(mode).upper()
    if mode_upper == "LIVE":
        blockers.append("FORWARD_TEST_LIVE_MODE_FORBIDDEN")
    elif mode_upper != "PAPER":
        blockers.append("FORWARD_TEST_PAPER_MODE_REQUIRED")

    if run_kind != "FORWARD_TEST":
        blockers.append("FORWARD_TEST_BACKTEST_BOUNDARY_VIOLATION")

    try:
        verify_protocol_ref(slug, campaigns_root_override=campaigns_root_override)
    except ProtocolRefError as exc:
        blockers.append(str(exc))

    try:
        manifest = load_activation_manifest(slug, campaigns_root_override=campaigns_root_override)
    except ActivationManifestError as exc:
        blockers.append(str(exc))
        return ForwardTestPreflightResult(
            disposition=PreflightDisposition.NOT_READY,
            blockers=tuple(blockers),
            warnings=tuple(warnings),
            campaign_id=slug,
            protocol_id="",
            activation_version="",
            manifest_fingerprint="",
            manifest_status="",
            metadata={"checked_at_ns": now_ns or time.time_ns()},
        )

    fingerprint = compute_manifest_fingerprint(manifest.raw)
    stored_fingerprint = manifest.manifest_fingerprint
    if stored_fingerprint and stored_fingerprint != fingerprint:
        blockers.append("ACTIVATION_MANIFEST_FINGERPRINT_MISMATCH")
    expected = manifest_fingerprint_expected or manifest_fingerprint
    if expected and expected.upper() != fingerprint:
        blockers.append("ACTIVATION_MANIFEST_FINGERPRINT_MISMATCH")

    if manifest.status == ActivationManifestStatus.DRAFT:
        blockers.append("ACTIVATION_MANIFEST_DRAFT")
    elif manifest.status == ActivationManifestStatus.PENDING_OWNER_DECISIONS:
        blockers.append("ACTIVATION_MANIFEST_PENDING_OWNER_DECISIONS")
    elif manifest.status not in {
        ActivationManifestStatus.FROZEN,
        ActivationManifestStatus.ACTIVE,
    }:
        blockers.append("ACTIVATION_MANIFEST_NOT_FROZEN")

    if manifest.owner_decisions_pending:
        blockers.append("ACTIVATION_MANIFEST_OWNER_DECISIONS_PENDING")

    binding = manifest.binding
    if binding.get("run_kind") != "FORWARD_TEST":
        blockers.append("FORWARD_TEST_BACKTEST_BOUNDARY_VIOLATION")
    if str(binding.get("mode", "")).upper() != "PAPER":
        blockers.append("FORWARD_TEST_PAPER_MODE_REQUIRED")

    safety = manifest.raw.get("safety_constraints")
    if isinstance(safety, dict) and safety.get("live_execution"):
        blockers.append("FORWARD_TEST_LIVE_MODE_FORBIDDEN")
    cost = safety.get("cost_usd") if isinstance(safety, dict) else None
    if cost is not None and int(cost) != 0:
        blockers.append("COST_AUTHORITY_VIOLATION")

    if binding.get("persistence_required") and not persistence_enabled():
        blockers.append("PERSISTENCE_DISABLED")

    paper_account_id = manifest.paper_account_id
    if paper_account_id is None and "paper_account_id" not in manifest.owner_decisions_pending:
        warnings.append("paper_account_id not declared in manifest")

    if cohort_arm:
        try:
            cohort_arm_policy(manifest, cohort_arm)
        except ActivationManifestError as exc:
            blockers.append(str(exc))

    disposition = PreflightDisposition.READY if not blockers else PreflightDisposition.NOT_READY
    return ForwardTestPreflightResult(
        disposition=disposition,
        blockers=tuple(blockers),
        warnings=tuple(warnings),
        campaign_id=manifest.campaign_id or manifest.campaign_slug,
        protocol_id=manifest.protocol_id,
        activation_version=manifest.activation_version,
        manifest_fingerprint=fingerprint,
        manifest_status=manifest.status.value,
        metadata={"checked_at_ns": now_ns or time.time_ns()},
    )


def assert_forward_test_preflight_ready(result: ForwardTestPreflightResult) -> None:
    if result.disposition != PreflightDisposition.READY:
        raise ActivationManifestError(
            "FORWARD_TEST_PREFLIGHT_FAILED:" + ",".join(result.blockers)
        )
