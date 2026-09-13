"""Read-only post-session catalyst attention watch (fixture / dry-run)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .campaign_status import collect_ftep_campaign_status

_ARTIFACT_KIND = "ftep_catalyst_watch_report"


def _artifact_dir_for_slug(campaign_slug: str) -> str:
    return campaign_slug.lower().replace("_", "-")


def governed_session_start_evidence_path(repository_root: Path, campaign_slug: str) -> Path:
    return (
        repository_root
        / "artifacts"
        / _artifact_dir_for_slug(campaign_slug)
        / "governed-session-start-evidence.jsonl"
    )


def load_governed_session_ids_from_evidence(
    repository_root: Path,
    campaign_slug: str,
) -> tuple[list[str], str | None]:
    """Return session_ids from append-only evidence; error detail if file missing."""

    path = governed_session_start_evidence_path(repository_root, campaign_slug)
    if not path.is_file():
        return [], None
    session_ids: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(record, dict):
            continue
        for item in record.get("sessions_created") or []:
            if isinstance(item, dict) and item.get("session_id"):
                session_ids.append(str(item["session_id"]))
    return session_ids, str(path)


def campaign_attention_fixture_path(repository_root: Path, campaign_slug: str) -> Path:
    return (
        repository_root
        / "artifacts"
        / "forward-test-campaigns"
        / campaign_slug
        / "opportunity-attention-fixture.json"
    )


def _load_attention_rows_safe(
    repository_root: Path,
    campaign_slug: str,
    *,
    fixture_only: bool,
    input_path: Path | None,
) -> tuple[list[dict[str, object]], str]:
    if input_path is not None:
        raw = json.loads(input_path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise ValueError("--input must contain a JSON array of attention rows")
        rows = [item for item in raw if isinstance(item, dict)]
        return rows, str(input_path)

    fixture = campaign_attention_fixture_path(repository_root, campaign_slug)
    if fixture.is_file():
        raw = json.loads(fixture.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise ValueError(f"{fixture} must contain a JSON array of attention rows")
        rows = [item for item in raw if isinstance(item, dict)]
        return rows, str(fixture.relative_to(repository_root))

    if fixture_only:
        raise FileNotFoundError(f"campaign fixture missing: {fixture}")

    sample_rows: tuple[dict[str, object], ...] = (
        {
            "attention_id": "att-catalyst-aapl",
            "symbol": "AAPL",
            "headline": "AAPL catalyst signal",
            "tier": 2,
            "catalyst_ids": ("earnings",),
        },
        {
            "attention_id": "att-catalyst-nvda",
            "symbol": "NVDA",
            "headline": "NVIDIA reports stronger than expected quarterly earnings outlook",
            "tier": 1,
            "catalyst_ids": ("earnings", "guidance", "analyst"),
        },
    )
    return [dict(item) for item in sample_rows], "sample"


def collect_ftep_catalyst_watch(
    repository_root: Path,
    campaign_slug: str = "FTEP-V1-002",
    *,
    fixture_only: bool = False,
    input_path: Path | None = None,
) -> dict[str, Any]:
    """Compose campaign status, evidence session_ids, and ranked fixture summaries (no writes)."""

    status = collect_ftep_campaign_status(repository_root, campaign_slug)
    governed_count = int(status.get("governed_session_count") or 0)
    rth_open = bool(status.get("us_equity_rth_open"))
    session_ids, evidence_path = load_governed_session_ids_from_evidence(
        repository_root,
        campaign_slug,
    )

    use_fixture = fixture_only or governed_count == 0 or not rth_open
    watch_mode = "FIXTURE_SMOKE" if use_fixture else "SESSION_ACTIVE_CORRELATION"

    blockers: list[str] = []
    operator_hints: list[str] = []
    if watch_mode == "SESSION_ACTIVE_CORRELATION" and not session_ids:
        blockers.append("GOVERNED_SESSION_EVIDENCE_MISSING")
        operator_hints.append(
            "Governed sessions exist in durable state but "
            "governed-session-start-evidence.jsonl has no session_id rows."
        )
    if governed_count > 0 and not rth_open:
        operator_hints.append(
            "US_EQUITY_RTH closed: catalyst watch uses fixture summaries only "
            "(no live Finviz ingress; correlate when RTH reopens)."
        )
    if governed_count == 0:
        operator_hints.append(
            "No governed sessions yet: fixture smoke only. "
            "After RTH session-start, re-run watch-catalysts to correlate session_ids."
        )

    rows, source_label = _load_attention_rows_safe(
        repository_root,
        campaign_slug,
        fixture_only=use_fixture,
        input_path=input_path,
    )

    from market_platform_foundation.intelligence.opportunity.read_model import (
        ftep_attention_candidate_to_summary,
        rank_opportunity_summaries,
    )

    summaries = tuple(
        ftep_attention_candidate_to_summary(row, campaign_slug=campaign_slug) for row in rows
    )
    ranked = rank_opportunity_summaries(summaries)

    correlation: list[dict[str, object]] = []
    if session_ids and ranked:
        for session_id in session_ids:
            correlation.append(
                {
                    "session_id": session_id,
                    "summary_count": len(ranked),
                    "top_instrument_id": ranked[0].instrument_id,
                    "note": "Operator correlates ranked summaries with open session (no auto lock).",
                }
            )

    disposition = "PASS" if not blockers else "BLOCKED"
    return {
        "schema_version": "1.0.0",
        "artifact_kind": _ARTIFACT_KIND,
        "campaign_slug": campaign_slug,
        "dry_run": True,
        "watch_mode": watch_mode,
        "disposition": disposition,
        "blockers": blockers,
        "operator_hints": operator_hints,
        "campaign_status": {
            "us_equity_rth_open": rth_open,
            "governed_session_count": governed_count,
            "empirical_lock_count": status.get("empirical_lock_count"),
            "manifest_fingerprint": status.get("manifest_fingerprint"),
        },
        "governed_session_ids": session_ids,
        "evidence_path": evidence_path,
        "attention_source": source_label,
        "summary_count": len(ranked),
        "summaries": [item.to_dict() for item in ranked],
        "session_correlation": correlation,
        "secrets_included": False,
    }


__all__ = [
    "collect_ftep_catalyst_watch",
    "governed_session_start_evidence_path",
    "load_governed_session_ids_from_evidence",
]
