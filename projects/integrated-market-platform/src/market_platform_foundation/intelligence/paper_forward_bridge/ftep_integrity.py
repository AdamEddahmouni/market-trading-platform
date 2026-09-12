"""Deterministic FTEP campaign integrity checks (read-only)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from market_platform_foundation.research.security_identity import FTEP_V1_001_MANIFEST_FINGERPRINT

from .activation import ActivationManifestError, load_activation_manifest
from .campaign_readiness import CampaignReadinessDisposition, evaluate_campaign_readiness
from .campaign_status import collect_ftep_campaign_status

FTEP_V1_002_EXPECTED_FINGERPRINT = (
    "F7083180990BC59578CA045E1E1318A356421BBC9B81EE514C14130CB0B356B1"
)


def _check(
    check_id: str,
    passed: bool,
    detail: str,
    *,
    severity: str = "ERROR",
) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "passed": passed,
        "severity": severity,
        "detail": detail,
    }


def collect_ftep_integrity_checks(
    repository_root: Path,
    campaign_slug: str = "FTEP-V1-002",
) -> dict[str, Any]:
    """Run fail-closed integrity assertions for an active FTEP campaign."""

    checks: list[dict[str, Any]] = []

    v1_001_fp: str | None = None
    v1_001_status: str | None = None
    try:
        manifest_001 = load_activation_manifest("FTEP-V1-001")
        v1_001_fp = manifest_001.manifest_fingerprint
        v1_001_status = str(manifest_001.status.value)
    except (ActivationManifestError, FileNotFoundError, ValueError) as exc:
        checks.append(
            _check(
                "ftep_v1_001_manifest_loadable",
                False,
                str(exc),
            )
        )
    else:
        checks.append(
            _check(
                "ftep_v1_001_manifest_loadable",
                True,
                "FTEP-V1-001 activation manifest loaded",
            )
        )
        checks.append(
            _check(
                "ftep_v1_001_fingerprint_unchanged",
                v1_001_fp == FTEP_V1_001_MANIFEST_FINGERPRINT,
                f"expected {FTEP_V1_001_MANIFEST_FINGERPRINT}, got {v1_001_fp}",
            )
        )
        checks.append(
            _check(
                "ftep_v1_001_frozen",
                v1_001_status == "FROZEN",
                f"status={v1_001_status}",
            )
        )

    try:
        manifest = load_activation_manifest(campaign_slug)
        checks.append(
            _check(
                f"{campaign_slug.lower()}_manifest_frozen",
                str(manifest.status.value) == "FROZEN",
                f"status={manifest.status.value}",
            )
        )
        if campaign_slug == "FTEP-V1-002":
            checks.append(
                _check(
                    "ftep_v1_002_fingerprint_expected",
                    manifest.manifest_fingerprint == FTEP_V1_002_EXPECTED_FINGERPRINT,
                    f"expected {FTEP_V1_002_EXPECTED_FINGERPRINT}, got {manifest.manifest_fingerprint}",
                )
            )
    except (ActivationManifestError, FileNotFoundError, ValueError) as exc:
        checks.append(
            _check(
                f"{campaign_slug.lower()}_manifest_loadable",
                False,
                str(exc),
            )
        )

    persist_on = os.environ.get("IMP_PERSIST_STATE") == "1" or bool(os.environ.get("IMP_STATE_DIR"))
    checks.append(
        _check(
            "imp_persist_state_configured",
            persist_on,
            "IMP_PERSIST_STATE=1 or IMP_STATE_DIR required for governed sessions",
            severity="WARN" if not persist_on else "ERROR",
        )
    )

    readiness = evaluate_campaign_readiness(campaign_slug, repository_root=repository_root)
    readiness_ready = readiness.disposition == CampaignReadinessDisposition.READY
    readiness_detail = (
        f"disposition={readiness.disposition.value}; blockers={readiness.blockers}"
    )
    if not readiness_ready and readiness.blockers == ("PERSISTENCE_DISABLED",):
        readiness_detail += (
            "; operator_hint=Set IMP_PERSIST_STATE=1 or IMP_STATE_DIR, then re-run "
            "integrity-check (campaign gates pass once durable state is enabled)"
        )
    checks.append(
        _check(
            "campaign_readiness_ready",
            readiness_ready,
            readiness_detail,
        )
    )

    status = collect_ftep_campaign_status(repository_root, campaign_slug)
    checks.append(
        _check(
            "no_fabricated_empirical_locks",
            status["empirical_lock_count"] == 0 and status["governed_session_count"] == 0,
            (
                f"locks={status['empirical_lock_count']} "
                f"sessions={status['governed_session_count']}"
            ),
        )
    )
    if status.get("signal_only_session_started"):
        checks.append(
            _check(
                "signal_only_session_requires_durable_state",
                False,
                "signal_only_session_started=true but session/lock counts are zero",
            )
        )
    else:
        checks.append(
            _check(
                "signal_only_session_requires_durable_state",
                True,
                "no governed session flag without durable counters",
            )
        )

    failed = [item for item in checks if not item["passed"] and item["severity"] == "ERROR"]
    disposition = "PASS" if not failed else "FAIL"

    operator_hints: list[str] = []
    if not persist_on and "PERSISTENCE_DISABLED" in readiness.blockers:
        operator_hints.append(
            "Durable forward-test state is off: set IMP_PERSIST_STATE=1 or IMP_STATE_DIR "
            "before integrity-check, campaign-readiness, or governed SIGNAL_ONLY session start."
        )

    return {
        "schema_version": "1.0.0",
        "artifact_kind": "ftep_integrity_report",
        "campaign_slug": campaign_slug,
        "disposition": disposition,
        "checks": checks,
        "failed_check_ids": [item["check_id"] for item in failed],
        "operator_hints": operator_hints,
        "secrets_included": False,
    }


__all__ = ["FTEP_V1_002_EXPECTED_FINGERPRINT", "collect_ftep_integrity_checks"]
