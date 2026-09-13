"""Governed FTEP session start gates and SIGNAL_ONLY session creation."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

_COHORT_ARM_INVOKE_KEYS: tuple[tuple[str, str], ...] = (
    ("baseline", "BASELINE"),
    ("ai_enhanced", "AI_ENHANCED"),
)


def _artifact_dir_for_slug(campaign_slug: str) -> str:
    return campaign_slug.lower().replace("_", "-")


def _persistence_configured() -> bool:
    return os.environ.get("IMP_PERSIST_STATE") == "1" or bool(os.environ.get("IMP_STATE_DIR"))


def _build_forward_test_invoke_steps(
    repository_root: Path,
    campaign_slug: str,
) -> list[dict[str, object]]:
    """Secret-free operator plan for governed SIGNAL_ONLY session creation."""

    from market_platform_foundation.intelligence.paper_forward_bridge.activation import (
        load_activation_manifest,
        manifest_universe_symbols,
    )

    manifest = load_activation_manifest(campaign_slug)
    binding = manifest.binding
    account_scope = manifest.raw.get("account_scope") or {}
    scope_account = (
        str(account_scope.get("account_id") or "") if isinstance(account_scope, dict) else ""
    )
    paper_account_id = str(binding.get("paper_account_id") or scope_account)
    horizon_ns = int(binding.get("evaluation_horizon_ns") or 0)
    universe = manifest_universe_symbols(manifest)
    campaign_id = str(manifest.campaign_id or "")
    fingerprint = manifest.manifest_fingerprint

    steps: list[dict[str, object]] = [
        {
            "step": 1,
            "action": "configure_persistence",
            "detail": "Set IMP_PERSIST_STATE=1 or IMP_STATE_DIR before any durable forward-test write.",
        },
        {
            "step": 2,
            "action": "construct_service",
            "detail": (
                "Instantiate ForwardTestService with the governed local replay store "
                "(same path as operator Paper console / forward-test API)."
            ),
        },
    ]
    order = 3
    for manifest_key, cohort_arm in _COHORT_ARM_INVOKE_KEYS:
        arms = binding.get("cohort_arms") or {}
        arm = arms.get(manifest_key)
        if not isinstance(arm, dict):
            continue
        policy_id = str(arm.get("policy_id") or "")
        policy_version = str(arm.get("policy_version") or "1.0.0")
        steps.append(
            {
                "step": order,
                "action": "ForwardTestService.create_session",
                "test_mode": "SIGNAL_ONLY",
                "note": "No Paper order preview/submit; empirical lock only after governed decision path.",
                "kwargs": {
                    "account_id": paper_account_id,
                    "mode": "PAPER",
                    "strategy_id": policy_id,
                    "strategy_version": policy_version,
                    "universe": universe,
                    "evaluation_horizon_ns": horizon_ns,
                    "campaign_id": campaign_id,
                    "campaign_slug": campaign_slug,
                    "cohort_arm": cohort_arm,
                    "manifest_fingerprint": fingerprint,
                    "api_path": True,
                },
            }
        )
        order += 1
    return steps


def collect_session_start_gates(
    repository_root: Path,
    campaign_slug: str,
    *,
    require_persistence: bool = False,
) -> dict[str, object]:
    src = repository_root / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))

    from market_platform_foundation.intelligence.paper_forward_bridge.campaign_status import (
        collect_ftep_campaign_status,
    )
    from market_platform_foundation.intelligence.paper_forward_bridge.ftep_integrity import (
        collect_ftep_integrity_checks,
    )

    blockers: list[str] = []
    if require_persistence and not _persistence_configured():
        blockers.append("PERSISTENCE_NOT_CONFIGURED")

    status = collect_ftep_campaign_status(repository_root, campaign_slug)
    if not status.get("signal_only_authorized"):
        blockers.append("SIGNAL_ONLY_NOT_AUTHORIZED")
    if status.get("manifest_status") != "FROZEN":
        blockers.append("ACTIVATION_MANIFEST_NOT_FROZEN")
    if status.get("campaign_readiness_disposition") != "READY":
        for item in status.get("campaign_readiness_blockers") or ():
            if item not in blockers:
                blockers.append(str(item))
    if not status.get("us_equity_rth_open"):
        blockers.append("US_EQUITY_RTH_CLOSED")

    integrity = collect_ftep_integrity_checks(repository_root, campaign_slug)
    if integrity["disposition"] != "PASS":
        blockers.append("INTEGRITY_CHECK_FAILED")

    would_create = not blockers
    payload: dict[str, object] = {
        "schema_version": "1.0.0",
        "artifact_kind": "ftep_session_start_gate",
        "campaign_slug": campaign_slug,
        "dry_run": not require_persistence,
        "would_create_session": would_create,
        "test_mode": "SIGNAL_ONLY",
        "blockers": blockers,
        "operator_hints": integrity.get("operator_hints") or [],
        "campaign_status": {
            "us_equity_rth_open": status.get("us_equity_rth_open"),
            "manifest_fingerprint": status.get("manifest_fingerprint"),
            "governed_session_count": status.get("governed_session_count"),
            "empirical_lock_count": status.get("empirical_lock_count"),
        },
        "secrets_included": False,
    }
    if would_create:
        payload["forward_test_invoke_steps"] = _build_forward_test_invoke_steps(
            repository_root,
            campaign_slug,
        )
    return payload


def append_session_start_evidence(
    repository_root: Path,
    campaign_slug: str,
    record: dict[str, Any],
) -> Path:
    artifact_dir = repository_root / "artifacts" / _artifact_dir_for_slug(campaign_slug)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    path = artifact_dir / "governed-session-start-evidence.jsonl"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
    return path


def _construct_forward_test_service():
    from market_platform_foundation.intelligence.paper_forward_bridge import (
        ForwardTestService,
        ForwardTestServiceError,
        create_forward_test_repository,
    )
    from market_platform_foundation.local_state.startup import open_local_state

    local = open_local_state()
    if local is None:
        raise ForwardTestServiceError("PERSISTENCE_DISABLED")
    return ForwardTestService(
        create_forward_test_repository(connection=local.connection),
    )


def execute_governed_session_start(
    repository_root: Path,
    campaign_slug: str,
) -> tuple[dict[str, object], int]:
    """Create governed SIGNAL_ONLY sessions when all gates pass (no Paper orders)."""

    gate = collect_session_start_gates(
        repository_root,
        campaign_slug,
        require_persistence=True,
    )
    gate["dry_run"] = False
    gate["artifact_kind"] = "ftep_session_start_result"

    if not gate.get("would_create_session"):
        gate["sessions_created"] = []
        gate["session_errors"] = []
        return gate, 1

    from market_platform_foundation.intelligence.paper_forward_bridge import ForwardTestServiceError

    service = _construct_forward_test_service()
    created_at_ns = time.time_ns()
    sessions_created: list[dict[str, object]] = []
    session_errors: list[dict[str, object]] = []
    steps = gate.pop("forward_test_invoke_steps", [])

    for step in steps:
        if step.get("action") != "ForwardTestService.create_session":
            continue
        kwargs = dict(step.get("kwargs") or {})
        kwargs["created_at_ns"] = created_at_ns
        cohort_arm = kwargs.get("cohort_arm")
        try:
            session = service.create_session(**kwargs)
        except ForwardTestServiceError as exc:
            session_errors.append(
                {
                    "cohort_arm": cohort_arm,
                    "error": str(exc),
                }
            )
            continue
        sessions_created.append(
            {
                "session_id": session.session_id,
                "cohort_arm": str(cohort_arm or ""),
                "campaign_id": session.campaign_id,
                "manifest_fingerprint": session.manifest_fingerprint,
            }
        )

    gate["sessions_created"] = sessions_created
    gate["session_errors"] = session_errors
    gate["would_create_session"] = bool(sessions_created)

    evidence_record = {
        "schema_version": "1.0.0",
        "artifact_kind": "ftep_governed_session_start_evidence",
        "campaign_slug": campaign_slug,
        "recorded_at_ns": time.time_ns(),
        "test_mode": "SIGNAL_ONLY",
        "sessions_created": sessions_created,
        "session_errors": session_errors,
        "manifest_fingerprint": gate.get("campaign_status", {}).get("manifest_fingerprint"),
        "secrets_included": False,
    }
    evidence_path = append_session_start_evidence(repository_root, campaign_slug, evidence_record)
    gate["evidence_paths"] = [str(evidence_path)]

    if not sessions_created:
        gate.setdefault("blockers", [])
        if "SESSION_CREATE_FAILED" not in gate["blockers"]:
            gate["blockers"].append("SESSION_CREATE_FAILED")
        return gate, 1
    return gate, 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "campaign_slug",
        nargs="?",
        default="FTEP-V1-002",
        help="Forward-test campaign slug (default: FTEP-V1-002)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate gates without creating sessions or locks",
    )
    parser.add_argument("--json", action="store_true", help="Machine-readable JSON")
    args = parser.parse_args(argv)

    if args.dry_run:
        payload = collect_session_start_gates(ROOT, args.campaign_slug)
        payload["dry_run"] = True
        exit_code = 0 if payload["would_create_session"] else 1
    else:
        payload, exit_code = execute_governed_session_start(ROOT, args.campaign_slug)

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    elif args.dry_run:
        print(
            f"would_create_session={payload['would_create_session']} blockers={payload['blockers']}"
        )
    else:
        sessions = payload.get("sessions_created") or []
        print(
            f"sessions_created={len(sessions)} "
            f"errors={len(payload.get('session_errors') or [])} "
            f"evidence={payload.get('evidence_paths')}"
        )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
