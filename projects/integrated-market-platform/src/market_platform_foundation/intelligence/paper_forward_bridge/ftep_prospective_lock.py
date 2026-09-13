"""Governed prospective decision-lock gates (dry-run; no fabricated locks)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .activation import load_activation_manifest, manifest_universe_symbols
from .campaign_status import (
    collect_ftep_campaign_status,
    empirical_lock_authorized,
    manifest_operator_empirical_lock_authorized,
)
from .ftep_catalyst_watch import collect_ftep_catalyst_watch
from .ftep_integrity import collect_ftep_integrity_checks

_ARTIFACT_KIND = "ftep_prospective_lock_gate"
_QUALIFYING_MAX_TIER = 2


def manifest_empirical_lock_authorized(
    repository_root: Path,
    campaign_slug: str,
) -> bool:
    """Backward-compatible alias: manifest attestation OR post-freeze authorization receipts."""

    return empirical_lock_authorized(repository_root, campaign_slug)


def _select_qualifying_summary(
    summaries: list[dict[str, object]],
) -> dict[str, object] | None:
    for item in summaries:
        meta = item.get("metadata") or {}
        tier = meta.get("tier") if isinstance(meta, dict) else None
        if tier is None:
            continue
        try:
            tier_int = int(tier)
        except (TypeError, ValueError):
            continue
        if tier_int <= _QUALIFYING_MAX_TIER:
            return item
    return None


def _build_forward_test_lock_invoke_steps(
    repository_root: Path,
    campaign_slug: str,
    *,
    qualifying_summary: dict[str, object],
    session_id: str,
) -> list[dict[str, object]]:
    manifest = load_activation_manifest(campaign_slug)
    binding = manifest.binding
    account_scope = manifest.raw.get("account_scope") or {}
    scope_account = (
        str(account_scope.get("account_id") or "") if isinstance(account_scope, dict) else ""
    )
    paper_account_id = str(binding.get("paper_account_id") or scope_account)
    arms = binding.get("cohort_arms") or {}
    baseline = arms.get("baseline") if isinstance(arms, dict) else None
    if not isinstance(baseline, dict):
        baseline = {}
    policy_id = str(baseline.get("policy_id") or "")
    policy_version = str(baseline.get("policy_version") or "1.0.0")
    symbol = str(qualifying_summary.get("instrument_id") or "").upper()
    universe = set(manifest_universe_symbols(manifest))
    if symbol not in universe:
        return []

    attention_id = ""
    meta = qualifying_summary.get("metadata") or {}
    if isinstance(meta, dict):
        attention_id = str(meta.get("attention_id") or qualifying_summary.get("summary_id") or "")

    return [
        {
            "step": 1,
            "action": "ForwardTestService.create_decision",
            "test_mode": "SIGNAL_ONLY",
            "note": (
                "Event-driven lock path after qualifying catalyst attention; "
                "zero Paper order preview/submit."
            ),
            "kwargs": {
                "account_id": paper_account_id,
                "mode": "PAPER",
                "session_id": session_id,
                "symbol": symbol,
                "direction": "BUY",
                "strategy_id": policy_id,
                "strategy_version": policy_version,
                "decision_payload": {
                    "catalyst_attention_id": attention_id,
                    "pipeline": "ftep_prospective_lock",
                },
            },
        },
        {
            "step": 2,
            "action": "ForwardTestService.lock_decision",
            "note": "Transitions DRAFT→LOCKED; records first_lock_at_ns on campaign binding.",
            "kwargs": {
                "account_id": paper_account_id,
                "forward_test_id": "<from_create_decision>",
            },
        },
    ]


def collect_ftep_prospective_lock_gates(
    repository_root: Path,
    campaign_slug: str = "FTEP-V1-002",
    *,
    fixture_only: bool = False,
    input_path: Path | None = None,
) -> dict[str, Any]:
    """Evaluate lock invariants; never writes durable forward-test state."""

    status = collect_ftep_campaign_status(repository_root, campaign_slug)
    watch = collect_ftep_catalyst_watch(
        repository_root,
        campaign_slug,
        fixture_only=fixture_only,
        input_path=input_path,
    )
    integrity = collect_ftep_integrity_checks(repository_root, campaign_slug)

    blockers: list[str] = []
    operator_hints: list[str] = list(watch.get("operator_hints") or [])

    if not status.get("signal_only_authorized"):
        blockers.append("SIGNAL_ONLY_NOT_AUTHORIZED")
    if status.get("manifest_status") != "FROZEN":
        blockers.append("ACTIVATION_MANIFEST_NOT_FROZEN")
    if not empirical_lock_authorized(repository_root, campaign_slug):
        blockers.append("EMPIRICAL_LOCK_NOT_AUTHORIZED")
    if not status.get("us_equity_rth_open"):
        blockers.append("US_EQUITY_RTH_CLOSED")
    governed_count = int(status.get("governed_session_count") or 0)
    if governed_count == 0:
        blockers.append("NO_GOVERNED_SESSION")
    if integrity["disposition"] != "PASS":
        blockers.append("INTEGRITY_CHECK_FAILED")
    if watch.get("disposition") != "PASS":
        for item in watch.get("blockers") or ():
            code = str(item)
            if code not in blockers:
                blockers.append(code)

    summaries = watch.get("summaries") or []
    qualifying = _select_qualifying_summary(
        [item for item in summaries if isinstance(item, dict)]
    )
    if qualifying is None and summaries:
        blockers.append("NO_QUALIFYING_CATALYST_TIER")
    elif not summaries:
        blockers.append("NO_CATALYST_SUMMARIES")

    session_ids = list(watch.get("governed_session_ids") or [])
    target_session_id = session_ids[0] if session_ids else None
    if governed_count > 0 and not target_session_id:
        if "GOVERNED_SESSION_EVIDENCE_MISSING" not in blockers:
            blockers.append("GOVERNED_SESSION_EVIDENCE_MISSING")

    would_record = not blockers
    payload: dict[str, Any] = {
        "schema_version": "1.0.0",
        "artifact_kind": _ARTIFACT_KIND,
        "campaign_slug": campaign_slug,
        "dry_run": True,
        "would_record_lock": would_record,
        "test_mode": "SIGNAL_ONLY",
        "blockers": blockers,
        "operator_hints": operator_hints,
        "watch_mode": watch.get("watch_mode"),
        "qualifying_catalyst": qualifying,
        "target_session_id": target_session_id,
        "campaign_status": {
            "us_equity_rth_open": status.get("us_equity_rth_open"),
            "manifest_fingerprint": status.get("manifest_fingerprint"),
            "governed_session_count": governed_count,
            "empirical_lock_count": status.get("empirical_lock_count"),
            "empirical_lock_authorized": empirical_lock_authorized(
                repository_root,
                campaign_slug,
            ),
            "manifest_operator_empirical_lock_authorized": manifest_operator_empirical_lock_authorized(
                campaign_slug
            ),
        },
        "secrets_included": False,
    }
    if would_record and qualifying is not None and target_session_id:
        steps = _build_forward_test_lock_invoke_steps(
            repository_root,
            campaign_slug,
            qualifying_summary=qualifying,
            session_id=target_session_id,
        )
        if not steps:
            payload["would_record_lock"] = False
            payload["blockers"] = [*blockers, "QUALIFYING_SYMBOL_NOT_IN_MANIFEST_UNIVERSE"]
        else:
            payload["forward_test_invoke_steps"] = steps
    return payload


__all__ = [
    "collect_ftep_prospective_lock_gates",
    "manifest_empirical_lock_authorized",
]
