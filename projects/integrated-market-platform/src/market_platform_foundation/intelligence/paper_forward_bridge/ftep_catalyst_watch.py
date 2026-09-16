"""Read-only post-session catalyst attention watch (fixture / dry-run)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ...git_ref import main_working_tree
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


def operator_primary_imp_root_for_evidence(repository_root: Path) -> Path | None:
    """Canonical IMP tree on the git primary checkout (monorepo layout)."""

    main = main_working_tree(start=repository_root)
    if main is None:
        return None
    candidate = main / "projects" / "integrated-market-platform"
    try:
        if (candidate / "phase0-dependency-lock.json").is_file():
            return candidate
    except OSError:
        return None
    return None


def _session_ids_from_evidence_file(path: Path) -> list[str]:
    session_ids: list[str] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return session_ids
    for line in lines:
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
    return session_ids


def _evidence_search_roots(repository_root: Path) -> tuple[Path, ...]:
    roots: list[Path] = [repository_root]
    primary = operator_primary_imp_root_for_evidence(repository_root)
    if primary is None:
        return tuple(roots)
    try:
        if primary.resolve() != repository_root.resolve():
            roots.append(primary)
    except OSError:
        roots.append(primary)
    return tuple(roots)


def load_governed_session_ids_from_evidence(
    repository_root: Path,
    campaign_slug: str,
) -> tuple[list[str], str | None]:
    """Return session_ids from append-only evidence; missing file is empty.

    Gitignored operator evidence lives on the primary IMP checkout. Linked
    worktrees must not treat that absence as a missing campaign.
    """

    last_path: str | None = None
    for root in _evidence_search_roots(repository_root):
        path = governed_session_start_evidence_path(root, campaign_slug)
        if not path.is_file():
            continue
        last_path = str(path)
        session_ids = _session_ids_from_evidence_file(path)
        if session_ids:
            return session_ids, last_path
    return [], last_path


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


def _attention_data_kind_from_source(source_label: str, *, live: bool) -> str:
    if live:
        return "LIVE_PROSPECTIVE"
    if source_label == "none":
        return "UNAVAILABLE"
    if source_label == "sample":
        return "SAMPLE"
    return "FIXTURE"


def collect_ftep_catalyst_watch(
    repository_root: Path,
    campaign_slug: str = "FTEP-V1-002",
    *,
    fixture_only: bool = False,
    input_path: Path | None = None,
    live_ingress: bool = False,
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
    if governed_count == 0 and not live_ingress:
        operator_hints.append(
            "No governed sessions yet: fixture smoke only. "
            "After RTH session-start, re-run watch-catalysts to correlate session_ids."
        )

    live_ingress_requested = live_ingress and input_path is None
    prospective_ingress_report: dict[str, object] | None = None
    prospective_ingress_result: Any | None = None
    observational_cockpit_admit: dict[str, object] | None = None
    used_live_ingress = False
    rows: list[dict[str, object]]
    source_label: str
    if live_ingress_requested and use_fixture:
        from .ftep_prospective_catalyst_ingress import session_unavailable_ingress_report

        prospective_ingress_report = session_unavailable_ingress_report(
            rth_open=rth_open,
            governed_count=governed_count,
            fixture_only=fixture_only,
        )
        blockers.append("LIVE_INGRESS_UNAVAILABLE")
        if fixture_only:
            operator_hints.append(
                "--fixture forces FIXTURE_SMOKE; --live-ingress cannot run until fixture mode is cleared."
            )
        elif governed_count == 0:
            operator_hints.append(
                "--live-ingress requires at least one governed session during US equity RTH "
                "(no fixture/SAMPLE substitute)."
            )
        elif not rth_open:
            operator_hints.append(
                "--live-ingress requires US equity RTH open "
                "(no fixture/SAMPLE substitute while RTH is closed)."
            )
        rows = []
        source_label = "none"
    elif not use_fixture and live_ingress_requested:
        from .ftep_prospective_catalyst_ingress import collect_finviz_prospective_attention_rows

        ingress = collect_finviz_prospective_attention_rows(
            repository_root,
            campaign_slug,
            live_ingress=True,
        )
        prospective_ingress_result = ingress
        prospective_ingress_report = ingress.to_report_dict()
        classification = str(prospective_ingress_report.get("classification") or "")
        if ingress.ready and ingress.rows:
            rows = [dict(item) for item in ingress.rows]
            source_label = ingress.source_label
            used_live_ingress = True
        elif ingress.ready and not ingress.rows:
            rows = []
            source_label = ingress.source_label
            used_live_ingress = True
            operator_hints.append(
                "Live Finviz ingress succeeded with zero universe-qualified catalyst rows "
                "(LIVE_INGRESS_SUCCESS_ZERO_QUALIFYING_ROWS); no fixture/SAMPLE substitute."
            )
        else:
            if classification == "GATES_INACTIVE" or ingress.reason == "INGRESS_GATES_INACTIVE":
                blockers.append("PROSPECTIVE_CATALYST_INGRESS_GATES_INACTIVE")
                operator_hints.append(
                    "Set IMP_FTEP_PROSPECTIVE_CATALYST_INGRESS=1 with IMP_FINVIZ_LIVE and "
                    "a configured Finviz Elite token before --live-ingress during RTH."
                )
            elif classification == "TOKEN_ABSENT" or ingress.reason == "FINVIZ_TOKEN_ABSENT":
                blockers.append("FINVIZ_PROSPECTIVE_TOKEN_ABSENT")
                operator_hints.append(
                    "Gates are on but no Finviz Elite token was found. Point "
                    "IMP_FINVIZ_SECRET_DIR at the primary checkout .private "
                    "(never copy .private into worktrees)."
                )
            elif (
                classification == "SECRET_DIR_MISSING"
                or ingress.reason == "FINVIZ_SECRET_DIR_MISSING"
            ):
                blockers.append("FINVIZ_PROSPECTIVE_SECRET_DIR_MISSING")
                operator_hints.append(
                    "Configured Finviz secret dir is missing. Prefer "
                    "IMP_FINVIZ_SECRET_DIR or the primary checkout .private; "
                    "do not search leftover nested clones."
                )
            elif classification == "HTTP_429" or ingress.reason == "FINVIZ_HTTP_429":
                blockers.append("FINVIZ_PROSPECTIVE_RATE_LIMITED")
                operator_hints.append(
                    "Finviz returned HTTP 429. Do not immediately retry; wait and "
                    "re-run a single --live-ingress command later."
                )
            elif classification == "PROVIDER_FAILURE" or ingress.reason == "FINVIZ_FETCH_FAILED":
                blockers.append("FINVIZ_PROSPECTIVE_FETCH_FAILED")
                operator_hints.append(
                    "Finviz prospective fetch failed; attention rows are not live-labelled."
                )
            if not used_live_ingress:
                rows = []
                source_label = "none"
    else:
        loaded_rows, loaded_source = _load_attention_rows_safe(
            repository_root,
            campaign_slug,
            fixture_only=use_fixture,
            input_path=input_path,
        )
        rows = loaded_rows
        source_label = loaded_source

    attention_data_kind = _attention_data_kind_from_source(
        source_label,
        live=used_live_ingress,
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

    ingress_outcome: str | None = None
    ingress_classification: str | None = None
    if live_ingress_requested and prospective_ingress_report is not None:
        ingress_classification = str(prospective_ingress_report.get("classification") or "") or None
        reason = prospective_ingress_report.get("reason")
        if used_live_ingress:
            ingress_outcome = (
                "LIVE_INGRESS_SUCCESS"
                if ranked
                else "LIVE_INGRESS_SUCCESS_ZERO_QUALIFYING_ROWS"
            )
        elif ingress_classification == "HTTP_429" or reason == "FINVIZ_HTTP_429":
            ingress_outcome = "LIVE_INGRESS_RATE_LIMITED"
        elif ingress_classification == "TOKEN_ABSENT" or reason == "FINVIZ_TOKEN_ABSENT":
            ingress_outcome = "LIVE_INGRESS_TOKEN_ABSENT"
        elif (
            ingress_classification == "SECRET_DIR_MISSING"
            or reason == "FINVIZ_SECRET_DIR_MISSING"
        ):
            ingress_outcome = "LIVE_INGRESS_SECRET_DIR_MISSING"
        elif ingress_classification == "GATES_INACTIVE" or reason == "INGRESS_GATES_INACTIVE":
            ingress_outcome = "LIVE_INGRESS_GATES_INACTIVE"
        elif (
            ingress_classification == "SESSION_UNAVAILABLE"
            or reason == "LIVE_INGRESS_UNAVAILABLE"
        ):
            ingress_outcome = "LIVE_INGRESS_UNAVAILABLE"
        elif ingress_classification in {"TIMEOUT", "MALFORMED_RESPONSE"}:
            ingress_outcome = "LIVE_INGRESS_FAILED"
        elif reason == "FINVIZ_FETCH_FAILED" or ingress_classification == "PROVIDER_FAILURE":
            ingress_outcome = "LIVE_INGRESS_FAILED"
        elif prospective_ingress_report.get("attempted") and not used_live_ingress:
            ingress_outcome = "LIVE_INGRESS_FAILED"

    if live_ingress_requested and prospective_ingress_report and watch_mode != "FIXTURE_SMOKE":
        watch_mode = "PROSPECTIVE_FINVIZ_INGRESS"

    if used_live_ingress and prospective_ingress_result is not None:
        from ...ui_api.cockpit_admit import post_prospective_ingress_to_running_ui_api

        observational_cockpit_admit = post_prospective_ingress_to_running_ui_api(
            prospective_ingress_result,
        )
        if prospective_ingress_result.rows and not observational_cockpit_admit.get("ok"):
            blockers.append("COCKPIT_ADMIT_UI_API_UNAVAILABLE")
            operator_hints.append(
                "Start UI API (run_ui_api.py --serve) before --live-ingress so FTEP can "
                f"POST to {observational_cockpit_admit.get('ui_api_base_url')}."
            )

    disposition = "PASS" if not blockers else "BLOCKED"
    return {
        "schema_version": "1.0.0",
        "artifact_kind": _ARTIFACT_KIND,
        "campaign_slug": campaign_slug,
        "dry_run": True,
        "test_mode": "SIGNAL_ONLY",
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
        "attention_data_kind": attention_data_kind,
        "prospective_ingress": prospective_ingress_report,
        "observational_cockpit_admit": observational_cockpit_admit,
        "ingress_outcome": ingress_outcome,
        "ingress_classification": ingress_classification,
        "summary_count": len(ranked),
        "summaries": [item.to_dict() for item in ranked],
        "session_correlation": correlation,
        "secrets_included": False,
    }


__all__ = [
    "collect_ftep_catalyst_watch",
    "governed_session_start_evidence_path",
    "load_governed_session_ids_from_evidence",
    "operator_primary_imp_root_for_evidence",
]
