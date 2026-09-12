"""Durable campaign binding for FTEP-V1 forward-test activation."""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from ...clock import monotonic_wall_ns
from ...local_state.connection import LocalStateConnection
from .activation import ActivationManifest, compute_manifest_fingerprint, manifest_path
from .protocol_ref import ProtocolRef, verify_protocol_ref


class CampaignBindingState(StrEnum):
    ACTIVE = "ACTIVE"
    RELEASED = "RELEASED"


class CampaignBindingError(ValueError):
    """Campaign binding boundary failure."""


@dataclass(frozen=True, slots=True)
class CampaignBinding:
    campaign_id: str
    account_id: str
    manifest_fingerprint: str
    manifest_path: str
    protocol_id: str
    protocol_sha256: str
    campaign_state: CampaignBindingState
    activated_at_ns: int | None
    first_lock_at_ns: int | None
    forward_test_session_id: str | None
    created_at_ns: int
    updated_at_ns: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "account_id": self.account_id,
            "manifest_fingerprint": self.manifest_fingerprint,
            "manifest_path": self.manifest_path,
            "protocol_id": self.protocol_id,
            "protocol_sha256": self.protocol_sha256,
            "campaign_state": self.campaign_state.value,
            "activated_at_ns": self.activated_at_ns,
            "first_lock_at_ns": self.first_lock_at_ns,
            "forward_test_session_id": self.forward_test_session_id,
            "created_at_ns": self.created_at_ns,
            "updated_at_ns": self.updated_at_ns,
        }


def binding_from_row(row: dict[str, Any]) -> CampaignBinding:
    return CampaignBinding(
        campaign_id=str(row["campaign_id"]),
        account_id=str(row["account_id"]),
        manifest_fingerprint=str(row["manifest_fingerprint"]),
        manifest_path=str(row["manifest_path"]),
        protocol_id=str(row["protocol_id"]),
        protocol_sha256=str(row["protocol_sha256"]),
        campaign_state=CampaignBindingState(str(row["campaign_state"])),
        activated_at_ns=int(row["activated_at_ns"]) if row.get("activated_at_ns") is not None else None,
        first_lock_at_ns=int(row["first_lock_at_ns"]) if row.get("first_lock_at_ns") is not None else None,
        forward_test_session_id=(
            str(row["forward_test_session_id"]) if row.get("forward_test_session_id") else None
        ),
        created_at_ns=int(row["created_at_ns"]),
        updated_at_ns=int(row["updated_at_ns"]),
    )


def get_active_binding(
    connection: LocalStateConnection,
    *,
    account_id: str,
) -> CampaignBinding | None:
    row = connection.execute(
        """
        SELECT * FROM forward_test_campaign_bindings
        WHERE account_id=? AND campaign_state=?
        ORDER BY activated_at_ns DESC, created_at_ns DESC
        LIMIT 1
        """,
        (account_id, CampaignBindingState.ACTIVE.value),
    ).fetchone()
    return None if row is None else binding_from_row(dict(row))


def assert_no_concurrent_campaign(
    connection: LocalStateConnection,
    *,
    account_id: str,
    campaign_id: str | None = None,
) -> None:
    active = get_active_binding(connection, account_id=account_id)
    if active is None:
        return
    if campaign_id and active.campaign_id == campaign_id:
        return
    raise CampaignBindingError("FORWARD_TEST_CONCURRENT_CAMPAIGN_ACTIVE")


def claim_active_binding(
    connection: LocalStateConnection,
    *,
    account_id: str,
    manifest: ActivationManifest,
    protocol_ref: ProtocolRef,
    forward_test_session_id: str,
    campaigns_root_override: Path | None = None,
    activated_at_ns: int | None = None,
) -> CampaignBinding:
    campaign_id = manifest.campaign_id or manifest.campaign_slug
    if not campaign_id:
        raise CampaignBindingError("FORWARD_TEST_CAMPAIGN_ID_REQUIRED")
    assert_no_concurrent_campaign(connection, account_id=account_id, campaign_id=campaign_id)
    existing = get_active_binding(connection, account_id=account_id)
    now_ns = activated_at_ns or time.time_ns()
    manifest_fp = compute_manifest_fingerprint(manifest.raw)
    manifest_file = manifest_path(
        manifest.campaign_slug,
        campaigns_root_override=campaigns_root_override,
    )
    if existing is not None and existing.campaign_id == campaign_id:
        if existing.manifest_fingerprint != manifest_fp:
            raise CampaignBindingError("ACTIVATION_MANIFEST_FINGERPRINT_MISMATCH")
        if existing.protocol_sha256 != protocol_ref.protocol_doc_sha256:
            raise CampaignBindingError("PROTOCOL_REF_DOC_SHA256_MISMATCH")
        return existing
    binding = CampaignBinding(
        campaign_id=campaign_id,
        account_id=account_id,
        manifest_fingerprint=manifest_fp,
        manifest_path=str(manifest_file),
        protocol_id=protocol_ref.protocol_id or manifest.protocol_id,
        protocol_sha256=protocol_ref.protocol_doc_sha256,
        campaign_state=CampaignBindingState.ACTIVE,
        activated_at_ns=now_ns,
        first_lock_at_ns=None,
        forward_test_session_id=forward_test_session_id,
        created_at_ns=now_ns,
        updated_at_ns=now_ns,
    )
    try:
        connection.execute(
            """
            INSERT INTO forward_test_campaign_bindings(
                campaign_id, account_id, manifest_fingerprint, manifest_path,
                protocol_id, protocol_sha256, campaign_state, activated_at_ns,
                first_lock_at_ns, forward_test_session_id, created_at_ns, updated_at_ns
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                binding.campaign_id,
                binding.account_id,
                binding.manifest_fingerprint,
                binding.manifest_path,
                binding.protocol_id,
                binding.protocol_sha256,
                binding.campaign_state.value,
                binding.activated_at_ns,
                binding.first_lock_at_ns,
                binding.forward_test_session_id,
                binding.created_at_ns,
                binding.updated_at_ns,
            ),
        )
    except sqlite3.IntegrityError as exc:
        raise CampaignBindingError("FORWARD_TEST_CONCURRENT_CAMPAIGN_ACTIVE") from exc
    return binding


def release_binding(
    connection: LocalStateConnection,
    *,
    account_id: str,
    campaign_id: str | None = None,
    released_at_ns: int | None = None,
) -> CampaignBinding | None:
    active = get_active_binding(connection, account_id=account_id)
    if active is None:
        return None
    if campaign_id and active.campaign_id != campaign_id:
        return None
    now_ns = released_at_ns or monotonic_wall_ns()
    connection.execute(
        """
        UPDATE forward_test_campaign_bindings
        SET campaign_state=?, updated_at_ns=?
        WHERE campaign_id=? AND account_id=? AND campaign_state=?
        """,
        (
            CampaignBindingState.RELEASED.value,
            now_ns,
            active.campaign_id,
            account_id,
            CampaignBindingState.ACTIVE.value,
        ),
    )
    return binding_from_row(
        {
            **active.to_dict(),
            "campaign_state": CampaignBindingState.RELEASED.value,
            "updated_at_ns": now_ns,
        }
    )


def record_first_lock_at_ns(
    connection: LocalStateConnection,
    *,
    account_id: str,
    campaign_id: str,
    first_lock_at_ns: int,
) -> None:
    active = get_active_binding(connection, account_id=account_id)
    if active is None or active.campaign_id != campaign_id:
        return
    if active.first_lock_at_ns is not None:
        return
    now_ns = monotonic_wall_ns()
    connection.execute(
        """
        UPDATE forward_test_campaign_bindings
        SET first_lock_at_ns=?, updated_at_ns=?
        WHERE campaign_id=? AND account_id=? AND campaign_state=?
        """,
        (
            first_lock_at_ns,
            now_ns,
            campaign_id,
            account_id,
            CampaignBindingState.ACTIVE.value,
        ),
    )


def build_binding_from_activation(
    *,
    account_id: str,
    manifest: ActivationManifest,
    campaign_slug: str,
    forward_test_session_id: str,
    campaigns_root_override: Path | None = None,
    activated_at_ns: int | None = None,
) -> CampaignBinding:
    protocol_ref = verify_protocol_ref(campaign_slug, campaigns_root_override=campaigns_root_override)
    campaign_id = manifest.campaign_id or manifest.campaign_slug
    now_ns = activated_at_ns or time.time_ns()
    manifest_fp = compute_manifest_fingerprint(manifest.raw)
    manifest_file = manifest_path(campaign_slug, campaigns_root_override=campaigns_root_override)
    return CampaignBinding(
        campaign_id=campaign_id,
        account_id=account_id,
        manifest_fingerprint=manifest_fp,
        manifest_path=str(manifest_file),
        protocol_id=protocol_ref.protocol_id or manifest.protocol_id,
        protocol_sha256=protocol_ref.protocol_doc_sha256,
        campaign_state=CampaignBindingState.ACTIVE,
        activated_at_ns=now_ns,
        first_lock_at_ns=None,
        forward_test_session_id=forward_test_session_id,
        created_at_ns=now_ns,
        updated_at_ns=now_ns,
    )
