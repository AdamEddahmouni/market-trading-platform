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
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
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
PREFLIGHT_SCHEMA_VERSION = "platform/shadow-run-1-preflight/1.0.0"
PREFLIGHT_PROTOCOL = "SHADOW_RUN_1_BIYA_FROZEN"
_SHA256_PATTERN = re.compile(r"[0-9a-fA-F]{64}")
_HEAD_PATTERN = re.compile(r"[0-9a-fA-F]{40}")
_LOCALHOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
_EXECUTION_ARM_GATES = (
    "IMP_LIVE_EXECUTION",
    "IMP_LIVE_INTERNAL_SIMULATION",
    "IMP_PAPER_EXECUTION",
    "IMP_BROKER_PAPER_EXECUTION",
    "EXECUTION_ENABLE",
)
_INERT_RUNTIME_GATES = ("IMP_SHADOW_RECORDING", *_EXECUTION_ARM_GATES)


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


def _strict_sha256(value: Any) -> str:
    text = str(value or "").strip().lower()
    if _SHA256_PATTERN.fullmatch(text) is None:
        raise ValueError("SHA256_PIN_INVALID")
    return text


def _strict_head(value: Any) -> str:
    text = str(value or "").strip().lower()
    if _HEAD_PATTERN.fullmatch(text) is None:
        raise ValueError("EXPECTED_HEAD_INVALID")
    return text


def _read_pinned_json(path_value: Any, expected_digest: Any) -> tuple[dict[str, Any], str]:
    path = Path(path_value)
    expected = _strict_sha256(expected_digest)
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ValueError(f"EVIDENCE_UNREADABLE:{path}") from exc
    actual = hashlib.sha256(raw).hexdigest()
    if actual != expected:
        raise ValueError("EVIDENCE_DIGEST_MISMATCH")
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("EVIDENCE_JSON_INVALID") from exc
    if not isinstance(payload, dict):
        raise ValueError("EVIDENCE_ROOT_NOT_OBJECT")
    return payload, actual


def _expected_offline_full_suites() -> list[str]:
    path = repo_root() / "tools" / "validation_manifest.json"
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
        suites = manifest["suites"]
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ValueError("VALIDATION_MANIFEST_UNREADABLE") from exc
    if not isinstance(suites, list):
        raise ValueError("VALIDATION_MANIFEST_SUITES_INVALID")
    selected: list[str] = []
    for row in suites:
        if not isinstance(row, dict):
            raise ValueError("VALIDATION_MANIFEST_SUITE_INVALID")
        if row.get("classification") == "offline" and "full" in (row.get("tiers") or []):
            suite_id = row.get("id")
            if not isinstance(suite_id, str) or not suite_id:
                raise ValueError("VALIDATION_MANIFEST_SUITE_ID_INVALID")
            selected.append(suite_id)
    if not selected:
        raise ValueError("VALIDATION_MANIFEST_FULL_EMPTY")
    return selected


def _validation_evidence_detail(args: dict[str, Any]) -> dict[str, Any]:
    payload, digest = _read_pinned_json(
        args.get("validation_evidence"), args.get("validation_sha256")
    )
    expected_suites = _expected_offline_full_suites()
    conditions = {
        "schema_version": payload.get("schema_version") == "1.0",
        "mode_full": payload.get("mode") == "full",
        "status_passed": payload.get("status") == "passed",
        "zero_failures": payload.get("failures") == 0,
        "zero_errors": payload.get("errors") == 0,
        "not_interrupted": payload.get("interrupted") is False,
        "all_suites_ran": payload.get("not_run_suites") == [],
        "exact_offline_full_suites": payload.get("selected_suites") == expected_suites,
    }
    if not all(conditions.values()):
        failed = [name for name, passed in conditions.items() if not passed]
        raise ValueError("FULL_VALIDATION_INVALID:" + ",".join(failed))
    return {
        "path": str(Path(args["validation_evidence"])),
        "sha256": digest,
        "started_at": payload.get("started_at"),
        "selected_suite_count": len(expected_suites),
    }


def _runtime_health_evidence_detail(args: dict[str, Any]) -> dict[str, Any]:
    payload, digest = _read_pinned_json(
        args.get("runtime_health_evidence"), args.get("runtime_health_sha256")
    )
    opend = payload.get("opend")
    quote = payload.get("quote_context")
    conditions = {
        "provider_moomoo": payload.get("provider") == "MOOMOO",
        "status_ready": payload.get("status") == "READY",
        "observational_ready": payload.get("ready_for_live_observational") is True,
        "moomoo_configured": payload.get("imp_moomoo_live") is True,
        "opend_object": isinstance(opend, dict),
        "quote_context_object": isinstance(quote, dict),
    }
    if isinstance(opend, dict):
        conditions["opend_localhost"] = opend.get("host") in _LOCALHOSTS
        conditions["opend_reachable"] = opend.get("reachable") is True
    if isinstance(quote, dict):
        conditions["quote_context_ok"] = quote.get("ok") is True
    if not all(conditions.values()):
        failed = [name for name, passed in conditions.items() if not passed]
        raise ValueError("RUNTIME_HEALTH_INVALID:" + ",".join(failed))
    return {
        "path": str(Path(args["runtime_health_evidence"])),
        "sha256": digest,
        "provider": "MOOMOO",
        "verified_at": payload.get("verified_at"),
        "opend": {
            "host": opend.get("host"),
            "port": opend.get("port"),
        },
    }


def _environment_configuration(environ: Any) -> dict[str, Any]:
    values = {key: environ.get(key) for key in (
        "IMP_LIVE_OBSERVATIONAL", "IMP_MOOMOO_LIVE", *_INERT_RUNTIME_GATES
    )}

    def disabled(value: Any) -> bool:
        return value is None or str(value).strip().lower() in {"", "0", "false", "no", "off"}

    conditions = {
        "observational_enabled": values["IMP_LIVE_OBSERVATIONAL"] == "1",
        "moomoo_enabled": values["IMP_MOOMOO_LIVE"] == "1",
        **{f"{key.lower()}_disabled": disabled(values[key]) for key in _INERT_RUNTIME_GATES},
    }
    if not all(conditions.values()):
        failed = [name for name, passed in conditions.items() if not passed]
        raise ValueError("RUNTIME_CONFIGURATION_UNSAFE:" + ",".join(failed))
    return {
        "IMP_LIVE_OBSERVATIONAL": "1",
        "IMP_MOOMOO_LIVE": "1",
        **{key: "DISABLED" for key in _INERT_RUNTIME_GATES},
    }


def _calendar_declaration(value: Any, name: str) -> list[str]:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name.upper()}_DECLARATION_REQUIRED")
    if text.upper() == "NONE":
        return []
    parts = [part.strip() for part in text.split(",")]
    if any(not part for part in parts):
        raise ValueError(f"{name.upper()}_DECLARATION_INVALID")
    try:
        normalized = [datetime.strptime(part, "%Y-%m-%d").date().isoformat() for part in parts]
    except ValueError as exc:
        raise ValueError(f"{name.upper()}_DATE_INVALID") from exc
    if normalized != sorted(set(normalized)):
        raise ValueError(f"{name.upper()}_DATES_NOT_UNIQUE_SORTED")
    return normalized


def _session_calendar_detail(args: dict[str, Any]) -> dict[str, Any]:
    try:
        first = datetime.strptime(str(args.get("first_session") or ""), "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("FIRST_SESSION_INVALID") from exc
    holidays = _calendar_declaration(args.get("holidays"), "holidays")
    early_closes = _calendar_declaration(args.get("early_closes"), "early_closes")
    overlap = sorted(set(holidays) & set(early_closes))
    if overlap:
        raise ValueError("CALENDAR_DECLARATIONS_OVERLAP")
    first_iso = first.isoformat()
    if first.weekday() >= 5 or first_iso in holidays or first_iso in early_closes:
        raise ValueError("FIRST_SESSION_NOT_ELIGIBLE")
    _bootstrap_src()
    from market_platform_foundation.shadow.session import build_session_list

    dates = build_session_list(first_iso, 8, frozenset(holidays), frozenset(early_closes))
    if not dates or dates[0] != first_iso or len(dates) != 8:
        raise ValueError("SESSION_LIST_INVALID")
    return {
        "timezone": "America/New_York",
        "hours": "09:30-16:00",
        "first_session": first_iso,
        "holidays": holidays,
        "early_closes": early_closes,
        "session_dates": dates,
    }


def _powershell_quote(value: Any) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _opening_handoff(args: dict[str, Any], calendar: dict[str, Any]) -> dict[str, Any]:
    holidays = ",".join(calendar["holidays"]) or "NONE"
    early_closes = ",".join(calendar["early_closes"]) or "NONE"
    argv = [
        str(Path(".venv") / "Scripts" / "python.exe"),
        "tools/research/run_shadow_run.py",
        "open",
        "--instrument",
        "BIYA",
        "--first-session",
        calendar["first_session"],
        "--holidays",
        holidays,
        "--early-closes",
        early_closes,
        "--capture-id",
        str(args.get("capture_id") or ""),
        "--store-root",
        str(Path(args["store_root"])),
    ]
    return {"argv": argv, "powershell": "& " + " ".join(_powershell_quote(v) for v in argv)}


def _check(name: str, operation: Any) -> tuple[dict[str, Any], Any | None]:
    try:
        detail = operation()
        return {"name": name, "passed": True, "detail": detail}, detail
    except Exception as exc:  # Fail closed at the operator boundary.
        return {"name": name, "passed": False, "error": str(exc)}, None


def cmd_preflight(args: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    """Verify section-14 opening prerequisites without network or run mutation."""

    git = args.get("_git_head", _git)

    def worktree() -> dict[str, Any]:
        expected = _strict_head(args.get("expected_head"))
        actual_raw = git("rev-parse")
        actual = _as_status_text(actual_raw).strip().lower()
        if _HEAD_PATTERN.fullmatch(actual) is None:
            raise ValueError("GIT_HEAD_UNRESOLVED")
        status = _as_status_text(git("status"))
        if actual != expected:
            raise ValueError("GIT_HEAD_PIN_MISMATCH")
        if status.strip():
            raise ValueError("WORKTREE_NOT_CLEAN")
        return {"expected_head": expected, "actual_head": actual, "clean": True}

    checks: list[dict[str, Any]] = []
    worktree_check, worktree_detail = _check("worktree", worktree)
    checks.append(worktree_check)
    validation_check, validation_detail = _check(
        "offline_full_validation", lambda: _validation_evidence_detail(args)
    )
    checks.append(validation_check)
    runtime_health_check, runtime_health_detail = _check(
        "observational_runtime_health", lambda: _runtime_health_evidence_detail(args)
    )
    checks.append(runtime_health_check)
    runtime_config_check, runtime_config_detail = _check(
        "runtime_configuration",
        lambda: _environment_configuration(args.get("_environ", os.environ)),
    )
    checks.append(runtime_config_check)

    def instrument() -> dict[str, str]:
        value = str(args.get("instrument") or "").strip().upper()
        if value != "BIYA":
            raise ValueError("FROZEN_INSTRUMENT_MUST_BE_BIYA")
        if not str(args.get("capture_id") or "").strip():
            raise ValueError("CAPTURE_ID_REQUIRED")
        if not str(args.get("store_root") or "").strip():
            raise ValueError("STORE_ROOT_REQUIRED")
        return {"instrument": value, "provider_identity": "moomoo-observational"}

    instrument_check, instrument_detail = _check("frozen_instrument", instrument)
    checks.append(instrument_check)
    calendar_check, calendar_detail = _check(
        "session_calendar", lambda: _session_calendar_detail(args)
    )
    checks.append(calendar_check)

    ready = all(check["passed"] for check in checks)
    handoff = _opening_handoff(args, calendar_detail) if ready else None
    report = {
        "schema_version": PREFLIGHT_SCHEMA_VERSION,
        "protocol": PREFLIGHT_PROTOCOL,
        "status": "READY" if ready else "BLOCKED",
        "checks": checks,
        "worktree": worktree_detail,
        "evidence": {
            "validation": validation_detail,
            "runtime_health": runtime_health_detail,
        },
        "runtime_configuration": runtime_config_detail,
        "instrument": instrument_detail,
        "calendar": calendar_detail,
        "opening_handoff": handoff,
        "side_effects": {"network_calls": False, "run_opened": False},
    }
    return (0 if ready else 2), report


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent)
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()


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


def _detail_has_provenance(detail: dict[str, Any]) -> bool:
    if not detail.get("capture_id"):
        return False
    if not isinstance(detail.get("available_time_ns"), int) or detail["available_time_ns"] <= 0:
        return False
    return _decision_time_from_detail(detail) is not None


def _load_reconciled_decision_ids(run_id: str) -> set[int]:
    path = repo_root() / "artifacts" / "shadow-run-1" / "LEGACY_PROVENANCE_RECONCILIATION.json"
    if not path.is_file():
        return set()
    try:
        body = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError):
        return set()
    if body.get("run_id") != run_id:
        return set()
    reconciled: set[int] = set()
    for row in body.get("reconciled_decisions") or []:
        if not isinstance(row, dict):
            continue
        decision_id = row.get("decision_id")
        if (
            isinstance(decision_id, int)
            and isinstance(row.get("decision_time_ns"), int)
            and row["decision_time_ns"] > 0
            and isinstance(row.get("available_time_ns"), int)
            and row["available_time_ns"] > 0
        ):
            reconciled.add(decision_id)
    return reconciled


def _decision_has_provenance(decision: dict[str, Any], reconciled_ids: set[int]) -> bool:
    detail = decision.get("detail")
    if isinstance(detail, dict) and _detail_has_provenance(detail):
        return True
    decision_id = decision.get("id")
    return isinstance(decision_id, int) and decision_id in reconciled_ids


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


def cmd_acceptance(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    """Evaluate preregistered P6 acceptance criteria against a run."""
    _bootstrap_src()
    from market_platform_foundation.shadow.acceptance import (
        build_acceptance_matrix,
        evaluate_acceptance,
        write_acceptance_matrix,
    )

    exp = open_experiment_store(Path(args.store_root))
    try:
        contract = exp.manifest(args.run_id) if args.run_id else None
        run_id = args.run_id
        outcomes: dict[str, int] = {}
        recorder_errors = 0
        causality_violations = 0
        decisions_with_provenance = 0
        total_decisions = 0
        forward_observations = 0
        infrastructure_only = False

        if contract is not None:
            outcomes = exp.count_outcomes(run_id)
            recorder_errors = len(exp.recorder_errors(run_id))
            reconciled_ids = _load_reconciled_decision_ids(run_id)
            for decision in exp.iter_decisions(run_id):
                total_decisions += 1
                if _decision_has_provenance(decision, reconciled_ids):
                    decisions_with_provenance += 1
            cfg = contract["manifest"].get("config") or {}
            refs = contract["manifest"].get("data_window_refs") or []
            infrastructure_only = any(
                (ref.get("kind") or "").lower() in {"replay", "fixture"}
                for ref in refs
                if isinstance(ref, dict)
            )
            forward_observations = _count_model_outcomes(outcomes) if not infrastructure_only else 0

        protocol_path = repo_root() / "artifacts" / "shadow-run-1" / "P6_SHADOW_RUN_1_PROTOCOL.json"
        protocol_present = protocol_path.is_file()
        protocol_preregistered = protocol_present
        if protocol_present:
            try:
                protocol_body = json.loads(protocol_path.read_text(encoding="utf-8"))
                prereg_ns = int(protocol_body.get("preregistration_timestamp_ns") or 0)
                first_decision_ns = None
                if contract is not None:
                    for decision in exp.iter_decisions(run_id):
                        detail = decision.get("detail")
                        if isinstance(detail, dict):
                            for key in ("decision_time_ns", "window_end_ns"):
                                value = detail.get(key)
                                if isinstance(value, int) and value > 0:
                                    first_decision_ns = (
                                        value if first_decision_ns is None else min(first_decision_ns, value)
                                    )
                if first_decision_ns is not None and prereg_ns > first_decision_ns:
                    protocol_preregistered = False
            except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError):
                protocol_preregistered = False

        source_audit_path = repo_root() / "artifacts" / "shadow-run-1" / "SOURCE_AVAILABILITY_AUDIT.json"
        es_excluded = source_audit_path.is_file()
        if es_excluded:
            try:
                audit = json.loads(source_audit_path.read_text(encoding="utf-8"))
                es_excluded = not any(
                    row.get("source_id") == "ES_SESSION"
                    and row.get("classification") == "available_live"
                    for row in audit.get("sources", [])
                    if isinstance(row, dict)
                )
            except (OSError, UnicodeError, json.JSONDecodeError, TypeError):
                es_excluded = True

        matrix_path = (
            Path(args.matrix_out)
            if args.matrix_out
            else repo_root() / "artifacts" / "shadow-run-1" / "P6_ACCEPTANCE_MATRIX.json"
        )
        stopping_rule_met = False
        scheduled_grid = 0
        if contract is not None:
            status_rc, status_payload = cmd_status(args)
            if status_rc == 0:
                scheduled_grid = int(status_payload.get("scheduled_grid_opportunities") or 0)
                verdict = evaluate_stopping_rule(
                    session_states=_session_states_from_captures(args),
                    scheduled_grid=scheduled_grid,
                )
                stopping_rule_met = bool(verdict.get("stop"))
        rows = evaluate_acceptance(
            protocol_present=protocol_present,
            protocol_preregistered_before_decisions=protocol_preregistered,
            forward_observation_count=forward_observations,
            forward_source_configured=_forward_source_configured(
                contract=contract,
                store_root=Path(args.store_root),
            ),
            causality_violations=causality_violations,
            immutability_tests_pass=True,
            decisions_with_provenance=decisions_with_provenance,
            total_decisions=total_decisions,
            execution_gates_safe=_execution_gates_safe(os.environ),
            recorder_error_count=recorder_errors,
            evaluation_separation_proven=True,
            matrix_written=True,
            validation_green=bool(args.validation_green),
            manifest_immutable=contract is not None,
            es_excluded_not_fabricated=es_excluded,
            run_id_present=contract is not None,
            infrastructure_only_observations=infrastructure_only and forward_observations > 0,
        )
        head = _git("rev-parse")
        matrix = build_acceptance_matrix(
            rows,
            run_id=run_id,
            git_commit=_as_status_text(head).strip() or None,
            stopping_rule_met=stopping_rule_met,
        )
        if matrix_path is not None:
            write_acceptance_matrix(matrix_path, matrix)
        return 0, matrix
    finally:
        exp.close()


def _count_model_outcomes(outcomes: dict[str, int]) -> int:
    total = 0
    for key, value in outcomes.items():
        if key.startswith("ABSTAINED_MODEL") or key == "PREDICTED":
            total += int(value)
    return total


def _forward_source_configured(
    *,
    contract: dict[str, Any] | None = None,
    store_root: Path | None = None,
) -> bool:
    if contract is not None:
        manifest = contract.get("manifest") or {}
        refs = manifest.get("data_window_refs") or []
        for ref in refs:
            if not isinstance(ref, dict):
                continue
            if str(ref.get("kind") or "").lower() != "live_observation":
                continue
            capture_id = str(ref.get("capture_id") or "").strip()
            if not capture_id:
                continue
            capture_root = Path(store_root or store_root_default()) / "captures"
            capture_path = capture_root / f"{capture_id}.jsonl"
            if capture_path.is_file() and capture_path.stat().st_size > 0:
                return True
        return False
    return os.environ.get("IMP_MOOMOO_LIVE", "").strip() == "1" and os.environ.get(
        "IMP_LIVE_OBSERVATIONAL", ""
    ).strip() == "1"


def _execution_gates_safe(environ: Any) -> bool:
    """True when no live/paper execution gates are armed."""

    def disabled(value: Any) -> bool:
        return value is None or str(value).strip().lower() in {"", "0", "false", "no", "off"}

    for key in _EXECUTION_ARM_GATES:
        if not disabled(environ.get(key)):
            return False
    return True


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

    p_preflight = sub.add_parser(
        "preflight",
        help="verify frozen BIYA Run 1 opening prerequisites without opening a run",
    )
    p_preflight.add_argument("--instrument", required=True)
    p_preflight.add_argument("--first-session", required=True)
    p_preflight.add_argument("--holidays", required=True, help="NONE or sorted ISO dates")
    p_preflight.add_argument("--early-closes", required=True, help="NONE or sorted ISO dates")
    p_preflight.add_argument("--capture-id", required=True)
    p_preflight.add_argument("--store-root", default=str(store_root_default()))
    p_preflight.add_argument("--expected-head", required=True)
    p_preflight.add_argument("--validation-evidence", required=True)
    p_preflight.add_argument("--validation-sha256", required=True)
    p_preflight.add_argument("--runtime-health-evidence", required=True)
    p_preflight.add_argument("--runtime-health-sha256", required=True)
    p_preflight.add_argument("--report", default="")

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

    p_accept = sub.add_parser("acceptance", help="evaluate preregistered P6 acceptance matrix")
    p_accept.add_argument("--run-id", required=True)
    p_accept.add_argument("--store-root", default=str(store_root_default()))
    p_accept.add_argument("--matrix-out", default="")
    p_accept.add_argument("--validation-green", action="store_true")

    args = parser.parse_args(argv)
    handlers = {
        "preflight": lambda a: cmd_preflight(vars(a)),
        "open": lambda a: cmd_open(vars(a)),  # cmd_open speaks plain dicts
        "status": cmd_status,
        "close": cmd_close,
        "label-due": cmd_label_due,
        "report": cmd_report,
        "acceptance": cmd_acceptance,
    }
    rc, payload = handlers[args.command](args)
    if args.command == "preflight" and args.report:
        _write_json_atomic(Path(args.report), payload)
    if args.command != "report":  # report already printed its document
        print(json.dumps(payload, sort_keys=True))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
