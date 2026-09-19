"""RTH empirical operations command center — thin coordination over existing tools.

Software-only: never places orders, never creates empirical locks, never enables
live ingress unless the operator explicitly sets temporary env gates outside this
module. Does not declare FTEP ``EMPIRICAL_ACTIVE`` or empirical evidence gates.
"""

from __future__ import annotations

import argparse
import json
import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..git_ref import read_git_head
from ..intelligence.paper_forward_bridge.campaign_status import collect_ftep_campaign_status
from ..intelligence.paper_forward_bridge.ftep_catalyst_watch import collect_ftep_catalyst_watch
from ..intelligence.paper_forward_bridge.ftep_finviz_prospective_preflight import (
    FtepFinvizProspectivePreflightOptions,
    run_ftep_finviz_prospective_preflight,
)
from ..intelligence.paper_forward_bridge.ftep_integrity import collect_ftep_integrity_checks
from ..intelligence.paper_forward_bridge.ftep_prospective_catalyst_ingress import (
    _INGRESS_ENV,
    prospective_catalyst_ingress_enabled,
)
from ..intelligence.paper_forward_bridge.session_policy import (
    CALENDAR_US_EQUITY_RTH,
    is_within_us_equity_rth,
)
from ..intelligence.production.corpus_collection_status import run_governed_corpus_collection_status
from ..local_state.paths import REPO_ROOT, persistence_enabled, state_dir
from ..paper.calibration.bar_ohlcv_prospective_proof import (
    READINESS_RTH_REQUIRED,
    item9_prospective_readiness,
    prospective_run_without_poll_outcome,
)
from ..paper.calibration.runner import (
    STATUS_COMPARATOR_NOT_CONFIGURED,
    alpaca_paper_configured,
    classify_calibration_run,
)
from ..providers.adapters.finviz_elite_context import configured_token, finviz_live_enabled
from ..providers.adapters.moomoo_opend_equity_quote import opend_moomoo_auth_entitlements
from ..providers.equity_quote_selection import opend_readiness
from .runtime_resilience_diagnostic import build_runtime_resilience_diagnostic

ACCEPTANCE_LABEL_READY = "RTH_EMPIRICAL_OPS_READY"
ARTIFACT_KIND_PREFLIGHT = "rth_empirical_ops_preflight"
ARTIFACT_KIND_RUN = "rth_empirical_ops_run"
_SCHEMA_VERSION = "1.0.0"
_DEFAULT_CAMPAIGN = "FTEP-V1-002"

_SECRET_SUBSTRINGS = (
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "credential",
    "login_json_paths",
    "token_txt_paths",
)


def _now_ns(explicit: int | None) -> int:
    return explicit if explicit is not None else time.time_ns()


def _operator_run_id() -> str:
    return f"RTHOPS-{uuid.uuid4().hex[:12].upper()}"


def _runtime_git_sha(repository_root: Path) -> str | None:
    return read_git_head(start=repository_root)


def _finviz_credential_presence(repository_root: Path, env: Mapping[str, str]) -> dict[str, str]:
    from ..intelligence.paper_forward_bridge.ftep_finviz_prospective_preflight import (
        _private_credential_paths,
    )

    cred = _private_credential_paths(repository_root)
    token_ok = bool(configured_token(env)) or cred.get("finviz_login_present") or cred.get("finviz_token_file_present")
    return {
        "finviz_login": "PRESENT" if cred.get("finviz_login_present") else "ABSENT",
        "finviz_token_file": "PRESENT" if cred.get("finviz_token_file_present") else "ABSENT",
        "finviz_token_configured": "VALID" if token_ok else "INVALID",
    }


def _redact_secrets(payload: Any) -> Any:
    if isinstance(payload, dict):
        cleaned: dict[str, Any] = {}
        for key, value in payload.items():
            lowered = str(key).lower()
            if any(part in lowered for part in _SECRET_SUBSTRINGS):
                if isinstance(value, bool):
                    cleaned[key] = "PRESENT" if value else "ABSENT"
                elif isinstance(value, list):
                    cleaned[key] = f"COUNT_{len(value)}"
                else:
                    cleaned[key] = "REDACTED"
            else:
                cleaned[key] = _redact_secrets(value)
        return cleaned
    if isinstance(payload, list):
        return [_redact_secrets(item) for item in payload]
    return payload


def _moomoo_auth_entitlements(
    *,
    host: str,
    port: int,
    reachable: bool,
) -> tuple[dict[str, str], dict[str, Any]]:
    return opend_moomoo_auth_entitlements(host=host, port=port, reachable=reachable)


def _paper_comparator_configuration(env: Mapping[str, str], now_ns: int) -> dict[str, Any]:
    configured = alpaca_paper_configured(env)
    status = classify_calibration_run(env=env, now_ns=now_ns)
    return {
        "alpaca_paper_credentials": "PRESENT" if configured else "ABSENT",
        "harness_status": status,
        "orders_placed": False,
        "calibrated": False,
        "comparator_not_configured": status == STATUS_COMPARATOR_NOT_CONFIGURED,
    }


def _finviz_observational_gate(finviz_preflight: dict[str, Any]) -> str:
    disposition = str(finviz_preflight.get("disposition") or "BLOCKED")
    if disposition == "READY":
        return "READY"
    if disposition == "SOFTWARE_READY_RTH_REQUIRED":
        return READINESS_RTH_REQUIRED
    return "BLOCKED"


def _prospective_catalyst_gate(env: Mapping[str, str]) -> str:
    live = finviz_live_enabled(env)
    ingress = prospective_catalyst_ingress_enabled(env)
    if live and ingress:
        return "ENABLED"
    if ingress and not live:
        return "INVALID_FINVIZ_LIVE_REQUIRED"
    return "DISABLED"


@dataclass(frozen=True, slots=True)
class RthEmpiricalOpsOptions:
    campaign_slug: str = _DEFAULT_CAMPAIGN
    now_ns: int | None = None
    training_cutoff_ns: int | None = None
    instrument_id: str = "AAPL"
    write_run_artifact: bool = False


def run_rth_empirical_ops_preflight(
    repository_root: Path,
    *,
    options: RthEmpiricalOpsOptions | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    opts = options or RthEmpiricalOpsOptions()
    mapping = env if env is not None else os.environ
    now = _now_ns(opts.now_ns)
    rth_open = is_within_us_equity_rth(now)

    finviz_report = run_ftep_finviz_prospective_preflight(
        repository_root,
        options=FtepFinvizProspectivePreflightOptions(
            campaign_slug=opts.campaign_slug,
            now_ns=now,
        ),
        env=mapping,
    )
    integrity = collect_ftep_integrity_checks(repository_root, opts.campaign_slug)
    status = collect_ftep_campaign_status(repository_root, opts.campaign_slug)
    readiness = opend_readiness()
    moomoo_auth, moomoo_entitlements = _moomoo_auth_entitlements(
        host=readiness.host,
        port=readiness.port,
        reachable=readiness.reachable,
    )
    finviz_cred = _finviz_credential_presence(repository_root, mapping)
    comparator = _paper_comparator_configuration(mapping, now)
    item9 = item9_prospective_readiness(now_ns=now)

    training_cutoff = opts.training_cutoff_ns if opts.training_cutoff_ns is not None else now
    item7_report, _, _, _ = run_governed_corpus_collection_status(
        training_cutoff_ns=training_cutoff,
        repo_root=repository_root,
        persistence_root=state_dir() if persistence_enabled() else None,
        now_ns=now,
    )
    item7_body = item7_report.to_dict()

    hard_blockers: list[str] = []
    if finviz_report.get("disposition") == "BLOCKED":
        hard_blockers.append("FINVIZ_PREFLIGHT_BLOCKED")
    if integrity.get("disposition") != "PASS":
        hard_blockers.append("FTEP_INTEGRITY_NOT_PASS")
    if finviz_cred["finviz_token_configured"] == "INVALID":
        hard_blockers.append("FINVIZ_CREDENTIALS_ABSENT")

    soft_codes: list[str] = []
    if not rth_open:
        soft_codes.append(READINESS_RTH_REQUIRED)
    if _prospective_catalyst_gate(mapping) == "DISABLED":
        soft_codes.append("PROSPECTIVE_CATALYST_GATE_DISABLED")
    if _finviz_observational_gate(finviz_report) == READINESS_RTH_REQUIRED:
        soft_codes.append("FINVIZ_OBSERVATIONAL_RTH_REQUIRED")

    acceptance = ACCEPTANCE_LABEL_READY if not hard_blockers else "RTH_EMPIRICAL_OPS_BLOCKED"
    disposition = "BLOCKED" if hard_blockers else (
        READINESS_RTH_REQUIRED if not rth_open else "READY"
    )

    body: dict[str, Any] = {
        "artifact_kind": ARTIFACT_KIND_PREFLIGHT,
        "schema_version": _SCHEMA_VERSION,
        "acceptance_label": acceptance,
        "campaign_slug": opts.campaign_slug,
        "calendar_scope": CALENDAR_US_EQUITY_RTH,
        "observed_at_ns": now,
        "runtime_git_sha": _runtime_git_sha(repository_root),
        "canonical_imp_state_dir": str(state_dir()),
        "persistence_enabled": persistence_enabled(),
        "us_equity_rth_open": rth_open,
        "disposition": disposition,
        "hard_blockers": hard_blockers,
        "soft_codes": soft_codes,
        "ftep_integrity": integrity.get("disposition"),
        "governed_session_count": int(status.get("governed_session_count") or 0),
        "empirical_lock_count": int(status.get("empirical_lock_count") or 0),
        "ftep_empirical_active": False,
        "rth_status": "OPEN" if rth_open else "CLOSED",
        "opend_reachability": "REACHABLE" if readiness.reachable else "UNREACHABLE",
        "opend_endpoint": {"host": readiness.host, "port": readiness.port, "loopback": readiness.loopback},
        "moomoo_auth": moomoo_auth,
        "moomoo_entitlements": moomoo_entitlements,
        "finviz_credentials": finviz_cred,
        "finviz_observational_gate": _finviz_observational_gate(finviz_report),
        "prospective_catalyst_gate": _prospective_catalyst_gate(mapping),
        "prospective_catalyst_ingress_env": _INGRESS_ENV,
        "finviz_live_gate": "ENABLED" if finviz_live_enabled(mapping) else "DISABLED",
        "item7_collector_readiness": {
            "status": item7_body.get("status"),
            "acceptance_label": item7_body.get("acceptance_label"),
            "market_rth_open": item7_body.get("market_rth_open"),
            "blockers": list(item7_body.get("blockers") or ()),
        },
        "item9_tool_readiness": item9,
        "runtime_resilience": build_runtime_resilience_diagnostic(
            repository_root,
            env=mapping,
            now_ns=now,
        ),
        "paper_comparator": comparator,
        "delegated_preflight": {
            "ftep_finviz_prospective_preflight": _redact_secrets(finviz_report),
        },
        "operator_commands": {
            "finviz_preflight": f"python tools/ftep_finviz_prospective_preflight.py {opts.campaign_slug} --json",
            "catalyst_watch_dry_run": (
                f"python tools/ftep_watch_catalysts.py {opts.campaign_slug} --dry-run --json"
            ),
            "item9_readiness": "python tools/moomoo/opend_bar_1m_prospective_proof.py readiness",
            "item7_status": "python tools/item7_corpus_collector.py status --persistence-root %IMP_STATE_DIR%",
            "ftep_integrity": f"python tools/imp.py ftep integrity-check {opts.campaign_slug} --json",
        },
        "secrets_included": False,
        "evidence_class": "SOFTWARE",
    }
    return body


def run_rth_empirical_observational_dry_run(
    repository_root: Path,
    *,
    options: RthEmpiricalOpsOptions | None = None,
    env: Mapping[str, str] | None = None,
    live_ingress: bool = False,
) -> dict[str, Any]:
    """Coordinate observational paths in dry-run / closed-market safe mode."""

    opts = options or RthEmpiricalOpsOptions()
    mapping = env if env is not None else os.environ
    now = _now_ns(opts.now_ns)
    rth_open = is_within_us_equity_rth(now)
    run_id = _operator_run_id()
    operator_surfaced_at = time.time_ns()

    if live_ingress:
        return {
            "artifact_kind": ARTIFACT_KIND_RUN,
            "schema_version": _SCHEMA_VERSION,
            "operator_run_id": run_id,
            "ok": False,
            "reason_code": "LIVE_INGRESS_REFUSED_BY_OPS_LAYER",
            "message": "Set temporary env gates in the operator shell only; ops CLI refuses live ingress.",
            "evidence_class": "SOFTWARE",
        }

    signal_time_ns = now
    item9_outcome = prospective_run_without_poll_outcome(
        now_ns=now,
        signal_time_ns=signal_time_ns,
        signal_established_at_ns=signal_time_ns,
    )
    finviz_watch = collect_ftep_catalyst_watch(
        repository_root,
        opts.campaign_slug,
        fixture_only=False,
        live_ingress=False,
    )
    training_cutoff = opts.training_cutoff_ns if opts.training_cutoff_ns is not None else now
    item7_report, _, _, _ = run_governed_corpus_collection_status(
        training_cutoff_ns=training_cutoff,
        repo_root=repository_root,
        persistence_root=state_dir() if persistence_enabled() else None,
        now_ns=now,
    )

    timing: dict[str, int | None] = {
        "source_event_at": None,
        "imp_received_at": operator_surfaced_at,
        "normalized_at": None,
        "detected_at": None,
        "opportunity_created_at": None,
        "operator_surfaced_at": operator_surfaced_at,
    }
    if rth_open:
        timing["source_event_at"] = signal_time_ns

    reason = READINESS_RTH_REQUIRED if not rth_open else item9_outcome.get("reason_code")
    ok = False

    payload: dict[str, Any] = {
        "artifact_kind": ARTIFACT_KIND_RUN,
        "schema_version": _SCHEMA_VERSION,
        "operator_run_id": run_id,
        "campaign_slug": opts.campaign_slug,
        "mode": "DRY_RUN_OBSERVATIONAL",
        "live_ingress": False,
        "ok": ok,
        "reason_code": reason,
        "us_equity_rth_open": rth_open,
        "orders_placed": False,
        "calibrated": False,
        "empirical_lock_created": False,
        "ftep_empirical_active": False,
        "timing_ns": timing,
        "sub_artifacts": {
            "ftep_catalyst_watch": {
                "artifact_kind": finviz_watch.get("artifact_kind"),
                "dry_run": finviz_watch.get("dry_run"),
                "watch_mode": finviz_watch.get("watch_mode"),
                "disposition": finviz_watch.get("disposition"),
            },
            "item9_prospective": _redact_secrets(item9_outcome),
            "item7_corpus_status": {
                "status": item7_report.status,
                "acceptance_label": item7_report.acceptance_label,
                "market_rth_open": item7_report.market_rth_open,
            },
        },
        "evidence_class": "SOFTWARE",
    }

    if opts.write_run_artifact and persistence_enabled():
        out_dir = state_dir(create=True) / "rth-empirical-ops" / "runs"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{run_id}.json"
        out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        payload["run_artifact_path"] = str(out_path)

    return payload


def summarize_rth_empirical_ops(
    repository_root: Path,
    *,
    options: RthEmpiricalOpsOptions | None = None,
) -> dict[str, Any]:
    opts = options or RthEmpiricalOpsOptions()
    now = _now_ns(opts.now_ns)
    runs_dir = state_dir() / "rth-empirical-ops" / "runs"
    latest_run: dict[str, Any] | None = None
    latest_path: Path | None = None
    if runs_dir.is_dir():
        candidates = sorted(runs_dir.glob("RTHOPS-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        if candidates:
            latest_path = candidates[0]
            try:
                latest_run = json.loads(latest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                latest_run = None

    preflight = run_rth_empirical_ops_preflight(repository_root, options=opts)
    return {
        "artifact_kind": "rth_empirical_ops_summary",
        "schema_version": _SCHEMA_VERSION,
        "observed_at_ns": now,
        "acceptance_label": preflight.get("acceptance_label"),
        "preflight_disposition": preflight.get("disposition"),
        "latest_operator_run": latest_run,
        "latest_operator_run_path": str(latest_path) if latest_path else None,
        "evidence_class": "SOFTWARE",
    }


def build_rth_empirical_ops_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "RTH empirical operations command center (software-only). "
            "Coordinates preflight, dry-run observational wiring, status, and summarize."
        ),
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    parser.add_argument("--now-ns", type=int, default=None, help="Test-only clock override.")
    parser.add_argument("--campaign", default=_DEFAULT_CAMPAIGN, help="FTEP campaign slug.")
    parser.add_argument(
        "--training-cutoff-ns",
        type=int,
        default=None,
        help="Item 7 training cutoff (default: observation time).",
    )
    parser.add_argument(
        "--write-run-artifact",
        action="store_true",
        help="Persist run-observational JSON under IMP_STATE_DIR (never touches FTEP locks).",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("preflight", help="Independent coordinated preflight (secrets redacted).")
    sub.add_parser("status", help="Lightweight status from latest preflight fields.")
    sub.add_parser(
        "run-observational",
        help="Dry-run observational wiring (no live ingress; no orders).",
    )
    sub.add_parser("summarize", help="Preflight plus latest operator run artifact if present.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_rth_empirical_ops_parser().parse_args(argv)
    opts = RthEmpiricalOpsOptions(
        campaign_slug=args.campaign,
        now_ns=args.now_ns,
        training_cutoff_ns=args.training_cutoff_ns,
        write_run_artifact=bool(getattr(args, "write_run_artifact", False)),
    )
    env = dict(os.environ)

    if args.command == "preflight":
        report = run_rth_empirical_ops_preflight(REPO_ROOT, options=opts, env=env)
    elif args.command == "status":
        report = run_rth_empirical_ops_preflight(REPO_ROOT, options=opts, env=env)
        report = {
            "artifact_kind": "rth_empirical_ops_status",
            "acceptance_label": report.get("acceptance_label"),
            "disposition": report.get("disposition"),
            "rth_status": report.get("rth_status"),
            "runtime_git_sha": report.get("runtime_git_sha"),
            "canonical_imp_state_dir": report.get("canonical_imp_state_dir"),
            "hard_blockers": report.get("hard_blockers"),
            "soft_codes": report.get("soft_codes"),
            "evidence_class": "SOFTWARE",
        }
    elif args.command == "run-observational":
        report = run_rth_empirical_observational_dry_run(
            REPO_ROOT,
            options=opts,
            env=env,
            live_ingress=False,
        )
    elif args.command == "summarize":
        report = summarize_rth_empirical_ops(REPO_ROOT, options=opts)
    else:
        raise SystemExit(2)

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(json.dumps(report, indent=2, sort_keys=True))

    if args.command == "preflight":
        if report.get("acceptance_label") != ACCEPTANCE_LABEL_READY:
            return 1
        return 0
    if args.command == "run-observational":
        return 0 if report.get("reason_code") == READINESS_RTH_REQUIRED or report.get("ok") else 0
    return 0


__all__ = [
    "ACCEPTANCE_LABEL_READY",
    "ARTIFACT_KIND_PREFLIGHT",
    "ARTIFACT_KIND_RUN",
    "build_rth_empirical_ops_parser",
    "main",
    "run_rth_empirical_ops_preflight",
    "run_rth_empirical_observational_dry_run",
    "summarize_rth_empirical_ops",
]
