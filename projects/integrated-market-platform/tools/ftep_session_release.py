"""Governed FTEP campaign binding release (operator session-release)."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def _artifact_dir_for_slug(campaign_slug: str) -> str:
    return campaign_slug.lower().replace("_", "-")


def _persistence_configured() -> bool:
    return os.environ.get("IMP_PERSIST_STATE") == "1" or bool(os.environ.get("IMP_STATE_DIR"))


def collect_session_release_gates(
    repository_root: Path,
    campaign_slug: str,
    *,
    account_id: str,
    campaign_id: str | None = None,
    session_id: str | None = None,
    expect_manifest_fingerprint: str | None = None,
    expect_manifest_path_substring: str | None = None,
    require_frozen_manifest_fingerprint: bool = False,
    require_persistence: bool = False,
) -> dict[str, object]:
    src = repository_root / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))

    from market_platform_foundation.intelligence.paper_forward_bridge.activation import (
        ActivationManifestStatus,
        load_activation_manifest,
    )
    from market_platform_foundation.intelligence.paper_forward_bridge.campaign_binding import (
        CampaignBindingState,
        get_active_binding,
    )
    from market_platform_foundation.local_state.startup import open_local_state

    blockers: list[str] = []
    if require_persistence and not _persistence_configured():
        blockers.append("PERSISTENCE_NOT_CONFIGURED")

    active_binding: dict[str, Any] | None = None
    if not blockers:
        local = open_local_state()
        if local is None:
            blockers.append("PERSISTENCE_DISABLED")
        else:
            binding = get_active_binding(local.connection, account_id=account_id)
            if binding is None:
                blockers.append("NO_ACTIVE_BINDING")
            else:
                active_binding = binding.to_dict()
                if binding.campaign_state != CampaignBindingState.ACTIVE:
                    blockers.append("BINDING_NOT_ACTIVE")
                if campaign_id and binding.campaign_id != campaign_id:
                    blockers.append("CAMPAIGN_ID_MISMATCH")
                if session_id and binding.forward_test_session_id != session_id:
                    blockers.append("SESSION_ID_MISMATCH")
                if expect_manifest_fingerprint:
                    expected = expect_manifest_fingerprint.strip().upper()
                    actual = binding.manifest_fingerprint.strip().upper()
                    if actual != expected:
                        blockers.append("MANIFEST_FINGERPRINT_MISMATCH")
                if expect_manifest_path_substring:
                    if expect_manifest_path_substring not in binding.manifest_path:
                        blockers.append("MANIFEST_PATH_MISMATCH")
                if require_frozen_manifest_fingerprint:
                    manifest = load_activation_manifest(campaign_slug)
                    if manifest.status != ActivationManifestStatus.FROZEN:
                        blockers.append("ACTIVATION_MANIFEST_NOT_FROZEN")
                    else:
                        frozen_fp = str(
                            manifest.manifest_fingerprint or manifest.raw.get("fingerprint") or ""
                        ).strip().upper()
                        actual_fp = binding.manifest_fingerprint.strip().upper()
                        if frozen_fp and actual_fp != frozen_fp:
                            blockers.append("FROZEN_MANIFEST_FINGERPRINT_MISMATCH")

    would_release = not blockers
    payload: dict[str, object] = {
        "schema_version": "1.0.0",
        "artifact_kind": "ftep_session_release_gate",
        "campaign_slug": campaign_slug,
        "account_id": account_id,
        "dry_run": not require_persistence,
        "would_release_binding": would_release,
        "blockers": blockers,
        "active_binding": active_binding,
        "secrets_included": False,
    }
    if expect_manifest_fingerprint:
        payload["expect_manifest_fingerprint"] = expect_manifest_fingerprint.strip().upper()
    if expect_manifest_path_substring:
        payload["expect_manifest_path_substring"] = expect_manifest_path_substring
    if require_frozen_manifest_fingerprint:
        payload["require_frozen_manifest_fingerprint"] = True
    if campaign_id:
        payload["campaign_id"] = campaign_id
    if session_id:
        payload["session_id"] = session_id
    return payload


def append_session_release_evidence(
    repository_root: Path,
    campaign_slug: str,
    record: dict[str, Any],
) -> Path:
    artifact_dir = repository_root / "artifacts" / _artifact_dir_for_slug(campaign_slug)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    path = artifact_dir / "governed-session-release-evidence.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
    return path


def execute_governed_session_release(
    repository_root: Path,
    campaign_slug: str,
    *,
    account_id: str,
    campaign_id: str | None = None,
    session_id: str | None = None,
    expect_manifest_fingerprint: str | None = None,
    expect_manifest_path_substring: str | None = None,
    require_frozen_manifest_fingerprint: bool = False,
) -> tuple[dict[str, object], int]:
    gate = collect_session_release_gates(
        repository_root,
        campaign_slug,
        account_id=account_id,
        campaign_id=campaign_id,
        session_id=session_id,
        expect_manifest_fingerprint=expect_manifest_fingerprint,
        expect_manifest_path_substring=expect_manifest_path_substring,
        require_frozen_manifest_fingerprint=require_frozen_manifest_fingerprint,
        require_persistence=True,
    )
    gate["dry_run"] = False
    gate["artifact_kind"] = "ftep_session_release_result"

    if not gate.get("would_release_binding"):
        gate["binding_released"] = None
        return gate, 1

    from market_platform_foundation.intelligence.paper_forward_bridge import (
        create_forward_test_repository,
    )
    from market_platform_foundation.intelligence.paper_forward_bridge.campaign_binding import (
        CampaignBindingState,
        get_active_binding,
    )
    from market_platform_foundation.local_state.startup import open_local_state

    local = open_local_state()
    if local is None:
        gate.setdefault("blockers", [])
        if "PERSISTENCE_DISABLED" not in gate["blockers"]:
            gate["blockers"].append("PERSISTENCE_DISABLED")
        gate["binding_released"] = None
        return gate, 1

    repo = create_forward_test_repository(connection=local.connection)
    released = repo.release_binding(
        account_id=account_id,
        campaign_id=campaign_id,
    )
    if released is None or released.campaign_state != CampaignBindingState.RELEASED:
        gate.setdefault("blockers", [])
        if "RELEASE_BINDING_FAILED" not in gate["blockers"]:
            gate["blockers"].append("RELEASE_BINDING_FAILED")
        gate["binding_released"] = None
        return gate, 1

    still_active = get_active_binding(local.connection, account_id=account_id)
    if still_active is not None:
        gate.setdefault("blockers", [])
        if "ACTIVE_BINDING_REMAINS" not in gate["blockers"]:
            gate["blockers"].append("ACTIVE_BINDING_REMAINS")
        gate["binding_released"] = released.to_dict()
        return gate, 1

    gate["binding_released"] = released.to_dict()
    gate["would_release_binding"] = True

    evidence_record = {
        "schema_version": "1.0.0",
        "artifact_kind": "ftep_governed_session_release_evidence",
        "campaign_slug": campaign_slug,
        "recorded_at_ns": time.time_ns(),
        "account_id": account_id,
        "binding_released": released.to_dict(),
        "secrets_included": False,
    }
    evidence_path = append_session_release_evidence(repository_root, campaign_slug, evidence_record)
    gate["evidence_paths"] = [str(evidence_path)]
    return gate, 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "campaign_slug",
        nargs="?",
        default="FTEP-V1-002",
        help="Forward-test campaign slug for evidence routing (default: FTEP-V1-002)",
    )
    parser.add_argument(
        "--account-id",
        required=True,
        help="Paper account id scoped to the active campaign binding",
    )
    parser.add_argument(
        "--campaign-id",
        help="Optional campaign id; fail closed when active binding differs",
    )
    parser.add_argument(
        "--session-id",
        help="Optional forward_test_session_id; fail closed when binding differs",
    )
    parser.add_argument(
        "--expect-manifest-fingerprint",
        help="Fail closed unless the active binding fingerprint matches exactly",
    )
    parser.add_argument(
        "--expect-manifest-path-substring",
        help="Fail closed unless manifest_path contains this substring (fixture guard)",
    )
    parser.add_argument(
        "--require-frozen-manifest-fingerprint",
        action="store_true",
        help="Fail closed when active binding fingerprint differs from frozen manifest",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate release gates without durable writes",
    )
    parser.add_argument("--json", action="store_true", help="Machine-readable JSON")
    args = parser.parse_args(argv)

    if args.dry_run:
        payload = collect_session_release_gates(
            ROOT,
            args.campaign_slug,
            account_id=args.account_id,
            campaign_id=args.campaign_id,
            session_id=args.session_id,
            expect_manifest_fingerprint=args.expect_manifest_fingerprint,
            expect_manifest_path_substring=args.expect_manifest_path_substring,
            require_frozen_manifest_fingerprint=args.require_frozen_manifest_fingerprint,
            require_persistence=False,
        )
        payload["dry_run"] = True
        exit_code = 0 if payload["would_release_binding"] else 1
    else:
        payload, exit_code = execute_governed_session_release(
            ROOT,
            args.campaign_slug,
            account_id=args.account_id,
            campaign_id=args.campaign_id,
            session_id=args.session_id,
            expect_manifest_fingerprint=args.expect_manifest_fingerprint,
            expect_manifest_path_substring=args.expect_manifest_path_substring,
            require_frozen_manifest_fingerprint=args.require_frozen_manifest_fingerprint,
        )

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif args.dry_run:
        print(
            f"would_release_binding={payload['would_release_binding']} "
            f"blockers={payload['blockers']}"
        )
    else:
        released = payload.get("binding_released")
        print(
            f"released={'yes' if released else 'no'} "
            f"evidence={payload.get('evidence_paths')}"
        )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
