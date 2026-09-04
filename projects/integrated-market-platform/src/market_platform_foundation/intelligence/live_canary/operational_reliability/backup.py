"""Canonical state backup and integrity verification (BUILD 32)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from ..kill_switch_store import KillSwitchStore
from ..operator_control.context import OperatorControlContext
from .identity import derive_backup_manifest_id
from .types import (
    OPERATIONAL_RELIABILITY_SCHEMA_VERSION,
    BackupManifestV1,
)

SECRET_EXCLUSIONS = (
    "credentials",
    "api_secret",
    "token",
    "password",
    "oauth",
    "private_key",
    "session_cookie",
)


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _hash_content(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def collect_backup_scope(ctx: OperatorControlContext) -> dict[str, Any]:
    """Collect canonical canary state for backup — excludes secrets."""
    return {
        "kill_switch": ctx.kill_switch.to_persistence_dict(),
        "governance_state": ctx.governance_state.value,
        "session_ref": ctx.session_ref,
        "broker_health_label": ctx.broker_health,
        "reconciliation_health_label": ctx.reconciliation_health,
        "ledger_submissions": len(ctx.ledger.submission_receipts),
        "ledger_fills": len(ctx.ledger.fill_receipts),
        "incidents": [i.incident_id for i in ctx.incidents],
    }


def canonical_backup_content(scope: dict[str, Any]) -> str:
    return _canonical_json(scope)


def create_backup_manifest(
    ctx: OperatorControlContext,
    *,
    created_at_ns: int,
    source_head: str,
) -> BackupManifestV1:
    scope = collect_backup_scope(ctx)
    content = canonical_backup_content(scope)
    content_hash = _hash_content(content)
    manifest = BackupManifestV1(
        backup_manifest_id="",
        schema_version=OPERATIONAL_RELIABILITY_SCHEMA_VERSION,
        created_at_ns=created_at_ns,
        source_head=source_head,
        included_stores=(
            "kill_switch",
            "ledger",
            "incidents",
            "governance_state",
        ),
        content_hashes={"canonical_state": content_hash},
        exclusions=SECRET_EXCLUSIONS,
        integrity_status="VERIFIED",
        encryption_status="NONE_LOCAL_QUALIFICATION",
    )
    return BackupManifestV1(
        backup_manifest_id=derive_backup_manifest_id(manifest),
        schema_version=manifest.schema_version,
        created_at_ns=manifest.created_at_ns,
        source_head=manifest.source_head,
        included_stores=manifest.included_stores,
        content_hashes=manifest.content_hashes,
        exclusions=manifest.exclusions,
        integrity_status=manifest.integrity_status,
        encryption_status=manifest.encryption_status,
        metadata=manifest.metadata,
    )


def verify_backup_integrity(manifest: BackupManifestV1, content: str) -> bool:
    expected = manifest.content_hashes.get("canonical_state")
    if expected is None:
        return False
    return _hash_content(content) == expected


def restore_kill_switch_from_backup(data: dict[str, str] | None) -> KillSwitchStore:
    """Restore kill switch; corrupt/missing defaults to BLOCK."""
    return KillSwitchStore.from_persistence_dict(data)
