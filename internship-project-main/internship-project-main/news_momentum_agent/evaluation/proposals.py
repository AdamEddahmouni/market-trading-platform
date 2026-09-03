"""Proposal reports + audit log (manual review only — never auto-applies config).

Purpose
-------
Turn pattern-miner survivors into human-readable proposals and markdown reports.

Features / API role
-------------------
``build_proposals``, ``write_proposals``, ``format_proposals_markdown``,
``update_proposal_status``, ``append_audit``.

How this uses ``options_confirmation_engine``
-----------------------------------------------
Indirectly via miner patterns on ``options_band`` / ``options_bias`` fields from
replay that used engine scoring.

Options-specific vs reusable
----------------------------
Proposal text references options bands; audit workflow is reusable for any miner output.

Manual review only — never auto-applies config.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from evaluation.spy_qqq_replay import PATH_A_EXCLUSION_NOTE

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROPOSALS_DIR = PROJECT_ROOT / "state" / "learning" / "proposals"
AUDIT_PATH = PROJECT_ROOT / "state" / "learning" / "proposal_audit.jsonl"


def _suggest_config_change(pattern: Dict[str, Any]) -> str:
    feature = str(pattern.get("feature") or "")
    value = str(pattern.get("value") or "")
    kind = str(pattern.get("kind") or "")
    if feature == "lean_band" and kind == "protective":
        return (
            f"Suggestion (not applied): consider raising min lean strength so setups with "
            f"lean_band={value} are less likely to size/enter — review evidence first."
        )
    if feature == "confidence_band" and kind == "protective":
        return (
            f"Suggestion (not applied): review confidence calibration; band {value} underperformed "
            f"in discovery+validation — do not raise size on this band without more live evidence."
        )
    if feature == "would_be_side":
        return (
            f"Suggestion (not applied): review Path B side filter for side={value} "
            f"(favorable={kind == 'favorable'}). Manual settings change only if you agree."
        )
    if feature == "tod_bucket":
        return (
            f"Suggestion (not applied): review time-of-day gating for tod_bucket={value}. "
            f"If cache is EOD-only, prefer ignoring TOD proposals."
        )
    return (
        f"Suggestion (not applied): review gate/weight related to {feature}={value} "
        f"({kind}). Attach evidence below; human must edit settings.json manually if adopted."
    )


def build_proposals(miner_result: Dict[str, Any]) -> Dict[str, Any]:
    """Convert miner survivors into pending proposal dicts with suggested (non-applied) edits."""
    survivors = list(miner_result.get("survivors") or [])
    proposals = []
    for idx, pat in enumerate(survivors, start=1):
        val = pat.get("validation") or {}
        proposals.append(
            {
                "id": f"prop_{idx}_{pat.get('feature')}_{pat.get('value')}",
                "description": pat.get("summary"),
                "feature": pat.get("feature"),
                "value": pat.get("value"),
                "discovery": {
                    "n": pat.get("n"),
                    "win_rate": pat.get("win_rate"),
                    "wilson_lo": pat.get("wilson_lo"),
                    "wilson_hi": pat.get("wilson_hi"),
                    "lift": pat.get("lift"),
                    "avg_r_multiple": pat.get("avg_r_multiple"),
                    "expectancy_pnl_pct": pat.get("expectancy_pnl_pct"),
                },
                "validation": {
                    "n": val.get("n"),
                    "win_rate": val.get("win_rate"),
                    "wilson_lo": val.get("wilson_lo"),
                    "wilson_hi": val.get("wilson_hi"),
                    "lift": val.get("lift"),
                    "avg_r_multiple": val.get("avg_r_multiple"),
                    "expectancy_pnl_pct": val.get("expectancy_pnl_pct"),
                },
                "proposed_config_change": _suggest_config_change(pat),
                "status": "pending",
                "auto_apply": False,
            }
        )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "path_a_note": PATH_A_EXCLUSION_NOTE,
        "confidence_note": (
            "Keep source_kind visible; backtest_replay ≠ live_executed. "
            "No proposal is applied automatically."
        ),
        "miner_meta": {
            "min_n": miner_result.get("min_n"),
            "discovery_days": miner_result.get("discovery_days"),
            "validation_days": miner_result.get("validation_days"),
            "n_survivors": len(survivors),
            "n_failed_oos": len(miner_result.get("found_but_did_not_replicate") or []),
        },
        "proposals": proposals,
        "found_but_did_not_replicate": miner_result.get("found_but_did_not_replicate") or [],
    }


def format_proposals_markdown(payload: Dict[str, Any]) -> str:
    """Render proposal payload as markdown for human review."""
    lines = [
        "# SPY/QQQ research proposals (manual review only)",
        "",
        str(payload.get("path_a_note") or PATH_A_EXCLUSION_NOTE),
        "",
        str(payload.get("confidence_note") or ""),
        "",
        f"Generated: {payload.get('generated_at')}",
        f"Survivors: {payload.get('miner_meta', {}).get('n_survivors', 0)}",
        f"Failed OOS (logged): {payload.get('miner_meta', {}).get('n_failed_oos', 0)}",
        "",
    ]
    props = payload.get("proposals") or []
    if not props:
        lines.append("No patterns survived N-floor + chronological OOS validation.")
        lines.append("")
        failed = payload.get("found_but_did_not_replicate") or []
        if failed:
            lines.append("## Found but did not replicate")
            for row in failed[:20]:
                lines.append(
                    f"- {row.get('summary')} — {row.get('fail_reason')} "
                    f"(discovery N={row.get('n')})"
                )
        return "\n".join(lines)

    lines.append("## Surviving proposals")
    for p in props:
        disc = p.get("discovery") or {}
        val = p.get("validation") or {}
        lines.extend(
            [
                f"### {p.get('id')}",
                f"- {p.get('description')}",
                f"- discovery: N={disc.get('n')} win_rate={disc.get('win_rate')} "
                f"CI=[{disc.get('wilson_lo')},{disc.get('wilson_hi')}] lift={disc.get('lift')} "
                f"avg_R={disc.get('avg_r_multiple')} E[pnl]={disc.get('expectancy_pnl_pct')}",
                f"- validation: N={val.get('n')} win_rate={val.get('win_rate')} "
                f"CI=[{val.get('wilson_lo')},{val.get('wilson_hi')}] lift={val.get('lift')} "
                f"avg_R={val.get('avg_r_multiple')} E[pnl]={val.get('expectancy_pnl_pct')}",
                f"- {p.get('proposed_config_change')}",
                f"- status: {p.get('status')} (auto_apply=false)",
                "",
            ]
        )
    return "\n".join(lines)


def write_proposals(payload: Dict[str, Any], proposals_dir: Path = PROPOSALS_DIR) -> Dict[str, Path]:
    """Persist timestamped and ``latest_proposal`` JSON/markdown files; append audit entry."""
    proposals_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    json_path = proposals_dir / f"proposal_{stamp}.json"
    md_path = proposals_dir / f"proposal_{stamp}.md"
    latest_json = proposals_dir / "latest_proposal.json"
    latest_md = proposals_dir / "latest_proposal.md"
    text = json.dumps(payload, indent=2, default=str)
    md = format_proposals_markdown(payload)
    json_path.write_text(text, encoding="utf-8")
    md_path.write_text(md, encoding="utf-8")
    latest_json.write_text(text, encoding="utf-8")
    latest_md.write_text(md, encoding="utf-8")
    append_audit(
        {
            "ts": payload.get("generated_at"),
            "event": "proposals_generated",
            "path": str(json_path),
            "n_proposals": len(payload.get("proposals") or []),
            "statuses": ["pending"] * len(payload.get("proposals") or []),
        }
    )
    return {"json": json_path, "md": md_path, "latest_json": latest_json, "latest_md": latest_md}


def append_audit(record: Dict[str, Any], path: Path = AUDIT_PATH) -> None:
    """Append one JSONL audit record for proposal lifecycle events."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, default=str) + "\n")


def update_proposal_status(
    proposal_id: str,
    status: str,
    *,
    proposals_path: Optional[Path] = None,
    note: str = "",
) -> Dict[str, Any]:
    """Mark a proposal pending/adopted/rejected and rewrite latest files + audit."""
    if status not in {"pending", "adopted", "rejected"}:
        raise ValueError("status must be pending|adopted|rejected")
    path = proposals_path or (PROPOSALS_DIR / "latest_proposal.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    found = False
    for prop in payload.get("proposals") or []:
        if prop.get("id") == proposal_id:
            prop["status"] = status
            prop["status_note"] = note
            prop["status_updated_at"] = datetime.now(timezone.utc).isoformat()
            found = True
            break
    if not found:
        raise KeyError(f"proposal id not found: {proposal_id}")
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    md_path = path.with_suffix(".md")
    md_path.write_text(format_proposals_markdown(payload), encoding="utf-8")
    append_audit(
        {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": "proposal_status_update",
            "proposal_id": proposal_id,
            "status": status,
            "note": note,
            "path": str(path),
        }
    )
    return payload
