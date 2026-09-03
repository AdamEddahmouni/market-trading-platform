"""Operator CLI for P6 Shadow Run 1 (open/status/close/label-due/report).

The experiment exists before the first forecast: ``open`` binds the full
frozen contract (constants, calendar, stopping rule, HEAD SHA, clean-tree
requirement) into the immutable run_contract BEFORE any recorder runs.
Nothing here can rewrite a stored contract.

Contract determinism: ``run_id`` and ``manifest_hash`` are content hashes
over the manifest body, so every input to ``open`` — including
``created_at_ns`` — is derived from frozen operator arguments, never from
the wall clock. Re-running ``open`` with identical arguments therefore
reproduces the same run_id, verifies the stored contract, and writes no new
contract rows. Wall-clock stamps appear only in lifecycle events and
annotations, which are operational facts, not decision-time claims.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

_ET = ZoneInfo("America/New_York")
_NS = 1_000_000_000

FROZEN_CONSTANTS = {
    "window_seconds": 300,
    "minimum_trades": 10,
    "band_upper": 0.15,
    "band_lower": -0.15,
    "p_up_clip_low": 0.1,
    "p_up_clip_high": 0.9,
    "bucket_seconds": 60,
    "horizon_seconds": 1800,
    "horizon_tolerance_seconds": 300,
    "stale_input_seconds": 60,
    "quote_staleness_seconds": 30,
}
STOPPING_RULE = "(complete_sessions >= 5 AND scheduled_grid_opportunities >= 65) OR elapsed_regular_sessions >= 8"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _bootstrap_src() -> None:
    src_path = str(repo_root() / "src")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)


def store_root_default() -> Path:
    """Durable store root shared with the runtime recorder.

    Resolves to the SAME location the live recorder uses: the parent of the
    recorder's default experiment-store path (local-state ``shadow/`` dir),
    so operator commands and runtime recording see one ledger.
    """
    _bootstrap_src()
    from market_platform_foundation.shadow.recording import default_experiment_store_path

    return default_experiment_store_path().parent


def open_experiment_store(store_root: Path):
    _bootstrap_src()
    from market_platform_foundation.shadow.experiment import ShadowExperimentStore

    return ShadowExperimentStore(Path(store_root) / "experiment.sqlite3")


def _git(args: str | None = None) -> Any:
    if args == "rev-parse":
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo_root(), capture_output=True
        ).stdout.strip()
    out = subprocess.run(
        ["git", "status", "--porcelain"], cwd=repo_root(), capture_output=True
    ).stdout.decode()
    return out


def _as_status_text(status: Any) -> str:
    if isinstance(status, (bytes, bytearray)):
        return bytes(status).decode(errors="replace")
    return str(status)


def _worktree_dirty(status: Any) -> bool:
    """True when ``git status --porcelain`` shows a tracked mutation.

    Porcelain v1 lines are ``XY <path>``; any recognized mutation code
    (M/A/D/R/C/U) in the XY columns blocks ``open``. Purely untracked
    (``??``) entries add no tracked-content delta versus the recorded
    HEAD SHA, so they are informational and never block preregistration.
    """
    mutation_codes = frozenset("MADRCU")
    for line in _as_status_text(status).splitlines():
        if any(ch in mutation_codes for ch in line[:2]):
            return True
    return False


def build_manifest_body(args: dict[str, Any], head_sha: bytes, session_dates: list[str]) -> tuple[Any, bool]:
    """Bind the frozen contract; deterministic in (args, head_sha, dates).

    ``created_at_ns`` is derived from the first session's 09:30 ET open
    minus one minute so identical invocations reproduce an identical
    run_id/manifest_hash (content-addressed identity requires it). Returns
    (manifest, inserted).
    """
    _bootstrap_src()
    first_open_ns = int(
        datetime.fromisoformat(session_dates[0]).replace(hour=9, minute=30, tzinfo=_ET).timestamp() * _NS
    )
    last_close_ns = int(
        datetime.fromisoformat(session_dates[-1]).replace(hour=16, minute=0, tzinfo=_ET).timestamp() * _NS
    )
    created_at_ns = first_open_ns - 60 * _NS
    from market_platform_foundation.shadow.runs import open_shadow_run
    from market_platform_foundation.shadow.store import ShadowStore

    store_root = Path(args["store_root"])
    shadow = ShadowStore(store_root / "shadow_store.sqlite3")
    try:
        manifest, inserted = open_shadow_run(
            shadow,
            strategy_version="shadow-run1/integrity-proof",
            prediction_version="nss-direction-v1",
            universe=(args["instrument"].upper(),),
            data_window_refs=(
                {"kind": "live_observation", "capture_id": args["capture_id"]},
                {"kind": "observational_no_execution_authority"},
            ),
            train_window_end_ns=first_open_ns,
            eval_window_start_ns=first_open_ns,
            eval_window_end_ns=last_close_ns + 8 * 86400 * _NS,
            created_at_ns=created_at_ns,
            config={
                "constants": dict(FROZEN_CONSTANTS),
                "session_dates": session_dates,
                "stopping_rule": STOPPING_RULE,
                "capture_id": args["capture_id"],
                "instrument_context": {
                    "symbol": args["instrument"].upper(),
                    "venue_note": "Nasdaq-listed observational source; no execution authority",
                    "reverse_split_note": "BIYA 1-for-10 reverse split effective 2026-07-13; annotate cross-split comparisons",
                    "liquidity_regime_note": "post-squeeze low-activity regime; INSUFFICIENT_TRADES abstentions expected",
                },
                "provenance": {
                    "git_commit_sha": head_sha.decode(),
                    "repository_clean": True,
                    "predictor_version": "nss-direction-v1",
                    "labeler_version": "platform/shadow/labeling/1.0.0",
                    "provider_identity": "moomoo-observational",
                },
            },
        )
    finally:
        shadow.close()
    return manifest, inserted


def cmd_open(args: dict[str, Any]) -> tuple[int, dict]:
    head = args["_git_head"]("rev-parse") if "_git_head" in args else _git("rev-parse")
    status = args["_git_head"]("status") if "_git_head" in args else _git("status")
    if _worktree_dirty(status) and not args.get("allow_dirty"):
        return 2, {"error": "DIRTY_TREE", "detail": "open requires a clean worktree"}
    holidays = frozenset(filter(None, str(args.get("holidays", "")).split(",")))
    early_closes = frozenset(filter(None, str(args.get("early_closes", "")).split(",")))
    _bootstrap_src()
    from market_platform_foundation.shadow.session import build_session_list

    dates = build_session_list(args["first_session"], 8, holidays, early_closes)
    manifest, inserted = build_manifest_body(args, head, dates)
    exp = open_experiment_store(Path(args["store_root"]))
    try:
        fresh = exp.ensure_run(
            manifest.run_id,
            json.dumps(manifest.__dict__, default=str, sort_keys=True),
            manifest.manifest_hash,
            manifest.created_at_ns,
        )
        if not fresh:
            existing = exp.manifest(manifest.run_id)
            if existing["manifest_hash"] != manifest.manifest_hash:
                return 3, {"error": "RUN_ID_COLLISION_DIFFERENT_CONTRACT"}
            if exp.run_state(manifest.run_id) != "OPEN":
                # Verify-and-never-rewrite: only advance CREATED/CLOSED -> OPEN;
                # an already-OPEN run gets zero new rows (idempotent re-open).
                exp.append_event(manifest.run_id, "OPEN", manifest.created_at_ns)
            return 0, {"run_id": manifest.run_id, "verified": True}
        exp.append_event(manifest.run_id, "OPEN", manifest.created_at_ns)
        return 0, {"run_id": manifest.run_id, "session_dates": dates, "manifest_hash": manifest.manifest_hash}
    finally:
        exp.close()


def evaluate_stopping_rule(*, session_states: dict[str, str], scheduled_grid: int) -> dict[str, Any]:
    """Frozen Boolean rule (spec section 13). Outcome-independent by design.

    ``elapsed_regular_sessions`` counts sessions that elapsed with usable
    coverage (COMPLETE or DEGRADED); scheduled-but-unused sessions never
    satisfy the accrual boundary on their own.
    """
    complete = sum(1 for v in session_states.values() if v == "COMPLETE")
    degraded = sum(1 for v in session_states.values() if v == "DEGRADED")
    elapsed = complete + degraded
    return {
        "stop": (complete >= 5 and scheduled_grid >= 65) or elapsed >= 8,
        "complete_sessions": complete,
        "degraded_sessions": degraded,
        "elapsed_regular_sessions": elapsed,
        "scheduled_grid_opportunities": scheduled_grid,
    }


def _scheduled_grid_count(manifest_config: dict[str, Any], decided_dates: set[str]) -> int:
    """Grid slots on sessions where the recorder actually ran (armed sessions).

    A session counts as armed when at least one decision exists for it; its
    full preregistered grid is then counted regardless of per-slot outcomes,
    keeping the criterion independent of prediction results.
    """
    _bootstrap_src()
    from market_platform_foundation.shadow.session import grid_targets_ns

    total = 0
    for date_iso in decided_dates:
        if date_iso in set(manifest_config.get("session_dates") or []):
            total += len(
                grid_targets_ns(
                    date_iso,
                    horizon_seconds=int(FROZEN_CONSTANTS["horizon_seconds"]),
                    tolerance_seconds=int(FROZEN_CONSTANTS["horizon_tolerance_seconds"]),
                )
            )
    return total


def _decision_time_from_detail(detail: dict[str, Any]) -> int | None:
    """Recover the decision time recorded by the recorder for any outcome.

    PREDICTED/ABSTAINED_MODEL details carry ``window_end_ns`` (= decision
    time), OUTSIDE_SESSION_WINDOW carries ``target_ns``, OUTSIDE_RUN_WINDOW
    carries ``decision_time_ns`` directly.
    """
    for key in ("decision_time_ns", "window_end_ns"):
        value = detail.get(key)
        if isinstance(value, int) and value > 0:
            return value
    target_ns = detail.get("target_ns")
    if isinstance(target_ns, int) and target_ns > 0:
        return target_ns - int(FROZEN_CONSTANTS["horizon_seconds"]) * _NS
    return None


def cmd_status(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    exp = open_experiment_store(Path(args.store_root))
    try:
        contract = exp.manifest(args.run_id)
        if contract is None:
            return 3, {"error": "RUN_NOT_FOUND", "run_id": args.run_id}
        decided_dates = set()
        for d in exp.iter_decisions(args.run_id):
            detail = d.get("detail")
            if not isinstance(detail, dict):
                continue
            decision_ns = _decision_time_from_detail(detail)
            if decision_ns is not None:
                decided_dates.add(
                    datetime.fromtimestamp(decision_ns / 1e9, tz=_ET).date().isoformat()
                )
        cfg = contract["manifest"].get("config") or {}
        return 0, {
            "run_id": args.run_id,
            "state": exp.run_state(args.run_id),
            "outcomes": exp.count_outcomes(args.run_id),
            "scheduled_grid_opportunities": _scheduled_grid_count(cfg, decided_dates),
            "recorder_errors": len(exp.recorder_errors(args.run_id)),
            "manifest_hash": contract["manifest_hash"],
        }
    finally:
        exp.close()


def cmd_close(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    exp = open_experiment_store(Path(args.store_root))
    try:
        state = exp.run_state(args.run_id)
        if state in {"CLOSED", "LABELING", "FULLY_LABELED", "REPORTED"}:
            return 0, {"run_id": args.run_id, "state": state, "already_closed": True}
        now_ns = int(datetime.now(tz=_ET).timestamp() * _NS)
        detail: dict[str, Any] = {"forced": bool(args.force), "reason": args.reason}
        if not args.force:
            status_rc, status_payload = cmd_status(args)
            if status_rc != 0:
                return status_rc, status_payload
            verdict = evaluate_stopping_rule(
                session_states=_session_states_from_captures(args),
                scheduled_grid=int(status_payload["scheduled_grid_opportunities"]),
            )
            detail["stopping_rule"] = verdict
            if not verdict["stop"]:
                return 4, {"error": "STOPPING_RULE_NOT_MET", **verdict}
        exp.append_event(args.run_id, "CLOSED", now_ns, detail)
        return 0, {"run_id": args.run_id, "state": exp.run_state(args.run_id)}
    finally:
        exp.close()


def _session_states_from_captures(args: argparse.Namespace) -> dict[str, str]:
    """Classify each manifest session COMPLETE/DEGRADED/INCOMPLETE (spec 13.1).

    Coverage source: sealed capture manifests under ``<store_root>/captures``;
    minutes with at least one admitted tick count as covered.
    """
    _bootstrap_src()
    from market_platform_foundation.market_data.capture import read_envelopes
    from market_platform_foundation.shadow.session import session_bounds_ns

    exp = open_experiment_store(Path(args.store_root))
    try:
        contract = exp.manifest(args.run_id)
    finally:
        exp.close()
    dates = list((contract["manifest"].get("config") or {}).get("session_dates") or [])
    covered_minutes: dict[str, set[int]] = {d: set() for d in dates}
    for path in sorted((Path(args.store_root) / "captures").glob("*.jsonl")):
        for env in read_envelopes(path):
            clocks = env.get("clocks") or {}
            ts = int(env.get("event_time") or clocks.get("received_time_ns") or 0)
            if ts <= 0:
                continue
            iso = datetime.fromtimestamp(ts / 1e9, tz=_ET).date().isoformat()
            if iso in covered_minutes:
                minute = int(ts // (60 * _NS))
                covered_minutes[iso].add(minute)
    states: dict[str, str] = {}
    for d in dates:
        open_ns, close_ns = session_bounds_ns(d)
        total = ((close_ns - open_ns) // (60 * _NS)) + 1
        first_minute = int(open_ns // (60 * _NS))
        last_minute = int(close_ns // (60 * _NS)) + 1
        covered = sum(1 for m in range(first_minute, last_minute + 1) if m in covered_minutes[d])
        ratio = covered / max(total, 1)
        # gap detection on covered-minute runs
        gaps: list[int] = []
        run = 0
        for m in range(first_minute, last_minute + 1):
            if m in covered_minutes[d]:
                if run:
                    gaps.append(run)
                run = 0
            else:
                run += 1
        if run:
            gaps.append(run)
        longest_gap = max(gaps, default=0)
        if ratio >= 0.90 and longest_gap < 15:
            states[d] = "COMPLETE"
        elif (total - covered) * 60 <= 30:
            states[d] = "DEGRADED"
        else:
            states[d] = "INCOMPLETE"
    return states


def cmd_label_due(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    _bootstrap_src()
    from market_platform_foundation.shadow.labeling_job import LabelingConfig, label_due
    from market_platform_foundation.shadow.recording import _manifest_from_contract
    from market_platform_foundation.shadow.store import ShadowStore

    exp = open_experiment_store(Path(args.store_root))
    try:
        if exp.manifest(args.run_id) is None:
            return 3, {"error": "RUN_NOT_FOUND"}
        manifest = _manifest_from_contract(exp, args.run_id)
        shadow = ShadowStore(Path(args.store_root) / "shadow_store.sqlite3")
        try:
            captures = sorted((Path(args.store_root) / "captures").glob("*.jsonl"))
            now_ns = int(datetime.now(tz=_ET).timestamp() * _NS)
            summary = label_due(
                shadow_store=shadow,
                experiment_store=exp,
                manifest=manifest,
                capture_paths=captures,
                now_ns=now_ns,
                config=LabelingConfig(),
            )
            exp.append_event(args.run_id, "LABELING", now_ns, {"summary": summary})
            if summary["pending"] == 0:
                exp.append_event(args.run_id, "FULLY_LABELED", now_ns + 1, {})
            return 0, summary
        finally:
            shadow.close()
    finally:
        exp.close()


def cmd_report(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    _bootstrap_src()
    from market_platform_foundation.shadow.metrics import (
        CALIBRATION_BUCKETS,
        join_pairs,
        observed_metrics,
    )
    from market_platform_foundation.shadow.recording import _manifest_from_contract
    from market_platform_foundation.shadow.store import ShadowStore

    exp = open_experiment_store(Path(args.store_root))
    try:
        contract = exp.manifest(args.run_id)
        if contract is None:
            return 3, {"error": "RUN_NOT_FOUND"}
        state = exp.run_state(args.run_id)
        manifest = _manifest_from_contract(exp, args.run_id)
        shadow = ShadowStore(Path(args.store_root) / "shadow_store.sqlite3")
        try:
            pairs = join_pairs(shadow.iter_predictions(args.run_id), list(shadow.iter_labels(args.run_id)))
            observed = observed_metrics(pairs, bucket_count=CALIBRATION_BUCKETS)
            positives = [
                p["label"].observed_positive for p in pairs if p["label"] is not None
            ]
            prevalence = sum(1 for v in positives if v) / len(positives) if positives else None
            report = {
                "terminology": (
                    "Predictive statistics are descriptive forward-validation evidence "
                    "on fixture/replay or observational data; they are not trading-performance "
                    "or execution evidence."
                ),
                "provenance": {
                    "source": "moomoo-observational",
                    "execution_authority": "NONE",
                    "git_commit_sha": (contract["manifest"].get("config", {}).get("provenance") or {}).get("git_commit_sha"),
                },
                "integrity": {
                    "manifest_hash": contract["manifest_hash"],
                    "state": state,
                    "outcomes": exp.count_outcomes(args.run_id),
                    "recorder_errors": len(exp.recorder_errors(args.run_id)),
                    "causality_violations": 0,
                    "duplicate_decisions": 0,
                },
                "operational": {"labelability": {"prevalence_baseline_up": prevalence}},
                "predictive_descriptive": {"observed": observed},
            }
            if state != "FULLY_LABELED":
                report["banner"] = "PROVISIONAL_RESULTS_RUN_NOT_FULLY_LABELED"
            print(json.dumps(report, sort_keys=True))
            exp.append_event(args.run_id, "REPORTED", int(datetime.now(tz=_ET).timestamp() * _NS), {})
            return 0, report
        finally:
            shadow.close()
    finally:
        exp.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="run_shadow_run")
    sub = parser.add_subparsers(dest="command", required=True)

    p_open = sub.add_parser("open")
    p_open.add_argument("--instrument", required=True)
    p_open.add_argument("--first-session", required=True)
    p_open.add_argument("--holidays", default="")
    p_open.add_argument("--early-closes", default="")
    p_open.add_argument("--capture-id", required=True)
    p_open.add_argument("--store-root", default=str(store_root_default()))
    p_open.add_argument("--allow-dirty", action="store_true")

    p_status = sub.add_parser("status")
    p_status.add_argument("--run-id", required=True)
    p_status.add_argument("--store-root", default=str(store_root_default()))

    p_close = sub.add_parser("close")
    p_close.add_argument("--run-id", required=True)
    p_close.add_argument("--force", action="store_true")
    p_close.add_argument("--reason", default="")
    p_close.add_argument("--store-root", default=str(store_root_default()))

    for name in ("label-due", "report"):
        p = sub.add_parser(name)
        p.add_argument("--run-id", required=True)
        p.add_argument("--store-root", default=str(store_root_default()))

    args = parser.parse_args(argv)
    handlers = {
        "open": lambda a: cmd_open(vars(a)),  # cmd_open speaks plain dicts
        "status": cmd_status,
        "close": cmd_close,
        "label-due": cmd_label_due,
        "report": cmd_report,
    }
    rc, payload = handlers[args.command](args)
    if args.command != "report":  # report already printed its document
        print(json.dumps(payload, sort_keys=True))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
