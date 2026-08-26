"""Operator CLI for EVIDENCE-01A forward observation campaigns."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from market_platform_foundation.intelligence.forward_qualification.evidence01a import (
    CampaignEvidenceOrigin,
    CampaignService,
    SessionTerminationReason,
)

DEFAULT_CAMPAIGN_ROOT = ROOT / "artifacts" / "forward-qualification" / "campaigns"


def _add_campaign_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--campaign-id")
    parser.add_argument("--campaign-dir")


def _campaign_dir(args: argparse.Namespace) -> Path:
    if args.campaign_dir:
        return Path(args.campaign_dir)
    if args.campaign_id:
        return DEFAULT_CAMPAIGN_ROOT / args.campaign_id
    raise SystemExit("campaign-dir or campaign-id required")


def cmd_create(args: argparse.Namespace) -> None:
    service = CampaignService.create_campaign(
        campaign_root=DEFAULT_CAMPAIGN_ROOT,
        campaign_name=args.name,
        provider_id=args.provider,
        evidence_origin=CampaignEvidenceOrigin(args.origin),
    )
    spec = service.store.read_spec()
    print(json.dumps({"campaign_id": spec.campaign_id, "campaign_dir": str(service.store.root)}, indent=2))


def cmd_start(args: argparse.Namespace) -> None:
    service = CampaignService.open(_campaign_dir(args))
    state = service.start_campaign()
    print(json.dumps({"campaign_state": state.campaign_state.value}, indent=2))


def cmd_session_start(args: argparse.Namespace) -> None:
    service = CampaignService.open(_campaign_dir(args))
    session = service.start_session()
    print(json.dumps({"session_id": session.session_id}, indent=2))


def cmd_session_stop(args: argparse.Namespace) -> None:
    service = CampaignService.open(_campaign_dir(args))
    session = service.stop_session(reason=SessionTerminationReason.OPERATOR_STOP)
    print(json.dumps({"session_id": session.session_id, "ended_at_ns": session.ended_at_ns}, indent=2))


def cmd_settle(args: argparse.Namespace) -> None:
    service = CampaignService.open(_campaign_dir(args))
    count = service.settle_mature()
    print(json.dumps({"settled": count}, indent=2))


def cmd_checkpoint(args: argparse.Namespace) -> None:
    service = CampaignService.open(_campaign_dir(args))
    checkpoint = service.generate_checkpoint()
    print(json.dumps({"checkpoint_id": checkpoint.checkpoint_id, "disposition": checkpoint.qualification_disposition}, indent=2))


def cmd_status(args: argparse.Namespace) -> None:
    service = CampaignService.open(_campaign_dir(args))
    print(service.show_progress())


def cmd_finalize(args: argparse.Namespace) -> None:
    service = CampaignService.open(_campaign_dir(args))
    report = service.finalize_campaign()
    print(json.dumps({"report_id": report.report_id, "disposition": report.qualification_disposition}, indent=2))


def cmd_abort(args: argparse.Namespace) -> None:
    service = CampaignService.open(_campaign_dir(args))
    state = service.abort_campaign()
    print(json.dumps({"campaign_state": state.campaign_state.value}, indent=2))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="EVIDENCE-01A forward observation campaign")
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create")
    create.add_argument("--name", required=True)
    create.add_argument("--provider", default="MOOMOO")
    create.add_argument("--origin", default=CampaignEvidenceOrigin.LIVE_FORWARD.value)
    create.set_defaults(func=cmd_create)

    start = sub.add_parser("start")
    _add_campaign_args(start)
    start.set_defaults(func=cmd_start)

    session_start = sub.add_parser("session-start")
    _add_campaign_args(session_start)
    session_start.set_defaults(func=cmd_session_start)

    session_stop = sub.add_parser("session-stop")
    _add_campaign_args(session_stop)
    session_stop.set_defaults(func=cmd_session_stop)

    settle = sub.add_parser("settle")
    _add_campaign_args(settle)
    settle.set_defaults(func=cmd_settle)

    checkpoint = sub.add_parser("checkpoint")
    _add_campaign_args(checkpoint)
    checkpoint.set_defaults(func=cmd_checkpoint)

    status = sub.add_parser("status")
    _add_campaign_args(status)
    status.set_defaults(func=cmd_status)

    finalize = sub.add_parser("finalize")
    _add_campaign_args(finalize)
    finalize.set_defaults(func=cmd_finalize)

    abort = sub.add_parser("abort")
    _add_campaign_args(abort)
    abort.set_defaults(func=cmd_abort)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
