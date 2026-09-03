"""End-to-end acceptance checks for the futures read-only integration lane."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.donor_bridge.futures_client import is_available  # noqa: E402
from market_platform_foundation.donor_bridge.futures_projections import (  # noqa: E402
    ADMITTED_FUTURES_INSTRUMENT_ID,
    build_explore_futures_payload,
)
from market_platform_foundation.normalization.equity_bars import iso_to_epoch_ns  # noqa: E402
from market_platform_foundation.features.institutional import configure_institutional_ledger  # noqa: E402
from market_platform_foundation.providers.projections import build_workspace_futures_payload  # noqa: E402
from market_platform_foundation.providers.whale_ledger import build_combined_fixture_ledger  # noqa: E402

DEFAULT_DONOR_URL = "http://127.0.0.1:8788"
DEFAULT_IMP_URL = "http://127.0.0.1:8766"
FIXTURE_CUTOFF = iso_to_epoch_ns("2025-06-02T14:41:07.000000000Z")


@dataclass(frozen=True, slots=True)
class AcceptanceCheck:
    check_id: str
    passed: bool
    message: str


@dataclass(frozen=True, slots=True)
class AcceptanceResult:
    checks: tuple[AcceptanceCheck, ...]
    summary: dict[str, Any]
    require_imp: bool = False

    @property
    def passed(self) -> bool:
        projection = [check for check in self.checks if not check.check_id.startswith("imp_")]
        if not all(check.passed for check in projection):
            return False
        if self.require_imp:
            http = [check for check in self.checks if check.check_id.startswith("imp_")]
            return all(check.passed for check in http)
        return True

    def public_dict(self) -> dict[str, Any]:
        return {
            "lane": "futures-read-only",
            "status": "PASS" if self.passed else "FAIL",
            "checks": [asdict(check) for check in self.checks],
            "summary": self.summary,
        }


def _check(
    checks: list[AcceptanceCheck],
    check_id: str,
    condition: bool,
    success: str,
    failure: str,
) -> None:
    checks.append(AcceptanceCheck(check_id, bool(condition), success if condition else failure))


def _request_json(base_url: str, path: str) -> tuple[int | None, dict[str, Any] | None]:
    url = base_url.rstrip("/") + path
    request = Request(url, method="GET")
    try:
        with urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
            if not isinstance(payload, dict):
                return response.status, None
            return response.status, payload
    except HTTPError as exc:
        return exc.code, None
    except (URLError, json.JSONDecodeError, TimeoutError):
        return None, None


def _projection_checks(*, donor_url: str, donor_live: bool) -> list[AcceptanceCheck]:
    checks: list[AcceptanceCheck] = []
    as_of = {"mode": "REPLAY"}
    ledger = build_combined_fixture_ledger()
    configure_institutional_ledger(ledger)

    offline = build_explore_futures_payload(as_of_context=as_of, base_url="http://127.0.0.1:59999")
    _check(
        checks,
        "projection_fail_closed",
        offline.get("available") is False and offline.get("symbol") == ADMITTED_FUTURES_INSTRUMENT_ID,
        "Explore projection is fail-closed when donor bridge is down.",
        "Explore projection did not fail closed when donor bridge is down.",
    )

    fixture_workspace = build_workspace_futures_payload(
        ADMITTED_FUTURES_INSTRUMENT_ID,
        as_of_context=as_of,
        prediction_cutoff=FIXTURE_CUTOFF,
    )
    _check(
        checks,
        "projection_workspace_fixture_fallback",
        fixture_workspace.get("available") is True,
        "ES workspace projection serves admitted fixture when donor bridge is down.",
        "ES workspace fixture fallback unavailable.",
    )

    if not donor_live:
        configure_institutional_ledger(None)
        return checks

    explore = build_explore_futures_payload(as_of_context=as_of, base_url=donor_url)
    _check(
        checks,
        "projection_explore_live",
        explore.get("available") is True and explore.get("symbol") == ADMITTED_FUTURES_INSTRUMENT_ID,
        "Explore projection is available when FuturesX bridge is live.",
        "Explore projection unavailable or wrong symbol when donor is live.",
    )
    _check(
        checks,
        "projection_explore_bridge_url",
        bool(explore.get("bridge_url")),
        "Explore projection includes bridge URL metadata.",
        "Explore projection missing bridge URL metadata.",
    )

    donor_workspace = build_workspace_futures_payload(
        ADMITTED_FUTURES_INSTRUMENT_ID,
        as_of_context=as_of,
        prediction_cutoff=FIXTURE_CUTOFF,
    )
    _check(
        checks,
        "projection_workspace_donor_overlay",
        donor_workspace.get("available") is True
        and donor_workspace.get("provenance") == "donor_bridge",
        "ES workspace projection overlays donor bridge when :8788 is live.",
        "ES workspace donor overlay missing when bridge is live.",
    )
    configure_institutional_ledger(None)
    return checks


def _http_checks(*, imp_url: str, donor_live: bool) -> list[AcceptanceCheck]:
    checks: list[AcceptanceCheck] = []
    symbol = ADMITTED_FUTURES_INSTRUMENT_ID
    explain_ref = f"explain:futures:{symbol}"

    status, explore = _request_json(imp_url, "/explore/futures")
    _check(
        checks,
        "imp_explore_http",
        status == 200 and isinstance(explore, dict),
        "IMP /explore/futures responds over HTTP.",
        "IMP /explore/futures HTTP request failed.",
    )
    if not isinstance(explore, dict):
        return checks

    if donor_live:
        _check(
            checks,
            "imp_explore_available",
            explore.get("available") is True and explore.get("symbol") == symbol,
            "IMP explore futures bridge is available when donor is live.",
            "IMP explore futures bridge availability mismatch.",
        )
    else:
        _check(
            checks,
            "imp_explore_unavailable",
            explore.get("available") is False,
            "IMP explore futures bridge is fail-closed when donor is down.",
            "IMP explore futures bridge reported available without donor.",
        )

    status, workspace = _request_json(imp_url, f"/workspace/{symbol}/futures")
    _check(
        checks,
        "imp_workspace_futures_http",
        status == 200 and isinstance(workspace, dict) and workspace.get("available") is True,
        f"IMP workspace futures endpoint serves {symbol} detail.",
        f"IMP workspace futures endpoint failed for {symbol}.",
    )
    if donor_live and isinstance(workspace, dict):
        _check(
            checks,
            "imp_workspace_donor_overlay",
            workspace.get("provenance") == "donor_bridge",
            "IMP workspace futures shows donor_bridge provenance when bridge is live.",
            "IMP workspace futures missing donor_bridge provenance.",
        )

    explain_status, explain = _request_json(imp_url, f"/explain/{explain_ref}")
    _check(
        checks,
        "imp_explain_futures",
        explain_status == 200 and isinstance(explain, dict) and explain.get("explanation"),
        "IMP explain endpoint resolves futures refs.",
        "IMP explain endpoint failed for futures ref.",
    )

    status, attention = _request_json(imp_url, "/attention")
    futures_items = []
    if isinstance(attention, dict):
        items = attention.get("items", [])
        if isinstance(items, list):
            futures_items = [
                item for item in items if str(item.get("attention_id", "")).startswith("att-futures-")
            ]
    _check(
        checks,
        "imp_attention_futures",
        status == 200 and len(futures_items) >= 1,
        "IMP attention feed includes futures items when ES workspace is available.",
        "IMP attention feed missing futures items.",
    )
    return checks


def run_acceptance(
    *,
    donor_url: str = DEFAULT_DONOR_URL,
    imp_url: str = DEFAULT_IMP_URL,
    require_donor: bool = False,
    require_imp: bool = False,
) -> AcceptanceResult:
    donor_live = is_available(base_url=donor_url)
    imp_status, _ = _request_json(imp_url, "/context")
    imp_live = imp_status == 200

    summary: dict[str, Any] = {
        "donor_url": donor_url,
        "imp_url": imp_url,
        "donor_live": donor_live,
        "imp_live": imp_live,
        "symbol": ADMITTED_FUTURES_INSTRUMENT_ID,
    }

    checks: list[AcceptanceCheck] = []
    if require_donor and not donor_live:
        _check(
            checks,
            "donor_required",
            False,
            "",
            "FuturesX donor bridge is required but not reachable on :8788.",
        )
    if require_imp and not imp_live:
        _check(
            checks,
            "imp_required",
            False,
            "",
            "IMP UI API is required but not reachable.",
        )

    checks.extend(_projection_checks(donor_url=donor_url, donor_live=donor_live))
    http_checks: list[AcceptanceCheck] = []
    if imp_live:
        http_checks = _http_checks(imp_url=imp_url, donor_live=donor_live)
        checks.extend(http_checks)
    elif require_imp:
        _check(
            checks,
            "imp_http",
            False,
            "",
            "IMP UI API HTTP checks skipped because server is down.",
        )

    projection_passed = all(check.passed for check in checks if not check.check_id.startswith("imp_"))
    http_passed = all(check.passed for check in http_checks) if http_checks else True
    summary["projection_status"] = "PASS" if projection_passed else "FAIL"
    summary["http_status"] = "PASS" if http_passed else ("SKIP" if not http_checks else "FAIL")

    return AcceptanceResult(tuple(checks), summary, require_imp=require_imp)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--donor-url", default=DEFAULT_DONOR_URL)
    parser.add_argument("--imp-url", default=DEFAULT_IMP_URL)
    parser.add_argument("--require-donor", action="store_true")
    parser.add_argument("--require-imp", action="store_true")
    parser.add_argument("--output", type=Path, help="Write canonical JSON evidence to this path.")
    args = parser.parse_args()

    result = run_acceptance(
        donor_url=args.donor_url,
        imp_url=args.imp_url,
        require_donor=args.require_donor,
        require_imp=args.require_imp,
    )
    payload = result.public_dict()
    rendered = json.dumps(payload, sort_keys=True, indent=2)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
