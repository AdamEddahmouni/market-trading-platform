"""Aggregate read-only operator diagnostics into one coherent snapshot.

Lane C owns this composition layer. It does not mutate provider clients,
heartbeat probes, or collector process identity (Lane B). UI rendering is Lane E.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from ...local_state.paths import state_dir
from ...operating_modes import live_execution_env_enabled, paper_execution_env_enabled
from ...paper.calibration.bar_ohlcv_prospective_proof import resolve_runtime_git_sha
from ...paper.calibration.item9_next_rth_preflight import (
    FROZEN_COLLECTOR_AUTHORITY_SHA,
    FROZEN_COLLECTOR_WORKTREE_REL,
    run_item9_next_rth_preflight,
)
from ...ui_api import projections
from ...ui_api.live_projections import build_provider_health_payload
from ...ui_api.opportunity_projections import build_opportunities_summary_payload
from ...ui_api.operator_projections import build_operator_config_payload, build_operator_readiness_payload
from ...ui_api.store import ReplayStore

_SCHEMA_VERSION = "operator-diagnostics/1.0.0"

# Program pins (canonical prose: docs/platform/PROGRAM_STATUS.md) — not upgraded by this module.
_PIN_ITEM9_FROZEN_COLLECTOR_SHA = FROZEN_COLLECTOR_AUTHORITY_SHA
_PIN_FROZEN_COLLECTOR_WORKTREE = ".imp-actual-01-phase-d"

_FORBIDDEN_OPERATOR_ACTIONS = (
    "start_item9_prospective_poll_without_ready_to_collect_disposition",
    "restart_empirical_collector",
    "mutate_prospective_receipt_or_corpus",
    "auto_fit_item9_calibration",
    "enable_live_execution",
    "merge_pr222",
    "mutate_frozen_sep17_v3_receipts",
    "rerun_experiment_under_same_evidence_label",
)

_READ_ONLY_OPERATOR_ACTIONS = (
    "get_operator_diagnostics",
    "get_operator_readiness",
    "get_operator_lifecycle_status",
    "run_item9_next_rth_preflight_cli",
    "run_item9_corpus_status_read_only",
    "refresh_provider_credentials_configured",
)


def _imp_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _classify_session_evidence(store: ReplayStore, item9: Mapping[str, Any]) -> dict[str, Any]:
    as_of = projections.build_as_of_context(store)
    mode = str(as_of.get("mode") or store.mode or "UNKNOWN").upper()
    data_mode = str(as_of.get("data_mode") or store.data_mode or "UNKNOWN").upper()
    execution_mode = str(as_of.get("execution_mode") or store.execution_mode or "NONE").upper()

    tags: list[str] = []
    primary = "idle"

    collector = item9.get("active_collector") if isinstance(item9.get("active_collector"), dict) else {}
    if collector.get("detected"):
        primary = "empirical"
        tags.append("item9_prospective_collector_process_detected")
    elif str(item9.get("disposition")) == "READY_TO_COLLECT":
        primary = "empirical"
        tags.append("item9_collection_window_open_not_observed_running")

    if mode == "REPLAY" or data_mode in {"FIXTURE_REPLAY", "HISTORICAL_CAPTURE"}:
        if primary == "idle":
            primary = "replay"
        else:
            tags.append("replay_data_mode_also_active")
    if mode == "SIMULATION" or execution_mode == "INTERNAL_SIMULATION":
        if primary == "idle":
            primary = "simulation"
        else:
            tags.append("simulation_execution_also_active")
    if data_mode in {"DELAYED_PROSPECTIVE", "PAPER_OBSERVATIONAL"} and primary == "idle":
        primary = "research"
        tags.append("non_empirical_research_data_mode")

    if mode == "LIVE" and primary == "idle":
        tags.append("live_observational_surface")
        if not tags:
            primary = "idle"

    return {
        "primary_evidence_session_class": primary,
        "tags": sorted(set(tags)),
        "as_of_mode": mode,
        "data_mode": data_mode,
        "execution_mode": execution_mode,
        "note": (
            "Evidence classes are not upgraded here. "
            "empirical means prospective collection context only; replay/backtest remain distinct."
        ),
    }


def _provider_rollups(readiness_providers: list[Mapping[str, Any]]) -> dict[str, Any]:
    healthy = 0
    degraded = 0
    blocked = 0
    for row in readiness_providers:
        gate = str(row.get("gate_state") or "")
        transport = str(row.get("transport_state") or "")
        if gate != "ENABLED":
            blocked += 1
            continue
        if transport in {"CONNECTED", "AVAILABLE", "READY"}:
            healthy += 1
        elif transport in {"UNAVAILABLE", "BLOCKED_NON_LOOPBACK", "DEGRADED"}:
            degraded += 1
        else:
            degraded += 1
    return {
        "count": len(readiness_providers),
        "healthy": healthy,
        "degraded": degraded,
        "blocked_or_disabled": blocked,
    }


def _config_summary(config: Mapping[str, Any]) -> dict[str, Any]:
    providers = config.get("providers") if isinstance(config.get("providers"), list) else []
    rows: list[dict[str, Any]] = []
    for provider in providers:
        if not isinstance(provider, dict):
            continue
        fields = provider.get("fields") if isinstance(provider.get("fields"), list) else []
        configured = sum(1 for field in fields if isinstance(field, dict) and field.get("configured"))
        rows.append(
            {
                "provider": provider.get("provider"),
                "label": provider.get("label"),
                "fields_total": len(fields),
                "fields_configured": configured,
            }
        )
    return {"providers": rows, "schema_version": config.get("schema_version")}


def _freshness_view(
    readiness_providers: list[Mapping[str, Any]],
    provider_health: Mapping[str, Any],
    opportunity_summary: Mapping[str, Any],
) -> dict[str, Any]:
    provider_freshness = [
        {
            "provider": row.get("provider"),
            "freshness": row.get("freshness") or "NOT_OBSERVED",
            "last_updated": row.get("last_updated"),
        }
        for row in readiness_providers
        if isinstance(row, dict)
    ]
    live_available = bool(provider_health.get("available"))
    lag: dict[str, Any] = {}
    summary = provider_health.get("provider_summary")
    if isinstance(summary, dict):
        for key in (
            "event_lag_ms_p50",
            "quote_lag_ms_p50",
            "queue_depth",
            "dropped",
            "reconnects",
        ):
            if key in summary:
                lag[key] = summary.get(key)
    return {
        "provider_rows": provider_freshness,
        "live_feed_metrics": lag if live_available else "UNAVAILABLE",
        "opportunity_feed_status": opportunity_summary.get("feed_status") or "NOT_OBSERVED",
        "opportunity_unready_reason": opportunity_summary.get("unready_reason"),
    }


def _cycle_recovery_view(item9: Mapping[str, Any], lifecycle: Mapping[str, Any]) -> dict[str, Any]:
    """Expected cycle failures are not centrally journaled yet — explicit honesty."""
    services = lifecycle.get("services") if isinstance(lifecycle.get("services"), list) else []
    unhealthy = [
        str(row.get("name"))
        for row in services
        if isinstance(row, dict)
        and isinstance(row.get("health"), dict)
        and str(row["health"].get("status")) not in {"HEALTHY", "OK", "RUNNING"}
    ]
    return {
        "expected_cycle_failure": "NOT_OBSERVED",
        "recovery_observed": "NOT_OBSERVED",
        "lifecycle_degraded_services": unhealthy,
        "item9_disposition": item9.get("disposition"),
        "gap_note": (
            "No durable expected-cycle ledger is exposed yet. "
            "Use lifecycle service health + item9 disposition until Lane B adds cycle receipts."
        ),
    }


def _evidence_gaps(opportunity_summary: Mapping[str, Any], item9: Mapping[str, Any]) -> list[dict[str, str]]:
    gaps: list[dict[str, str]] = []
    feed = str(opportunity_summary.get("feed_status") or "UNKNOWN")
    if feed == "UNREADY":
        gaps.append(
            {
                "domain": "opportunity_feed",
                "token": "UNAVAILABLE" if opportunity_summary.get("unready_reason") == "LIVE_AS_OF_UNAVAILABLE" else "UNREADY",
                "detail": str(opportunity_summary.get("unready_reason") or "feed_unready"),
            }
        )
    elif feed == "EMPTY":
        gaps.append({"domain": "opportunity_feed", "token": "NOT_EXPECTED", "detail": "empty_ranked_set"})
    path_gate = item9.get("output_path_gate")
    if isinstance(path_gate, dict) and not path_gate.get("ok"):
        gaps.append(
            {
                "domain": "item9_receipt_path",
                "token": "INVALID",
                "detail": str(path_gate.get("reason_code") or "output_path_gate_failed"),
            }
        )
    if str(item9.get("disposition")) == "WRONG_RUNTIME":
        gaps.append(
            {
                "domain": "runtime_authority",
                "token": "UNAVAILABLE",
                "detail": "api_runtime_sha_not_frozen_collector_authority",
            }
        )
    return gaps


def _operator_questions(
    *,
    lifecycle: Mapping[str, Any],
    runtime_sha: str,
    item9: Mapping[str, Any],
    readiness: Mapping[str, Any],
    config_summary: Mapping[str, Any],
    state_path: Mapping[str, Any],
    session: Mapping[str, Any],
    freshness: Mapping[str, Any],
    cycle: Mapping[str, Any],
    evidence_gaps: list[Mapping[str, str]],
    governance: Mapping[str, Any],
) -> dict[str, Any]:
    platform_status = str(lifecycle.get("status") or "UNKNOWN")
    running = platform_status not in {"STOPPED", "UNKNOWN"}
    runtime = item9.get("runtime") if isinstance(item9.get("runtime"), dict) else {}
    collector = item9.get("active_collector") if isinstance(item9.get("active_collector"), dict) else {}
    providers = readiness.get("providers") if isinstance(readiness.get("providers"), list) else []
    rollup = _provider_rollups([row for row in providers if isinstance(row, dict)])

    return {
        "q01_imp_running": {
            "answer": running,
            "detail": platform_status,
            "source": "/operator/lifecycle/status",
        },
        "q02_runtime_git_sha": {
            "answer": runtime_sha,
            "frozen_collector_pin": _PIN_ITEM9_FROZEN_COLLECTOR_SHA[:8],
            "matches_frozen_authority": runtime.get("runtime_matches_frozen_authority"),
            "source": "resolve_runtime_git_sha + item9 preflight",
        },
        "q03_configuration_loaded": {
            "answer": config_summary,
            "state_dir": str(state_dir()),
            "state_path_warnings": state_path.get("warnings") or [],
            "source": "/operator/config + state_path_diagnostic",
        },
        "q04_providers_healthy": {
            "answer": rollup,
            "source": "/operator/readiness",
        },
        "q05_providers_degraded": {
            "answer": [
                row
                for row in providers
                if isinstance(row, dict)
                and (
                    str(row.get("transport_state")) in {"UNAVAILABLE", "BLOCKED_NON_LOOPBACK", "DEGRADED"}
                    or str(row.get("gate_state")) != "ENABLED"
                )
            ],
            "source": "/operator/readiness",
        },
        "q06_data_fresh": {
            "answer": freshness,
            "source": "/operator/readiness + /provider/health + /opportunities/summary",
        },
        "q07_session_evidence_class": {
            "answer": session,
            "source": "composed",
        },
        "q08_collector_active": {
            "answer": bool(collector.get("detected")),
            "process_probe_status": collector.get("process_probe_status"),
            "source": "item9 preflight (probe optional; default NOT_RUN in API)",
        },
        "q09_collector_identity": {
            "answer": {
                "authorized_worktree": _PIN_FROZEN_COLLECTOR_WORKTREE,
                "authorized_sha_prefix": _PIN_ITEM9_FROZEN_COLLECTOR_SHA[:8],
                "frozen_collector_git_sha": runtime.get("frozen_collector_git_sha"),
                "frozen_collector_available": runtime.get("frozen_collector_available"),
            },
            "source": "item9 preflight + PROGRAM_STATUS pin",
        },
        "q10_expected_cycle_fail": {
            "answer": cycle.get("expected_cycle_failure"),
            "detail": cycle.get("gap_note"),
            "source": "NOT_OBSERVED (gap)",
        },
        "q11_recovery_observed": {
            "answer": cycle.get("recovery_observed"),
            "lifecycle_degraded_services": cycle.get("lifecycle_degraded_services"),
            "source": "NOT_OBSERVED (gap)",
        },
        "q12_evidence_gaps": {
            "answer": evidence_gaps,
            "source": "composed",
        },
        "q13_allowed_actions": {
            "answer": list(governance.get("allowed_read_only") or []),
            "source": "governance contract",
        },
        "q14_forbidden_actions": {
            "answer": list(governance.get("forbidden") or []),
            "source": "governance contract",
        },
        "q15_operator_intervention": {
            "answer": list(governance.get("interventions") or []),
            "source": "composed",
        },
        "q16_human_headline": {
            "answer": governance.get("headline"),
            "source": "composed",
        },
    }


def _governance_block(
    *,
    lifecycle_status: str,
    readiness_status: str,
    item9_disposition: str,
    state_warnings: list[str],
    interventions: list[str],
) -> dict[str, Any]:
    headline_parts: list[str] = []
    if lifecycle_status == "STOPPED":
        headline_parts.append("Platform services are stopped.")
    elif lifecycle_status not in {"HEALTHY", "OK", "RUNNING", "DEGRADED"}:
        headline_parts.append(f"Platform lifecycle status is {lifecycle_status}.")
    if readiness_status not in {"READY"}:
        headline_parts.append(f"Operator readiness is {readiness_status}.")
    if item9_disposition == "WRONG_RUNTIME":
        headline_parts.append(
            "API runtime SHA is not the frozen Item 9 collector authority; "
            "do not start prospective --poll from this checkout."
        )
    if "WORKTREE_STATE_MISMATCH" in state_warnings:
        headline_parts.append(
            "Persistence may be on the canonical state dir while this API runs from a linked worktree."
        )
    if not headline_parts:
        headline_parts.append("No blocking operator headline; inspect section details before governed actions.")

    return {
        "headline": " ".join(headline_parts),
        "allowed_read_only": list(_READ_ONLY_OPERATOR_ACTIONS),
        "forbidden": list(_FORBIDDEN_OPERATOR_ACTIONS),
        "interventions": interventions,
        "live_execution_env": live_execution_env_enabled(),
        "paper_execution_env": paper_execution_env_enabled(),
    }


def build_operator_diagnostics_snapshot(store: ReplayStore) -> dict[str, Any]:
    """Build a leak-safe, machine-readable operator diagnostic snapshot."""
    imp_root = _imp_root()
    runtime_sha = resolve_runtime_git_sha(start=imp_root)

    from tools.platform.control_service import build_control_status
    from tools.state_path_diagnostic import collect_state_path_report

    lifecycle = build_control_status(imp_root)
    readiness = build_operator_readiness_payload(store)
    config = build_operator_config_payload()
    config_summary = _config_summary(config)
    state_path = collect_state_path_report(imp_root)
    item9 = run_item9_next_rth_preflight(imp_root, active_collector_probe=None)
    provider_health = build_provider_health_payload(store)
    opportunity_summary = build_opportunities_summary_payload(store)

    readiness_providers = readiness.get("providers") if isinstance(readiness.get("providers"), list) else []
    session = _classify_session_evidence(store, item9)
    freshness = _freshness_view(readiness_providers, provider_health, opportunity_summary)
    cycle = _cycle_recovery_view(item9, lifecycle)
    evidence_gaps = _evidence_gaps(opportunity_summary, item9)

    interventions: list[str] = []
    if str(lifecycle.get("status")) == "STOPPED":
        interventions.append("Run operator lifecycle start (setup/start) for API/UI/control services.")
    if str(readiness.get("status")) == "ACTION_REQUIRED":
        interventions.append("Resolve provider transport/credential actions from /operator/readiness.")
    if str(item9.get("disposition")) == "PROVIDER_UNAVAILABLE":
        interventions.append("Restore OpenD loopback reachability before Item 9 collection.")
    if str(item9.get("disposition")) == "WRONG_RUNTIME":
        interventions.append(
            f"Use worktree {_PIN_FROZEN_COLLECTOR_WORKTREE} @ {_PIN_ITEM9_FROZEN_COLLECTOR_SHA[:8]} for governed collection."
        )
    if state_path.get("warnings"):
        interventions.append("Run python tools/imp.py state-path and align IMP_STATE_DIR with canonical FTEP state.")

    governance = _governance_block(
        lifecycle_status=str(lifecycle.get("status") or "UNKNOWN"),
        readiness_status=str(readiness.get("status") or "UNKNOWN"),
        item9_disposition=str(item9.get("disposition") or "UNKNOWN"),
        state_warnings=list(state_path.get("warnings") or []),
        interventions=interventions,
    )

    questions = _operator_questions(
        lifecycle=lifecycle,
        runtime_sha=runtime_sha,
        item9=item9,
        readiness=readiness,
        config_summary=config_summary,
        state_path=state_path,
        session=session,
        freshness=freshness,
        cycle=cycle,
        evidence_gaps=evidence_gaps,
        governance=governance,
    )

    severity = "OK"
    if str(lifecycle.get("status")) == "STOPPED":
        severity = "STOPPED"
    elif str(readiness.get("status")) != "READY" or evidence_gaps:
        severity = "DEGRADED"
    if str(item9.get("disposition")) in {"WRONG_RUNTIME", "PROVIDER_UNAVAILABLE", "OUTPUT_PATH_INVALID"}:
        severity = "ACTION_REQUIRED"

    return {
        "schema_version": _SCHEMA_VERSION,
        "as_of_utc": datetime.now(timezone.utc).isoformat(),
        "severity": severity,
        "secrets_included": False,
        "operator_questions": questions,
        "sections": {
            "lifecycle": {
                "status": lifecycle.get("status"),
                "services": lifecycle.get("services"),
                "update": lifecycle.get("update"),
            },
            "runtime": {
                "imp_project_root": str(imp_root),
                "git_sha": runtime_sha,
                "frozen_collector_worktree_rel": str(FROZEN_COLLECTOR_WORKTREE_REL),
                "item9_preflight": {
                    "disposition": item9.get("disposition"),
                    "blockers": item9.get("blockers"),
                    "reason_codes": item9.get("reason_codes"),
                    "calendar": item9.get("calendar"),
                    "runtime": item9.get("runtime"),
                    "active_collector": item9.get("active_collector"),
                    "does_not_start_collector": item9.get("does_not_start_collector"),
                },
            },
            "configuration": {
                "summary": config_summary,
                "state_path": state_path,
            },
            "readiness": {
                "status": readiness.get("status"),
                "checks": readiness.get("checks"),
                "providers": readiness.get("providers"),
                "as_of_context": readiness.get("as_of_context"),
            },
            "provider_health": {
                "available": provider_health.get("available"),
                "reason": provider_health.get("reason"),
                "provider_summary": provider_health.get("provider_summary"),
            },
            "opportunity_surface": {
                "feed_status": opportunity_summary.get("feed_status"),
                "unready_reason": opportunity_summary.get("unready_reason"),
                "quality_summary": opportunity_summary.get("quality_summary"),
            },
            "session_evidence": session,
            "cycle_recovery": cycle,
            "evidence_gaps": evidence_gaps,
            "governance": governance,
        },
        "human_summary": [
            governance["headline"],
            f"Lifecycle: {lifecycle.get('status')}; readiness: {readiness.get('status')}; "
            f"Item 9 preflight disposition: {item9.get('disposition')}.",
            f"Runtime SHA {runtime_sha[:12]}…; frozen collector pin {_PIN_ITEM9_FROZEN_COLLECTOR_SHA[:8]}….",
        ],
        "sources_composed": [
            "GET /operator/lifecycle/status",
            "GET /operator/readiness",
            "GET /operator/config",
            "GET /provider/health",
            "GET /opportunities/summary",
            "tools/state_path_diagnostic.collect_state_path_report",
            "item9_next_rth_preflight.run_item9_next_rth_preflight (read-only, no process probe)",
        ],
        "generated_at_monotonic": time.monotonic(),
    }
