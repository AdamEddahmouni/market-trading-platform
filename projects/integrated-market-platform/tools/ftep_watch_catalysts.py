"""Read-only FTEP catalyst watch (fixture dry-run; no locks or orders)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, TextIO

ROOT = Path(__file__).resolve().parents[1]


def emit_utf8_json(payload: dict[str, Any], stream: TextIO | None = None) -> None:
    """Always write UTF-8 JSON. Used for success and classified failure receipts."""

    text = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    out = stream if stream is not None else sys.stdout
    buffer = getattr(out, "buffer", None)
    if buffer is not None:
        buffer.write(text.encode("utf-8"))
        buffer.flush()
        return
    out.write(text)
    if hasattr(out, "flush"):
        out.flush()


def _exception_receipt(
    exc: BaseException,
    *,
    campaign_slug: str,
    live_ingress: bool,
) -> dict[str, Any]:
    from market_platform_foundation.intelligence.paper_forward_bridge.ftep_prospective_catalyst_ingress import (
        CLASS_HTTP_429,
        classify_finviz_fetch_exception,
    )

    classification, detail = classify_finviz_fetch_exception(exc)
    if classification == CLASS_HTTP_429:
        outcome = "LIVE_INGRESS_RATE_LIMITED"
        blocker = "FINVIZ_PROSPECTIVE_RATE_LIMITED"
        hint = (
            "Finviz returned HTTP 429. Do not immediately retry; wait and "
            "re-run a single --live-ingress command later."
        )
    else:
        outcome = "LIVE_INGRESS_FAILED"
        blocker = "FINVIZ_PROSPECTIVE_FETCH_FAILED"
        hint = "Finviz prospective watch failed before a provider receipt was composed."
    watch_mode = "PROSPECTIVE_FINVIZ_INGRESS" if live_ingress else "WATCH_EXCEPTION"
    return {
        "schema_version": "1.0.0",
        "artifact_kind": "ftep_catalyst_watch_report",
        "campaign_slug": campaign_slug,
        "dry_run": True,
        "test_mode": "SIGNAL_ONLY",
        "watch_mode": watch_mode,
        "disposition": "BLOCKED",
        "blockers": [blocker],
        "operator_hints": [hint],
        "prospective_ingress": {
            "attempted": bool(live_ingress),
            "ready": False,
            "classification": classification,
            "fetch_error": detail,
            "retry_attempted": False,
            "retry_count": 0,
            "test_mode": "SIGNAL_ONLY",
            "durable_lock": False,
        },
        "ingress_outcome": outcome,
        "ingress_classification": classification,
        "summary_count": 0,
        "summaries": [],
        "session_correlation": [],
        "secrets_included": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "campaign_slug",
        nargs="?",
        default="FTEP-V1-002",
        help="Forward-test campaign slug (default: FTEP-V1-002)",
    )
    parser.add_argument("--json", action="store_true", help="Machine-readable JSON")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Acknowledge read-only mode (no durable writes; default behavior)",
    )
    parser.add_argument(
        "--fixture",
        action="store_true",
        help="Force campaign attention fixture even when a governed session is active",
    )
    parser.add_argument(
        "--live-ingress",
        action="store_true",
        help=(
            "During active governed RTH sessions, ingest Finviz Elite news prospectively "
            "(requires IMP_FTEP_PROSPECTIVE_CATALYST_INGRESS=1 and IMP_FINVIZ_LIVE)"
        ),
    )
    parser.add_argument(
        "--input",
        type=Path,
        help="Optional JSON file with attention-candidate rows",
    )
    args = parser.parse_args(argv)

    src = ROOT / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))

    from market_platform_foundation.intelligence.paper_forward_bridge.ftep_catalyst_watch import (
        collect_ftep_catalyst_watch,
    )

    emit_json = bool(args.json or args.live_ingress)
    try:
        payload = collect_ftep_catalyst_watch(
            ROOT,
            args.campaign_slug,
            fixture_only=args.fixture,
            input_path=args.input,
            live_ingress=args.live_ingress,
        )
    except Exception as exc:
        payload = _exception_receipt(
            exc,
            campaign_slug=args.campaign_slug,
            live_ingress=args.live_ingress,
        )
        emit_utf8_json(payload)
        return 1

    classified = payload.get("ingress_classification") in {
        "HTTP_429",
        "TOKEN_ABSENT",
        "GATES_INACTIVE",
        "PROVIDER_FAILURE",
        "SUCCESS_EMPTY",
        "SUCCESS",
        "SECRET_DIR_MISSING",
        "SESSION_UNAVAILABLE",
        "TIMEOUT",
        "MALFORMED_RESPONSE",
    }
    if emit_json or classified:
        emit_utf8_json(payload)
    else:
        print(f"mode={payload['watch_mode']} disposition={payload['disposition']}")
        print(f"summaries={payload['summary_count']} sessions={payload['governed_session_ids']}")
    return 0 if payload["disposition"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
