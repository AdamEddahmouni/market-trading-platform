"""End-to-end acceptance checks for the short-squeeze read-only integration lane."""

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

from market_platform_foundation.donor_bridge.projections import (  # noqa: E402
    ADMITTED_REPLAY_INSTRUMENT_ID,
    FROZEN_DEMO_REFERENCE_SYMBOL,
    build_explore_squeeze_payload,
    build_explore_squeeze_scanner_payload,
    build_squeeze_attention_items,
    build_squeeze_scanner_attention_items,
    build_workspace_squeeze_payload,
)
from market_platform_foundation.donor_bridge.squeeze_client import (  # noqa: E402
    fetch_donor_deployment_mode,
    is_available,
)

DEFAULT_DONOR_URL = "http://127.0.0.1:8787"
DEFAULT_IMP_URL = "http://127.0.0.1:8766"
FROZEN_ROW_COUNT = 13


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
            "lane": "short-squeeze-read-only",
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
        with urlopen(request, timeout=180) as response:
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

    offline = build_explore_squeeze_payload(base_url="http://127.0.0.1:59999")
    _check(
        checks,
        "projection_fail_closed",
        offline.get("available") is False and offline.get("rows") == [],
        "Explore projection is fail-closed when donor is down.",
        "Explore projection did not fail closed when donor is down.",
    )

    offline_scanner = build_explore_squeeze_scanner_payload(base_url="http://127.0.0.1:59999")
    _check(
        checks,
        "projection_scanner_fail_closed",
        offline_scanner.get("available") is False and offline_scanner.get("rows") == [],
        "Scanner explore projection is fail-closed when donor is down.",
        "Scanner explore projection did not fail closed when donor is down.",
    )

    if not donor_live:
        return checks

    explore = build_explore_squeeze_payload(base_url=donor_url)
    _check(
        checks,
        "projection_explore_rows",
        explore.get("available") is True and explore.get("row_count") == FROZEN_ROW_COUNT,
        f"Explore projection returns {FROZEN_ROW_COUNT} frozen rows.",
        "Explore projection row count or availability mismatch.",
    )
    _check(
        checks,
        "projection_manifest",
        isinstance(explore.get("manifest"), dict)
        and bool(explore["manifest"].get("api_version"))
        and bool(explore["manifest"].get("schema_version")),
        "Explore projection includes donor manifest metadata.",
        "Explore projection missing manifest metadata.",
    )

    biya = build_workspace_squeeze_payload(ADMITTED_REPLAY_INSTRUMENT_ID, base_url=donor_url)
    _check(
        checks,
        "projection_workspace_replay_only",
        biya.get("replay_chart_available") is True and biya.get("available") is False,
        "BIYA keeps replay chart while donor squeeze evidence stays unavailable.",
        "BIYA replay/squeeze boundary mismatch.",
    )

    squeeze_symbol = FROZEN_DEMO_REFERENCE_SYMBOL
    squeeze = build_workspace_squeeze_payload(squeeze_symbol, base_url=donor_url)
    _check(
        checks,
        "projection_workspace_squeeze",
        squeeze.get("available") is True and squeeze.get("replay_chart_available") is False,
        f"{squeeze_symbol} workspace projection serves squeeze evidence without replay chart.",
        f"{squeeze_symbol} workspace projection missing squeeze evidence.",
    )
    _check(
        checks,
        "projection_workspace_rules",
        isinstance(squeeze.get("rules"), list)
        and len(squeeze.get("rules", [])) > 0
        and len(squeeze.get("ignition_evidence", [])) >= 3,
        f"{squeeze_symbol} workspace projection includes rules and ignition evidence cards.",
        f"{squeeze_symbol} workspace projection missing rules or ignition evidence.",
    )

    avtx = build_workspace_squeeze_payload("AVTX", base_url=donor_url)
    _check(
        checks,
        "projection_workspace_non_admitted",
        avtx.get("available") is True and avtx.get("replay_chart_available") is False,
        "Non-admitted symbol keeps replay chart unavailable.",
        "Non-admitted symbol incorrectly marked replay-available.",
    )

    attention = build_squeeze_attention_items(base_url=donor_url, limit=5)
    _check(
        checks,
        "projection_attention_items",
        len(attention) == 5 and all(item.get("explanation_ref", "").startswith("explain:squeeze:") for item in attention),
        "Attention projection surfaces five squeeze items with explain refs.",
        "Attention projection missing squeeze items or explain refs.",
    )

    scanner_explore = build_explore_squeeze_scanner_payload(base_url=donor_url)
    scanner_row_count = int(scanner_explore.get("row_count") or 0)
    _check(
        checks,
        "projection_scanner_explore",
        scanner_explore.get("available") is True and scanner_explore.get("data_mode") == "current",
        "Scanner explore projection is available in current data mode.",
        "Scanner explore projection unavailable or wrong data mode.",
    )
    scanner_attention = build_squeeze_scanner_attention_items(base_url=donor_url, limit=3)
    if scanner_row_count > 0:
        _check(
            checks,
            "projection_scanner_rows",
            scanner_row_count >= 1 and len(scanner_explore.get("rows", [])) >= 1,
            f"Scanner explore projection returns {scanner_row_count} current row(s).",
            "Scanner explore projection missing current rows.",
        )
        _check(
            checks,
            "projection_scanner_attention_items",
            len(scanner_attention) >= 1
            and all(
                str(item.get("attention_id", "")).startswith("att-squeeze-scanner-")
                for item in scanner_attention
            )
            and all(
                str(item.get("explanation_ref", "")).startswith("explain:squeeze:scanner:")
                for item in scanner_attention
            ),
            "Scanner attention projection surfaces ephemeral rows with scanner explain refs.",
            "Scanner attention projection missing items or explain refs.",
        )
        scanner_symbol = str(scanner_explore["rows"][0].get("symbol", "")).upper()
        if scanner_symbol:
            current_workspace = build_workspace_squeeze_payload(
                scanner_symbol,
                base_url=donor_url,
                data_mode="current",
            )
            _check(
                checks,
                "projection_workspace_current",
                current_workspace.get("available") is True
                and current_workspace.get("data_mode") == "current",
                f"{scanner_symbol} workspace current-mode projection serves scanner detail.",
                f"{scanner_symbol} workspace current-mode projection unavailable.",
            )
    else:
        _check(
            checks,
            "projection_scanner_attention_empty",
            scanner_attention == [],
            "Scanner attention projection stays empty when no current candidates.",
            "Scanner attention projection returned items without scanner rows.",
        )
    return checks


def _http_checks(*, imp_url: str, donor_live: bool) -> list[AcceptanceCheck]:
    checks: list[AcceptanceCheck] = []
    status, explore = _request_json(imp_url, "/explore/squeeze")
    _check(
        checks,
        "imp_explore_http",
        status == 200 and isinstance(explore, dict),
        "IMP /explore/squeeze responds over HTTP.",
        "IMP /explore/squeeze HTTP request failed.",
    )
    if not isinstance(explore, dict):
        return checks

    if donor_live:
        _check(
            checks,
            "imp_explore_available",
            explore.get("available") is True and explore.get("row_count") == FROZEN_ROW_COUNT,
            "IMP explore bridge returns 13 rows when donor is live.",
            "IMP explore bridge availability or row count mismatch.",
        )
    else:
        _check(
            checks,
            "imp_explore_unavailable",
            explore.get("available") is False,
            "IMP explore bridge is fail-closed when donor is down.",
            "IMP explore bridge reported available without donor.",
        )
        return checks

    status, squeeze = _request_json(imp_url, f"/workspace/{FROZEN_DEMO_REFERENCE_SYMBOL}/squeeze")
    _check(
        checks,
        "imp_workspace_squeeze_http",
        status == 200
        and isinstance(squeeze, dict)
        and squeeze.get("available") is True
        and squeeze.get("replay_chart_available") is False,
        f"IMP workspace squeeze endpoint serves {FROZEN_DEMO_REFERENCE_SYMBOL} detail.",
        f"IMP workspace squeeze endpoint failed for {FROZEN_DEMO_REFERENCE_SYMBOL}.",
    )

    status, biya = _request_json(imp_url, f"/workspace/{ADMITTED_REPLAY_INSTRUMENT_ID}/squeeze")
    _check(
        checks,
        "imp_workspace_replay_only_http",
        status == 200
        and isinstance(biya, dict)
        and biya.get("replay_chart_available") is True
        and biya.get("available") is False,
        "IMP workspace keeps BIYA replay-only when donor has no frozen case.",
        "IMP workspace BIYA replay/squeeze boundary mismatch.",
    )

    status, attention = _request_json(imp_url, "/attention")
    squeeze_items = []
    if isinstance(attention, dict):
        items = attention.get("items", [])
        if isinstance(items, list):
            squeeze_items = [item for item in items if str(item.get("attention_id", "")).startswith("att-squeeze-")]
    _check(
        checks,
        "imp_attention_squeeze",
        status == 200 and len(squeeze_items) >= 1,
        "IMP attention feed includes squeeze items when donor is live.",
        "IMP attention feed missing squeeze items.",
    )

    status, scanner_explore = _request_json(imp_url, "/explore/squeeze/scanner")
    _check(
        checks,
        "imp_scanner_explore_http",
        status == 200 and isinstance(scanner_explore, dict),
        "IMP /explore/squeeze/scanner responds over HTTP.",
        "IMP /explore/squeeze/scanner HTTP request failed.",
    )
    if isinstance(scanner_explore, dict):
        scanner_row_count = int(scanner_explore.get("row_count") or 0)
        _check(
            checks,
            "imp_scanner_explore_available",
            scanner_explore.get("available") is True and scanner_explore.get("data_mode") == "current",
            "IMP scanner explore bridge is available in current data mode.",
            "IMP scanner explore bridge unavailable or wrong data mode.",
        )
        if scanner_row_count > 0:
            scanner_rows = scanner_explore.get("rows", [])
            scanner_symbol = ""
            if isinstance(scanner_rows, list) and scanner_rows:
                scanner_symbol = str(scanner_rows[0].get("symbol", "")).upper()
            _check(
                checks,
                "imp_scanner_explore_rows",
                scanner_row_count >= 1,
                f"IMP scanner explore bridge returns {scanner_row_count} current row(s).",
                "IMP scanner explore bridge missing current rows.",
            )
            if scanner_symbol:
                ws_status, current_workspace = _request_json(
                    imp_url,
                    f"/workspace/{scanner_symbol}/squeeze?data_mode=current",
                )
                _check(
                    checks,
                    "imp_workspace_scanner_http",
                    ws_status == 200
                    and isinstance(current_workspace, dict)
                    and current_workspace.get("available") is True
                    and current_workspace.get("data_mode") == "current",
                    f"IMP workspace current-mode squeeze serves {scanner_symbol} scanner detail.",
                    f"IMP workspace current-mode squeeze failed for {scanner_symbol}.",
                )

    if squeeze_items:
        ref = str(squeeze_items[0].get("explanation_ref", ""))
        explain_status, explain = _request_json(imp_url, f"/explain/{ref}")
        _check(
            checks,
            "imp_explain_squeeze",
            explain_status == 200 and isinstance(explain, dict) and explain.get("explanation"),
            "IMP explain endpoint resolves squeeze attention refs.",
            "IMP explain endpoint failed for squeeze ref.",
        )

    scanner_items = []
    if isinstance(attention, dict):
        items = attention.get("items", [])
        if isinstance(items, list):
            scanner_items = [
                item for item in items if str(item.get("attention_id", "")).startswith("att-squeeze-scanner-")
            ]
    if scanner_items:
        scanner_ref = str(scanner_items[0].get("explanation_ref", ""))
        scanner_explain_status, scanner_explain = _request_json(imp_url, f"/explain/{scanner_ref}")
        _check(
            checks,
            "imp_explain_squeeze_scanner",
            scanner_explain_status == 200
            and isinstance(scanner_explain, dict)
            and scanner_explain.get("explanation"),
            "IMP explain endpoint resolves scanner squeeze attention refs.",
            "IMP explain endpoint failed for scanner squeeze ref.",
        )
    return checks


def run_acceptance(
    *,
    donor_url: str = DEFAULT_DONOR_URL,
    imp_url: str = DEFAULT_IMP_URL,
    require_donor: bool = False,
    require_imp: bool = False,
    require_scanner_rows: bool = False,
) -> AcceptanceResult:
    donor_live = is_available(base_url=donor_url)
    donor_mode = fetch_donor_deployment_mode(base_url=donor_url) if donor_live else None
    imp_status, _ = _request_json(imp_url, "/context")
    imp_live = imp_status == 200

    summary: dict[str, Any] = {
        "donor_url": donor_url,
        "imp_url": imp_url,
        "donor_live": donor_live,
        "donor_mode": donor_mode,
        "imp_live": imp_live,
        "frozen_row_count": FROZEN_ROW_COUNT,
    }

    checks: list[AcceptanceCheck] = []
    if require_donor and not donor_live:
        _check(
            checks,
            "donor_required",
            False,
            "",
            "Donor FROZEN_DEMO server is required but not reachable.",
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

    if donor_live:
        scanner_explore = build_explore_squeeze_scanner_payload(base_url=donor_url)
        summary["scanner_row_count"] = int(scanner_explore.get("row_count") or 0)
    if require_scanner_rows and donor_live:
        scanner_count = int(summary.get("scanner_row_count") or 0)
        _check(
            checks,
            "scanner_rows_required",
            scanner_count > 0,
            f"Live scanner returned {scanner_count} current row(s).",
            "Live scanner rows required but donor returned zero current candidates.",
        )

    projection_passed = all(check.passed for check in checks if not check.check_id.startswith("imp_"))
    http_passed = all(check.passed for check in http_checks) if http_checks else True
    summary["projection_status"] = "PASS" if projection_passed else "FAIL"
    summary["http_status"] = "PASS" if http_passed else ("SKIP" if not http_checks else "FAIL")
    if http_checks and not http_passed:
        summary["http_hint"] = "Restart IMP UI API if workspace squeeze routes return 404."

    return AcceptanceResult(tuple(checks), summary, require_imp=require_imp)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--donor-url", default=DEFAULT_DONOR_URL)
    parser.add_argument("--imp-url", default=DEFAULT_IMP_URL)
    parser.add_argument("--require-donor", action="store_true")
    parser.add_argument("--require-imp", action="store_true")
    parser.add_argument(
        "--require-scanner-rows",
        action="store_true",
        help="Fail when donor is live but /api/current/candidates returns zero rows.",
    )
    parser.add_argument("--output", type=Path, help="Write canonical JSON evidence to this path.")
    args = parser.parse_args()

    result = run_acceptance(
        donor_url=args.donor_url,
        imp_url=args.imp_url,
        require_donor=args.require_donor,
        require_imp=args.require_imp,
        require_scanner_rows=args.require_scanner_rows,
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
