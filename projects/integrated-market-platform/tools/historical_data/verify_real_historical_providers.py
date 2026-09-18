"""IMP-RESEARCH-VALIDATION-04 Lane B — bounded real historical provider verification."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from market_platform_foundation.market_data.historical_development.real_provider_verification import (  # noqa: E402
    DEFAULT_INSTRUMENTS,
    DEFAULT_SESSION_COUNT,
    IbkrHistoricalTradesVerification,
    OPTIONAL_EXPANSION_INSTRUMENTS,
    build_verification_receipt,
    evaluate_ibkr_historical_trades_gate,
    probe_ibkr_tws_loopback,
    verify_moomoo_real_historical,
)
from market_platform_foundation.paper.calibration.bar_ohlcv_prospective_proof import (  # noqa: E402
    resolve_runtime_git_sha,
)


def _parse_holidays(raw: str) -> frozenset[str]:
    return frozenset(filter(None, str(raw).split(",")))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "evidence" / "market_data" / "lane_b" / "real-historical-provider-verification.json",
    )
    parser.add_argument("--session-count", type=int, default=DEFAULT_SESSION_COUNT)
    parser.add_argument("--end-before", type=date.fromisoformat, default=date.today())
    parser.add_argument("--holidays", default="")
    parser.add_argument("--early-closes", default="")
    parser.add_argument(
        "--artifact-root",
        type=Path,
        default=ROOT / "artifacts" / "historical-rth-development-real-provider-verification",
    )
    parser.add_argument(
        "--expand-instruments",
        action="store_true",
        help="After AAPL verifies, also fetch MSFT and SPY with the same frozen config.",
    )
    parser.add_argument("--skip-rerun", action="store_true")
    parser.add_argument("--skip-ibkr-cli", action="store_true")
    args = parser.parse_args(argv)

    holidays = _parse_holidays(args.holidays)
    early_closes = _parse_holidays(args.early_closes)
    instruments = list(DEFAULT_INSTRUMENTS)
    moomoo = verify_moomoo_real_historical(
        repository_root=ROOT,
        artifact_root=args.artifact_root,
        instruments=instruments,
        session_count=args.session_count,
        end_before=args.end_before,
        holidays=holidays,
        early_closes=early_closes,
        perform_rerun_check=not args.skip_rerun,
    )
    expansion_report: dict[str, object] | None = None
    if args.expand_instruments and moomoo.status == "VERIFIED_BOUNDED":
        expanded = verify_moomoo_real_historical(
            repository_root=ROOT,
            artifact_root=args.artifact_root / "expansion",
            instruments=OPTIONAL_EXPANSION_INSTRUMENTS,
            session_count=args.session_count,
            end_before=args.end_before,
            holidays=holidays,
            early_closes=early_closes,
            perform_rerun_check=False,
        )
        expansion_report = expanded.as_report_fields()

    live = os.environ.get("IMP_IBKR_LIVE", "").strip() == "1"
    transport = os.environ.get("IMP_IBKR_TRANSPORT", "rest").strip().lower()
    host = os.environ.get("IMP_IBKR_TWS_HOST", "127.0.0.1").strip()
    try:
        port = int(os.environ.get("IMP_IBKR_TWS_PORT", "4001"))
    except ValueError:
        port = 0
    tws_reachable = probe_ibkr_tws_loopback(host=host, port=port)
    ibkr = evaluate_ibkr_historical_trades_gate(
        live_enabled=live,
        transport=transport,
        tws_reachable=tws_reachable,
    )

    ibkr_receipt_path = ROOT / "evidence" / "market_data" / "ibkr" / "historical-trades-verification.json"
    if not args.skip_ibkr_cli:
        ibkr_receipt_path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [sys.executable, str(ROOT / "tools" / "ibkr" / "verify_historical_trades_provider.py"), "--output", str(ibkr_receipt_path)],
            cwd=str(ROOT),
            check=False,
        )
        if ibkr_receipt_path.is_file():
            payload = json.loads(ibkr_receipt_path.read_text(encoding="utf-8"))
            limitations = list(ibkr.limitations)
            reason_text = str(payload.get("reason") or "")
            if reason_text and reason_text not in limitations:
                limitations.append(reason_text)
            provenance = payload.get("provenance") if isinstance(payload.get("provenance"), dict) else {}
            ibkr = IbkrHistoricalTradesVerification(
                status=str(payload.get("status") or ibkr.status),
                interval={
                    "symbol": payload.get("symbol"),
                    "accepted": payload.get("accepted"),
                }
                if payload.get("symbol")
                else None,
                trade_count=int(payload.get("trade_count") or 0),
                pagination={
                    "transport": payload.get("transport"),
                    "provenance_page_count": provenance.get("page_count"),
                },
                complete=payload.get("complete") if "complete" in payload else ibkr.complete,
                limitations=tuple(limitations),
                reason=reason_text or ibkr.reason,
            )

    receipt = build_verification_receipt(
        increment_id="IMP-RESEARCH-VALIDATION-04",
        moomoo=moomoo,
        ibkr=ibkr,
        code_sha=resolve_runtime_git_sha(start=ROOT),
    )
    if expansion_report is not None:
        receipt["moomoo_expansion"] = expansion_report
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
