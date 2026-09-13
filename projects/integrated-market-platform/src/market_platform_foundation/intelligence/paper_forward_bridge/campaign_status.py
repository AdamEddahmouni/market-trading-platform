"""Read-only FTEP campaign status composed from frozen artifacts and gates."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from .activation import ActivationManifestError, load_activation_manifest
from .campaign_readiness import evaluate_campaign_readiness
from .session_policy import CALENDAR_US_EQUITY_RTH, is_within_us_equity_rth


def _collect_durable_empirical_counts(
    repository_root: Path,
    campaign_slug: str,
) -> dict[str, Any]:
    """Count governed sessions and empirical locks from durable forward-test state."""

    from ...local_state.paths import persistence_enabled
    from ...local_state.startup import open_local_state

    baseline: dict[str, Any] = {
        "governed_session_count": 0,
        "empirical_lock_count": 0,
        "empirical_counts_source": "persistence_disabled",
    }
    if not persistence_enabled():
        return baseline

    repo = open_local_state()
    if repo is None:
        baseline["empirical_counts_source"] = "unavailable"
        return baseline

    try:
        manifest = load_activation_manifest(campaign_slug)
        campaign_id = str(manifest.campaign_id or "")
    except (ActivationManifestError, FileNotFoundError, ValueError):
        baseline["empirical_counts_source"] = "manifest_unavailable"
        return baseline

    if not campaign_id:
        baseline["empirical_counts_source"] = "campaign_id_missing"
        return baseline

    session_row = repo.connection.execute(
        "SELECT COUNT(*) AS count FROM forward_test_sessions WHERE campaign_id=?",
        (campaign_id,),
    ).fetchone()
    lock_row = repo.connection.execute(
        """
        SELECT COUNT(*) AS count
        FROM forward_test_decisions AS d
        INNER JOIN forward_test_sessions AS s ON d.session_id = s.session_id
        WHERE s.campaign_id=? AND d.state=?
        """,
        (campaign_id, "LOCKED"),
    ).fetchone()
    return {
        "governed_session_count": int(session_row["count"]) if session_row is not None else 0,
        "empirical_lock_count": int(lock_row["count"]) if lock_row is not None else 0,
        "empirical_counts_source": "durable",
    }


def _artifact_dir_for_slug(campaign_slug: str) -> str:
    return campaign_slug.lower().replace("_", "-")


def _artifact_dir(repository_root: Path, campaign_slug: str) -> Path:
    return repository_root / "artifacts" / _artifact_dir_for_slug(campaign_slug)


def _load_json_receipts(
    artifact_dir: Path,
    glob_pattern: str,
) -> list[dict[str, Any]]:
    if not artifact_dir.is_dir():
        return []
    receipts: list[dict[str, Any]] = []
    for path in sorted(artifact_dir.glob(glob_pattern)):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            receipts.append(payload)
    return receipts


def _load_signal_only_receipts(repository_root: Path, campaign_slug: str) -> list[dict[str, Any]]:
    return _load_json_receipts(
        _artifact_dir(repository_root, campaign_slug),
        "signal-only-authorization-receipt-*.json",
    )


def _load_empirical_lock_authorization_receipts(
    repository_root: Path,
    campaign_slug: str,
) -> list[dict[str, Any]]:
    return _load_json_receipts(
        _artifact_dir(repository_root, campaign_slug),
        "empirical-lock-authorization-receipt-*.json",
    )


def manifest_operator_empirical_lock_authorized(campaign_slug: str) -> bool:
    """Frozen manifest operator_attestation only (post-freeze receipts are separate)."""

    try:
        manifest = load_activation_manifest(campaign_slug)
    except (ActivationManifestError, FileNotFoundError, ValueError):
        return False
    attestation = manifest.raw.get("operator_attestation") or {}
    if not isinstance(attestation, dict):
        return False
    return bool(attestation.get("empirical_lock_authorized"))


def empirical_lock_authorized(repository_root: Path, campaign_slug: str) -> bool:
    """Manifest attestation or append-only owner authorization receipts (no manifest mutation)."""

    if manifest_operator_empirical_lock_authorized(campaign_slug):
        return True
    for receipt in _load_signal_only_receipts(repository_root, campaign_slug):
        if bool(receipt.get("empirical_lock_authorized")):
            return True
    for receipt in _load_empirical_lock_authorization_receipts(repository_root, campaign_slug):
        if bool(receipt.get("empirical_lock_authorized")):
            return True
    return False


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
    empirical = _collect_durable_empirical_counts(repository_root, campaign_slug)
    governed_session_count = int(empirical["governed_session_count"])
    empirical_lock_count = int(empirical["empirical_lock_count"])
    if governed_session_count > 0:
        signal_only_session_started = True

    notes = (
        "Lock and session counts are zero until first governed SIGNAL_ONLY session "
        "appends durable forward-test state (no prospective fabrication)."
    )
    if governed_session_count > 0 or empirical_lock_count > 0:
        notes = (
            "Counts sourced from durable forward-test state "
            f"({empirical.get('empirical_counts_source')})."
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
        "empirical_lock_count": empirical_lock_count,
        "governed_session_count": governed_session_count,
        "empirical_counts_source": empirical.get("empirical_counts_source"),
        "notes": notes,
        "empirical_lock_authorized": empirical_lock_authorized(repository_root, campaign_slug),
        "manifest_operator_empirical_lock_authorized": manifest_operator_empirical_lock_authorized(
            campaign_slug
        ),
        "authorization_receipt_paths": [
            str(_artifact_dir(repository_root, campaign_slug) / path.name)
            for path in sorted(
                _artifact_dir(repository_root, campaign_slug).glob(
                    "signal-only-authorization-receipt-*.json"
                )
            )
        ]
        if _artifact_dir(repository_root, campaign_slug).is_dir()
        else [],
        "empirical_lock_authorization_receipt_paths": [
            str(_artifact_dir(repository_root, campaign_slug) / path.name)
            for path in sorted(
                _artifact_dir(repository_root, campaign_slug).glob(
                    "empirical-lock-authorization-receipt-*.json"
                )
            )
        ]
        if _artifact_dir(repository_root, campaign_slug).is_dir()
        else [],
        "secrets_included": False,
    }


__all__ = [
    "collect_ftep_campaign_status",
    "empirical_lock_authorized",
    "manifest_operator_empirical_lock_authorized",
]
