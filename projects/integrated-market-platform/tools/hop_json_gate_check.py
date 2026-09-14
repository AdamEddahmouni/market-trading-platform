"""Monday cash RTH gate checker for Path A hop JSON.

Reads one hop artifact emitted by ``tools/path_a_prospective_run.py``. Does not
edit git, declare EMPIRICAL_ACTIVE, or flip DoD scoreboard rows.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Mapping

MOOMOO_OPEND_L1 = "moomoo.opend.observational"
FINVIZ_OVERLAY_ID = "finviz.elite.context"


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _finviz_overlay_present(equity_context: Mapping[str, Any]) -> tuple[bool, str]:
    """True when Finviz Elite overlay is admitted on this hop JSON (never L1)."""
    discovery = _as_dict(equity_context.get("discovery"))
    overlay_result = _as_dict(equity_context.get("result"))

    if discovery.get("provider_id") != FINVIZ_OVERLAY_ID:
        return False, str(discovery.get("provider_id") or "absent")

    if overlay_result.get("is_l1") is True:
        return False, "finviz_marked_l1"

    auto_fetch = str(discovery.get("auto_fetch_status") or "")
    if auto_fetch == "FETCHED":
        return True, "FETCHED"

    classification = str(discovery.get("classification") or "")
    reason = str(discovery.get("reason_code") or overlay_result.get("reason_code") or "")
    if classification in {"CONFIGURED", "CONFIGURED_BLOCKED"} and reason == "LIVE_DISABLED":
        if discovery.get("overlay_token_present") is True or auto_fetch in {
            "FETCHED",
            "NOT_ATTEMPTED",
        }:
            return auto_fetch == "FETCHED", auto_fetch or classification

    return False, auto_fetch or classification or "NOT_PRESENT"


def _hop_l1_is_opend(payload: Mapping[str, Any]) -> tuple[bool, str]:
    """L1 identity from admitted hop result + discovery stack (not top-level quotes)."""
    result = _as_dict(payload.get("result"))
    discovery = _as_dict(payload.get("discovery"))

    result_pid = str(result.get("provider_id") or "")
    discovery_pid = str(discovery.get("provider_id") or "")

    if result_pid != MOOMOO_OPEND_L1:
        return False, result_pid or "missing"
    if discovery_pid != MOOMOO_OPEND_L1:
        return False, f"discovery={discovery_pid or 'missing'}"

    if "last_price" in payload:
        return False, "top_level_last_price_present"

    return True, MOOMOO_OPEND_L1


def evaluate_hop(payload: Mapping[str, Any]) -> dict[str, str]:
    result = _as_dict(payload.get("result"))
    freshness = _as_dict(result.get("freshness"))
    actionable = freshness.get("actionable") is True

    l1_ok, l1_detail = _hop_l1_is_opend(payload)
    finviz_ok, finviz_detail = _finviz_overlay_present(_as_dict(payload.get("equity_context")))

    item2_flip = actionable and l1_ok and finviz_ok
    emit = "run" if item2_flip else "skip"

    return {
        "ITEM2_FLIP": "yes" if item2_flip else "no",
        "EMIT": emit,
        "FTEP": "NOT_READY",
        "freshness_actionable": "true" if actionable else "false",
        "hop_l1_provider": l1_detail,
        "finviz_overlay": finviz_detail if finviz_ok else f"no:{finviz_detail}",
        "g7_status": str(result.get("status") or "missing"),
        "path_a_status": str(result.get("path_a_status") or "null"),
        "persist_context_injected": "true"
        if payload.get("persist_context_injected") is True
        else "false",
    }


def _human_summary(metrics: Mapping[str, str]) -> str:
    lines = [
        "Hop JSON gate (Monday cash RTH).",
        f"Item 2 flip: {metrics['ITEM2_FLIP']} — DoD item 2 stays PARTIAL unless ITEM2_FLIP=yes "
        "(freshness.actionable=true, hop L1 moomoo.opend.observational, Finviz overlay FETCHED on same JSON).",
        f"Emit guidance: EMIT={metrics['EMIT']} (run second-hop produce only when ITEM2_FLIP=yes; else skip).",
        f"FTEP: {metrics['FTEP']} (this checker never declares EMPIRICAL_ACTIVE).",
        f"Observed: G7={metrics['g7_status']}, path_a_status={metrics['path_a_status']}, "
        f"persist_context_injected={metrics['persist_context_injected']}.",
        "Top-level last_price is not L1 evidence; do not treat Sunday stale leftover hops as MATCHED.",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 1:
        print("usage: python3 hop_json_gate_check.py PATH_TO_HOP_JSON", file=sys.stderr)
        return 2

    path = Path(args[0])
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"ERROR=unreadable path={path} detail={exc}", file=sys.stderr)
        return 1

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"ERROR=invalid_json path={path} detail={exc}", file=sys.stderr)
        return 1

    if not isinstance(payload, dict):
        print(f"ERROR=invalid_root path={path} detail=expected_object", file=sys.stderr)
        return 1

    metrics = evaluate_hop(payload)
    for key in (
        "ITEM2_FLIP",
        "EMIT",
        "FTEP",
        "freshness_actionable",
        "hop_l1_provider",
        "finviz_overlay",
        "g7_status",
        "path_a_status",
        "persist_context_injected",
    ):
        print(f"{key}={metrics[key]}")
    print()
    print(_human_summary(metrics))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
