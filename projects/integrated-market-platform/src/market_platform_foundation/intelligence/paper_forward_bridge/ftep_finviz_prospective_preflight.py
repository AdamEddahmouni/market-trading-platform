"""FTEP-V1-002 Finviz prospective observation preflight — software only.

Never starts sessions, locks, orders, or live Finviz fetch. Validates durable
state selection, campaign integrity, SIGNAL_ONLY authorization, calendar, and
operator gates for ``ftep_watch_catalysts.py --live-ingress``.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from ...finviz.config import operator_repo_search_roots
from ...git_ref import main_working_tree
from ...local_state.paths import database_path, persistence_enabled, state_dir
from ...providers.adapters.finviz_elite_context import configured_token, finviz_live_enabled
from ...providers.equity_quote_selection import opend_readiness
from .campaign_status import collect_ftep_campaign_status
from .ftep_catalyst_watch import load_governed_session_ids_from_evidence
from .ftep_integrity import FTEP_V1_002_EXPECTED_FINGERPRINT, collect_ftep_integrity_checks
from .ftep_prospective_catalyst_ingress import (
    _INGRESS_ENV,
    prospective_catalyst_ingress_enabled,
)
from .session_policy import CALENDAR_US_EQUITY_RTH

_ARTIFACT_KIND = "ftep_finviz_prospective_preflight"
_SCHEMA_VERSION = "1.0.0"
_EXPECTED_GOVERNED_SESSIONS = 2

_PREFLIGHT_DISPOSITIONS = frozenset({"READY", "SOFTWARE_READY_RTH_REQUIRED", "BLOCKED"})


@dataclass(frozen=True, slots=True)
class FtepFinvizProspectivePreflightOptions:
    campaign_slug: str = "FTEP-V1-002"
    now_ns: int | None = None


def _now_ns(explicit: int | None) -> int:
    if explicit is not None:
        return explicit
    return time.time_ns()


def operator_primary_imp_root(repository_root: Path) -> Path:
    """Canonical IMP tree on the git primary checkout (monorepo layout)."""

    main = main_working_tree(start=repository_root)
    if main is None:
        return repository_root
    candidate = main / "projects" / "integrated-market-platform"
    try:
        if (candidate / "phase0-dependency-lock.json").is_file():
            return candidate
    except OSError:
        pass
    return repository_root


def canonical_primary_state_database(repository_root: Path) -> Path | None:
    """Best-effort canonical durable SQLite on the operator monorepo primary checkout."""

    main = main_working_tree(start=repository_root)
    if main is None:
        return None
    candidates = (
        main / "projects" / "integrated-market-platform" / ".local" / "imp-state.sqlite3",
        main / "integrated-market-platform" / ".local" / "imp-state.sqlite3",
    )
    for candidate in candidates:
        try:
            if candidate.is_file():
                return candidate.resolve()
        except OSError:
            continue
    return candidates[0].resolve()


def _private_credential_paths(repository_root: Path) -> dict[str, Any]:
    login_paths: list[str] = []
    token_paths: list[str] = []
    roots: list[Path] = [repository_root, operator_primary_imp_root(repository_root)]
    for root in operator_repo_search_roots(start=repository_root):
        roots.append(root)
    seen: set[str] = set()
    for root in roots:
        login = root / ".private" / "finviz-login.json"
        token = root / ".private" / "finviz-token.txt"
        try:
            if login.is_file():
                key = str(login.resolve())
                if key not in seen:
                    seen.add(key)
                    login_paths.append(key)
        except OSError:
            pass
        try:
            if token.is_file():
                key = str(token.resolve())
                if key not in seen:
                    seen.add(key)
                    token_paths.append(key)
        except OSError:
            pass
    return {
        "finviz_login_json_paths": login_paths,
        "finviz_token_txt_paths": token_paths,
        "finviz_login_present": bool(login_paths),
        "finviz_token_file_present": bool(token_paths),
    }


def _finviz_capability_report(repository_root: Path) -> dict[str, Any]:
    report_path = repository_root / "evidence" / "market_data" / "finviz" / "capability-report.json"
    body: dict[str, Any] = {"path": str(report_path), "present": report_path.is_file()}
    if not report_path.is_file():
        body["status"] = "ABSENT"
        return body
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        body["status"] = "UNREADABLE"
        body["error"] = type(exc).__name__
        return body
    body["status"] = "PRESENT"
    body["generated_at"] = payload.get("generated_at") or payload.get("observed_at")
    news = None
    for row in payload.get("capabilities") or []:
        if isinstance(row, dict) and row.get("name") == "News":
            news = {
                "verified": row.get("verified"),
                "account_accessible": row.get("account_accessible"),
            }
            break
    body["news_capability"] = news
    return body


def _aggregate_disposition(
    *,
    rth_open: bool,
    hard_blockers: tuple[str, ...],
) -> str:
    if hard_blockers:
        return "BLOCKED"
    if not rth_open:
        return "SOFTWARE_READY_RTH_REQUIRED"
    return "READY"


def run_ftep_finviz_prospective_preflight(
    repository_root: Path,
    *,
    options: FtepFinvizProspectivePreflightOptions | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    opts = options or FtepFinvizProspectivePreflightOptions()
    mapping = env if env is not None else os.environ
    now = _now_ns(opts.now_ns)
    imp_root = operator_primary_imp_root(repository_root)

    status = collect_ftep_campaign_status(imp_root, opts.campaign_slug)
    rth_open = bool(status.get("us_equity_rth_open"))
    governed_count = int(status.get("governed_session_count") or 0)
    empirical_locks = int(status.get("empirical_lock_count") or 0)

    hard_blockers: list[str] = []
    soft_codes: list[str] = []
    operator_hints: list[str] = []

    selected_db = database_path()
    canonical_db = canonical_primary_state_database(repository_root)
    persist_on = persistence_enabled()
    state_path = state_dir()
    canonical_selected = False
    if not persist_on:
        hard_blockers.append("CANONICAL_STATE_NOT_SELECTED")
        operator_hints.append(
            "Set IMP_STATE_DIR to the primary IMP .local directory (canonical imp-state.sqlite3) "
            "or run from the primary checkout with IMP_PERSIST_STATE=1."
        )
    elif canonical_db is not None:
        try:
            canonical_selected = selected_db.resolve() == canonical_db.resolve()
        except OSError:
            canonical_selected = False
        if not canonical_selected:
            hard_blockers.append("CANONICAL_STATE_NOT_SELECTED")
            operator_hints.append(
                f"Selected state DB {selected_db} does not match canonical primary "
                f"{canonical_db}. Export IMP_STATE_DIR=<primary .local> before preflight."
            )

    if opts.campaign_slug == "FTEP-V1-002":
        fingerprint = status.get("manifest_fingerprint")
        if fingerprint != FTEP_V1_002_EXPECTED_FINGERPRINT:
            hard_blockers.append("MANIFEST_FINGERPRINT_MISMATCH")

    integrity = collect_ftep_integrity_checks(imp_root, opts.campaign_slug)
    if integrity.get("disposition") != "PASS":
        hard_blockers.append("FTEP_INTEGRITY_FAILED")

    if not status.get("signal_only_authorized"):
        hard_blockers.append("SIGNAL_ONLY_NOT_AUTHORIZED")

    if governed_count != _EXPECTED_GOVERNED_SESSIONS:
        hard_blockers.append("SESSION_COUNT_INVALID")

    if empirical_locks != 0:
        hard_blockers.append("EMPIRICAL_LOCK_PRESENT")

    evidence_ids, evidence_path = load_governed_session_ids_from_evidence(
        imp_root,
        opts.campaign_slug,
    )
    if governed_count > 0 and not evidence_ids:
        hard_blockers.append("GOVERNED_SESSION_EVIDENCE_MISSING")
        operator_hints.append(
            "Durable sessions exist but governed-session-start-evidence.jsonl lacks session_id rows "
            "(untracked evidence is not absent — confirm artifact path on primary checkout)."
        )

    cred_paths = _private_credential_paths(imp_root)
    token_configured = bool(configured_token(mapping)) or (
        cred_paths["finviz_login_present"] or cred_paths["finviz_token_file_present"]
    )
    if not token_configured and not cred_paths["finviz_login_present"]:
        hard_blockers.append("FINVIZ_CREDENTIAL_MISSING")

    if not finviz_live_enabled(mapping):
        soft_codes.append("FINVIZ_LIVE_DISABLED")
        operator_hints.append(
            "Tomorrow bounded observational run requires owner-temporary IMP_FINVIZ_LIVE=1 "
            "(do not commit or permanently enable in config)."
        )

    if not prospective_catalyst_ingress_enabled(mapping):
        soft_codes.append("PROSPECTIVE_INGRESS_DISABLED")
        operator_hints.append(
            f"Set {_INGRESS_ENV}=1 with IMP_FINVIZ_LIVE=1 for --live-ingress during RTH."
        )

    if not rth_open:
        soft_codes.append("RTH_CLOSED")

    readiness_disp = status.get("campaign_readiness_disposition")
    if readiness_disp != "READY":
        hard_blockers.append("CAMPAIGN_READINESS_NOT_READY")

    disposition = _aggregate_disposition(rth_open=rth_open, hard_blockers=tuple(hard_blockers))

    # RTH-time live watch requires observational gates; off-hours they are expected soft.
    rth_blockers: list[str] = []
    if disposition == "READY":
        if "FINVIZ_LIVE_DISABLED" in soft_codes:
            rth_blockers.append("FINVIZ_LIVE_DISABLED")
        if "PROSPECTIVE_INGRESS_DISABLED" in soft_codes:
            rth_blockers.append("PROSPECTIVE_INGRESS_DISABLED")

    opend = opend_readiness()
    capability_report = _finviz_capability_report(imp_root)

    reason_codes = list(dict.fromkeys([*hard_blockers, *soft_codes]))

    return {
        "artifact_kind": _ARTIFACT_KIND,
        "schema_version": _SCHEMA_VERSION,
        "campaign_slug": opts.campaign_slug,
        "test_mode": "SIGNAL_ONLY",
        "ftep_empirical_active": False,
        "observed_at_ns": now,
        "calendar_scope": CALENDAR_US_EQUITY_RTH,
        "us_equity_rth_open": rth_open,
        "disposition": disposition,
        "blockers": hard_blockers,
        "rth_live_ingress_blockers": rth_blockers,
        "reason_codes": reason_codes,
        "operator_hints": operator_hints,
        "expected_governed_session_count": _EXPECTED_GOVERNED_SESSIONS,
        "live_watch_command": (
            f"python tools/ftep_watch_catalysts.py {opts.campaign_slug} --live-ingress --json"
        ),
        "live_ingress_outcomes": {
            "success_with_rows": "watch_mode=PROSPECTIVE_FINVIZ_INGRESS; attention_data_kind=LIVE_PROSPECTIVE",
            "success_zero_qualifying_rows": "LIVE_INGRESS_SUCCESS_ZERO_QUALIFYING_ROWS",
            "failed": "LIVE_INGRESS_FAILED (fetch/pipeline/gates; disposition BLOCKED)",
        },
        "operator_primary_imp_root": str(imp_root),
        "state_selection": {
            "persistence_enabled": persist_on,
            "state_dir": str(state_path),
            "selected_database": str(selected_db),
            "canonical_primary_database": str(canonical_db) if canonical_db else None,
            "canonical_selected": canonical_selected,
            "empirical_counts_source": status.get("empirical_counts_source"),
        },
        "campaign_status": {
            "manifest_status": status.get("manifest_status"),
            "manifest_fingerprint": status.get("manifest_fingerprint"),
            "governed_session_count": governed_count,
            "empirical_lock_count": empirical_locks,
            "signal_only_authorized": status.get("signal_only_authorized"),
            "campaign_readiness_disposition": readiness_disp,
        },
        "integrity_disposition": integrity.get("disposition"),
        "governed_session_ids_from_evidence": evidence_ids,
        "governed_session_evidence_path": evidence_path,
        "finviz": {
            "token_configured": token_configured,
            "finviz_live_enabled": finviz_live_enabled(mapping),
            "prospective_ingress_enabled": prospective_catalyst_ingress_enabled(mapping),
            "prospective_ingress_env": _INGRESS_ENV,
            **cred_paths,
            "capability_report": capability_report,
        },
        "opend_readiness": {
            "host": opend.host,
            "port": opend.port,
            "reachable": opend.reachable,
            "note": "Informational for FTEP-V1-002 stack; prospective catalyst ingress is Finviz-only.",
        },
        "secrets_included": False,
    }


def build_ftep_finviz_prospective_preflight_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Software-only preflight for FTEP-V1-002 Finviz prospective catalyst watch. "
            "Never fetches live Finviz data or mutates durable state."
        ),
    )
    parser.add_argument(
        "campaign_slug",
        nargs="?",
        default="FTEP-V1-002",
        help="Forward-test campaign slug (default: FTEP-V1-002)",
    )
    parser.add_argument("--json", action="store_true", help="Machine-readable JSON report")
    parser.add_argument("--now-ns", type=int, default=None, help="Test-only wall clock override.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    from ...local_state.paths import REPO_ROOT

    args = build_ftep_finviz_prospective_preflight_parser().parse_args(argv)
    report = run_ftep_finviz_prospective_preflight(
        REPO_ROOT,
        options=FtepFinvizProspectivePreflightOptions(
            campaign_slug=args.campaign_slug,
            now_ns=args.now_ns,
        ),
    )
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"disposition={report['disposition']} blockers={report['blockers']}")
        print(f"reason_codes={report['reason_codes']}")
    disposition = report["disposition"]
    if disposition in {"READY", "SOFTWARE_READY_RTH_REQUIRED"}:
        return 0
    return 1


__all__ = [
    "FtepFinvizProspectivePreflightOptions",
    "build_ftep_finviz_prospective_preflight_parser",
    "canonical_primary_state_database",
    "operator_primary_imp_root",
    "main",
    "run_ftep_finviz_prospective_preflight",
]
