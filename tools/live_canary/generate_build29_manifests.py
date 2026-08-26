"""Generate BUILD 29 live canary artifacts."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from market_platform_foundation.git_ref import read_git_head, read_remote_ref
from market_platform_foundation.intelligence.live_canary import (
    BUILD28_BRANCH,
    BUILD29_KNOWN_LIMITATIONS,
    build_default_canary_policy,
    build_live_portfolio_snapshot,
    canary_policy_v1_to_dict,
    canary_report_v1_to_dict,
    canary_run_v1_to_dict,
    derive_account_fingerprint,
    preview_v1_to_dict,
    prepare_canary_authorization_preview,
)
from market_platform_foundation.intelligence.live_canary.identity import derive_canary_run_id
from market_platform_foundation.intelligence.live_canary.report import build_canary_qualification_report
from market_platform_foundation.intelligence.live_canary.types import CanaryDisposition, LiveCanaryRunV1

ARTIFACT_DIR = ROOT / "artifacts" / "live-canary"
BUILD27_BRANCH = "cloud/build-27-forward-paper-execution"


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    head = read_git_head() or ""
    build28_head = read_remote_ref("origin", BUILD28_BRANCH) or head
    build27_head = read_remote_ref("origin", BUILD27_BRANCH) or head

    policy = build_default_canary_policy(
        broker="tradier.paper",
        account_ref="fp-canary-preview",
        required_broker_certification_ref="BUILD28_ZERO_SUBMIT",
    )
    portfolio = build_live_portfolio_snapshot(
        as_of_ns=1_700_000_000_000_000_000,
        broker=policy.broker,
        account_ref=policy.account_ref,
        cash_minor=10_000_00,
    )
    fingerprint = derive_account_fingerprint(policy.account_ref)
    preview = prepare_canary_authorization_preview(
        policy=policy,
        broker=policy.broker,
        account_ref=policy.account_ref,
        account_fingerprint=fingerprint,
        generated_at_ns=1_700_000_000_000_000_000,
        starting_positions=portfolio.positions,
        starting_open_orders=portfolio.open_orders,
        known_limitations=BUILD29_KNOWN_LIMITATIONS,
    )

    run = LiveCanaryRunV1(
        canary_run_id="",
        schema_version="1",
        source_build28_ref=build28_head,
        source_build27_ref=build27_head,
        source_head=head,
        canary_policy_ref=policy.canary_policy_id,
        authorization_ref=None,
        broker=policy.broker,
        account_ref=policy.account_ref,
        start_time_ns=1_700_000_000_000_000_000,
        end_time_ns=None,
        allowed_order_count=policy.max_order_count,
        allowed_notional_minor=policy.max_total_canary_notional_minor,
        initial_reconciliation_ref=None,
        initial_portfolio_ref=portfolio.snapshot_id,
        runtime_activation_ref=policy.required_runtime_activation_ref,
        execution_policy_ref=policy.required_execution_policy_ref,
        champion_ref=None,
        metadata={"human_approved": False},
    )
    object.__setattr__(run, "canary_run_id", derive_canary_run_id(run))

    report = build_canary_qualification_report(
        canary_run=run,
        authorization_ref=None,
        disposition=CanaryDisposition.CANARY_NOT_EXECUTED,
        limitations=BUILD29_KNOWN_LIMITATIONS + ("REAL_CANARY_NOT_EXECUTED", "NO_EXPLICIT_HUMAN_AUTHORIZATION"),
    )

    policy_path = ARTIFACT_DIR / "BUILD29_CANARY_POLICY.json"
    preview_path = ARTIFACT_DIR / "BUILD29_AUTHORIZATION_PREVIEW.json"
    run_path = ARTIFACT_DIR / "BUILD29_CANARY_RUN_MANIFEST.json"
    evidence_path = ARTIFACT_DIR / "BUILD29_LIVE_CANARY_EVIDENCE.json"
    report_path = ARTIFACT_DIR / "BUILD29_CANARY_REPORT.json"
    limitations_path = ARTIFACT_DIR / "BUILD29_KNOWN_LIMITATIONS.md"

    policy_path.write_text(json.dumps(canary_policy_v1_to_dict(policy), indent=2))
    preview_path.write_text(json.dumps(preview_v1_to_dict(preview), indent=2))
    run_path.write_text(json.dumps(canary_run_v1_to_dict(run), indent=2))
    evidence_path.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "human_authorized": False,
                "real_submit_count": 0,
                "preview_id": preview.preview_id,
                "canary_run_id": run.canary_run_id,
            },
            indent=2,
        )
    )
    report_path.write_text(json.dumps(canary_report_v1_to_dict(report), indent=2))
    limitations_path.write_text(
        "# BUILD 29 Known Limitations\n\n"
        + "\n".join(f"- {item}" for item in BUILD29_KNOWN_LIMITATIONS)
        + "\n- REAL_CANARY_NOT_EXECUTED\n- NO_EXPLICIT_HUMAN_AUTHORIZATION\n"
    )

    hashes = {
        p.name: _file_hash(p)
        for p in [
            policy_path,
            preview_path,
            run_path,
            evidence_path,
            report_path,
            limitations_path,
        ]
    }
    (ARTIFACT_DIR / "BUILD29_FILE_HASHES.json").write_text(json.dumps(hashes, indent=2))
    print(f"BUILD 29 artifacts written to {ARTIFACT_DIR}")


if __name__ == "__main__":
    main()
