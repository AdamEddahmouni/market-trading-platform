"""Read-only FTEP campaign status composed from frozen artifacts and gates."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .activation import ActivationManifestError, load_activation_manifest
from .campaign_readiness import evaluate_campaign_readiness
from .session_policy import CALENDAR_US_EQUITY_RTH, is_within_us_equity_rth


def _artifact_dir_for_slug(campaign_slug: str) -> str:
    return campaign_slug.lower().replace("_", "-")


def _load_signal_only_receipts(repository_root: Path, campaign_slug: str) -> list[dict[str, Any]]:
    artifact_dir = repository_root / "artifacts" / _artifact_dir_for_slug(campaign_slug)
    if not artifact_dir.is_dir():
        return []
    receipts: list[dict[str, Any]] = []
    for path in sorted(artifact_dir.glob("signal-only-authorization-receipt-*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            receipts.append(payload)
    return receipts


def collect_ftep_campaign_status(
    repository_root: Path,
    campaign_slug: str,
) -> dict[str, Any]:
    """Secret-free campaign progress snapshot for operators and orchestration."""

    now_ns = time.time_ns()
    calendar_open = is_within_us_equity_rth(now_ns)
    manifest_status = "UNKNOWN"
    manifest_fingerprint: str | None = None
    manifest_error: str | None = None
    try:
        manifest = load_activation_manifest(campaign_slug)
        manifest_status = str(manifest.status.value)
        manifest_fingerprint = manifest.manifest_fingerprint
    except (ActivationManifestError, FileNotFoundError, ValueError) as exc:
        manifest_error = str(exc)

    readiness = evaluate_campaign_readiness(
        campaign_slug,
        repository_root=repository_root,
    )
    readiness_payload = readiness.to_dict()

    receipts = _load_signal_only_receipts(repository_root, campaign_slug)
    signal_only_authorized = bool(receipts)
    signal_only_session_started = any(
        bool(item.get("signal_only_session_started")) for item in receipts
    )

    return {
        "schema_version": "1.0.0",
        "artifact_kind": "ftep_campaign_status",
        "campaign_slug": campaign_slug,
        "observed_at_ns": now_ns,
        "calendar_scope": CALENDAR_US_EQUITY_RTH,
        "us_equity_rth_open": calendar_open,
        "manifest_status": manifest_status,
        "manifest_fingerprint": manifest_fingerprint,
        "manifest_error": manifest_error,
        "campaign_readiness_disposition": readiness_payload.get("disposition"),
        "campaign_readiness_blockers": readiness_payload.get("blockers", []),
        "signal_only_authorization_receipt_count": len(receipts),
        "signal_only_authorized": signal_only_authorized,
        "signal_only_session_started": signal_only_session_started,
        "empirical_lock_count": 0,
        "governed_session_count": 0,
        "notes": (
            "Lock and session counts are zero until first governed SIGNAL_ONLY session "
            "appends durable forward-test state (no prospective fabrication)."
        ),
        "authorization_receipt_paths": [
            str(repository_root / "artifacts" / _artifact_dir_for_slug(campaign_slug) / path.name)
            for path in sorted(
                (repository_root / "artifacts" / _artifact_dir_for_slug(campaign_slug)).glob(
                    "signal-only-authorization-receipt-*.json"
                )
            )
        ]
        if (repository_root / "artifacts" / _artifact_dir_for_slug(campaign_slug)).is_dir()
        else [],
        "secrets_included": False,
    }


__all__ = ["collect_ftep_campaign_status"]
