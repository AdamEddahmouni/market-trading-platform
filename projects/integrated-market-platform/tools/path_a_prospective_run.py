"""One-shot Paper/Demo Path A prospective runner. Never submits Live orders."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.strategy.path_a_prospective import (
    PathAProspectiveComposer,
    build_paper_demo_path_a_invoke,
)
from market_platform_foundation.providers.equity_quote_discovery import discover_equity_quote_stack


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="One-shot Path A prospective hop (Paper/Demo).")
    parser.add_argument("--symbol", default="AAPL")
    parser.add_argument("--mode", default="paper", choices=("paper", "demo"))
    args = parser.parse_args(argv)
    provider, discovery = discover_equity_quote_stack()
    invoke = build_paper_demo_path_a_invoke(args.symbol, mode=args.mode)
    result = PathAProspectiveComposer(
        quote_provider=provider,
        path_a_caller=invoke.caller,
    ).run(args.symbol, mode=args.mode, scan_request=invoke.scan_request)
    payload = {
        "discovery": {
            "classification": discovery.classification,
            "config_names_present": list(discovery.config_names_present),
            "finviz_token_names_present": list(discovery.finviz_token_names_present),
            "opend_reachable": discovery.opend_reachable,
            "provider_id": discovery.provider_id,
            "reason_code": discovery.reason_code,
            "timeliness": discovery.timeliness,
        },
        "result": result.to_dict(),
    }
    json.dump(payload, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0 if result.status not in {"LIVE_FORBIDDEN"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
