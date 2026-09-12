"""Governed FTEP session start gates (dry-run only; no locks or durable writes)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_COHORT_ARM_INVOKE_KEYS: tuple[tuple[str, str], ...] = (
    ("baseline", "BASELINE"),
    ("ai_enhanced", "AI_ENHANCED"),
)


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
        "dry_run": True,
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
        help="Validate gates without creating sessions or locks (required)",
    )
    parser.add_argument("--json", action="store_true", help="Machine-readable JSON")
    args = parser.parse_args(argv)

    if not args.dry_run:
        print("Only --dry-run is supported; governed session creation uses ForwardTestService.", file=sys.stderr)
        return 2

    payload = collect_session_start_gates(ROOT, args.campaign_slug)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(
            f"would_create_session={payload['would_create_session']} blockers={payload['blockers']}"
        )
    return 0 if payload["would_create_session"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
