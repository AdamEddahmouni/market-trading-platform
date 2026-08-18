"""End-to-end acceptance checks for the catalyst read-only integration lane."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.donor_bridge import internship_client  # noqa: E402
from market_platform_foundation.donor_bridge.projections import (  # noqa: E402
    build_catalyst_attention_items,
    build_explore_catalyst_payload,
    build_workspace_catalyst_payload,
)
from market_platform_foundation.normalization.equity_bars import iso_to_epoch_ns  # noqa: E402
from market_platform_foundation.features.institutional import configure_institutional_ledger  # noqa: E402
from market_platform_foundation.providers.projections import build_workspace_catalyst_payload as build_fixture_catalyst  # noqa: E402
from market_platform_foundation.providers.whale_ledger import build_combined_fixture_ledger  # noqa: E402

DEFAULT_IMP_URL = "http://127.0.0.1:8766"
REFERENCE_SYMBOL = "BOXL"
FIXTURE_CUTOFF = iso_to_epoch_ns("2026-07-22T00:00:00.000000000Z")
SEED_INSTRUCTION = (
    "Run: python scripts/seed_demo_state.py in "
    "internship-project-main/internship-project-main/news_momentum_agent/"
)


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
            "lane": "catalyst-read-only",
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


def _state_live(state_dir: Path | None = None) -> bool:
    return internship_client.is_available(state_dir=state_dir)


def _projection_checks(*, state_dir: Path | None, state_live: bool) -> list[AcceptanceCheck]:
    checks: list[AcceptanceCheck] = []
    as_of = {"mode": "REPLAY"}
    ledger = build_combined_fixture_ledger()
    configure_institutional_ledger(ledger)

    with tempfile.TemporaryDirectory() as tmp:
        offline = build_explore_catalyst_payload(state_dir=Path(tmp), as_of_context=as_of)
        _check(
            checks,
            "projection_fail_closed",
            offline.get("available") is False and offline.get("rows") == [],
            "Explore projection is fail-closed when internship demo state is missing.",
            "Explore projection did not fail closed when demo state is missing.",
        )

    fixture_workspace = build_fixture_catalyst(
        REFERENCE_SYMBOL,
        as_of_context=as_of,
        prediction_cutoff=FIXTURE_CUTOFF,
    )
    _check(
        checks,
        "projection_workspace_fixture_fallback",
        fixture_workspace.get("available") is True,
        f"{REFERENCE_SYMBOL} workspace projection serves admitted fixture.",
        f"{REFERENCE_SYMBOL} workspace fixture fallback unavailable.",
    )

    if not state_live:
        _check(
            checks,
            "state_seed_prereq",
            True,
            f"Demo state not seeded; {SEED_INSTRUCTION}",
            "",
        )
        configure_institutional_ledger(None)
        return checks

    explore = build_explore_catalyst_payload(state_dir=state_dir, as_of_context=as_of)
    symbols = {str(row.get("symbol", "")).upper() for row in explore.get("rows", [])}
    _check(
        checks,
        "projection_explore_rows",
        explore.get("available") is True and int(explore.get("row_count") or 0) > 0,
        f"Explore projection returns {explore.get('row_count')} catalyst row(s).",
        "Explore projection row count or availability mismatch.",
    )
    _check(
        checks,
        "projection_reference_symbol",
        REFERENCE_SYMBOL in symbols,
        f"Explore projection includes {REFERENCE_SYMBOL}.",
        f"Explore projection missing {REFERENCE_SYMBOL}.",
    )
    _check(
        checks,
        "projection_decision_summary",
        isinstance(explore.get("decision_summary"), list) and len(explore.get("decision_summary", [])) > 0,
        "Explore projection includes decision_summary aggregation.",
        "Explore projection missing decision_summary.",
    )

    bridge_workspace = build_workspace_catalyst_payload(REFERENCE_SYMBOL, state_dir=state_dir)
    _check(
        checks,
        "projection_workspace_catalyst",
        bridge_workspace.get("available") is True,
        f"{REFERENCE_SYMBOL} donor workspace projection serves catalyst evidence.",
        f"{REFERENCE_SYMBOL} donor workspace projection unavailable.",
    )

    attention = build_catalyst_attention_items(state_dir=state_dir, limit=5)
    _check(
        checks,
        "projection_attention_items",
        len(attention) >= 1
        and all(str(item.get("explanation_ref", "")).startswith("explain:catalyst:") for item in attention),
        "Attention projection surfaces catalyst items with explain refs.",
        "Attention projection missing catalyst items or explain refs.",
    )
    configure_institutional_ledger(None)
    return checks


def _http_checks(*, imp_url: str, state_live: bool) -> list[AcceptanceCheck]:
    checks: list[AcceptanceCheck] = []
    explain_ref = f"explain:catalyst:{REFERENCE_SYMBOL}"

    status, explore = _request_json(imp_url, "/explore/catalyst")
    _check(
        checks,
        "imp_explore_http",
        status == 200 and isinstance(explore, dict),
        "IMP /explore/catalyst responds over HTTP.",
        "IMP /explore/catalyst HTTP request failed.",
    )
    if isinstance(explore, dict):
        if state_live:
            _check(
                checks,
                "imp_explore_available",
                explore.get("available") is True and int(explore.get("row_count") or 0) > 0,
                "IMP explore catalyst bridge returns rows when demo state is seeded.",
                "IMP explore catalyst bridge availability or row count mismatch.",
            )
        else:
            _check(
                checks,
                "imp_explore_unavailable",
                explore.get("available") is False,
                "IMP explore catalyst bridge is fail-closed when demo state is missing.",
                "IMP explore catalyst bridge reported available without seeded state.",
            )

    status, workspace = _request_json(imp_url, f"/workspace/{REFERENCE_SYMBOL}/catalyst")
    _check(
        checks,
        "imp_workspace_catalyst_http",
        status == 200 and isinstance(workspace, dict) and workspace.get("available") is True,
        f"IMP workspace catalyst endpoint serves {REFERENCE_SYMBOL} detail.",
        f"IMP workspace catalyst endpoint failed for {REFERENCE_SYMBOL}.",
    )

    explain_status, explain = _request_json(imp_url, f"/explain/{explain_ref}")
    _check(
        checks,
        "imp_explain_catalyst",
        explain_status == 200 and isinstance(explain, dict) and explain.get("explanation"),
        "IMP explain endpoint resolves catalyst refs.",
        "IMP explain endpoint failed for catalyst ref.",
    )

    status, attention = _request_json(imp_url, "/attention")
    catalyst_items = []
    if isinstance(attention, dict):
        items = attention.get("items", [])
        if isinstance(items, list):
            catalyst_items = [
                item for item in items if str(item.get("attention_id", "")).startswith("att-catalyst-")
            ]
    _check(
        checks,
        "imp_attention_catalyst",
        status == 200 and (len(catalyst_items) >= 1 if state_live else True),
        "IMP attention feed includes catalyst items when demo state is seeded.",
        "IMP attention feed missing catalyst items.",
    )
    return checks


def run_acceptance(
    *,
    imp_url: str = DEFAULT_IMP_URL,
    state_dir: Path | None = None,
    require_state: bool = False,
    require_imp: bool = False,
) -> AcceptanceResult:
    resolved_state_dir = state_dir or internship_client.default_state_dir()
    state_live = _state_live(state_dir=resolved_state_dir)
    imp_status, _ = _request_json(imp_url, "/context")
    imp_live = imp_status == 200

    summary: dict[str, Any] = {
        "imp_url": imp_url,
        "state_dir": str(resolved_state_dir),
        "state_live": state_live,
        "imp_live": imp_live,
        "reference_symbol": REFERENCE_SYMBOL,
        "seed_instruction": SEED_INSTRUCTION,
    }

    checks: list[AcceptanceCheck] = []
    if require_state and not state_live:
        _check(
            checks,
            "state_required",
            False,
            "",
            f"Internship demo state is required but not seeded. {SEED_INSTRUCTION}",
        )
    if require_imp and not imp_live:
        _check(
            checks,
            "imp_required",
            False,
            "",
            "IMP UI API is required but not reachable.",
        )

    checks.extend(_projection_checks(state_dir=resolved_state_dir, state_live=state_live))
    http_checks: list[AcceptanceCheck] = []
    if imp_live:
        http_checks = _http_checks(imp_url=imp_url, state_live=state_live)
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
    parser.add_argument("--imp-url", default=DEFAULT_IMP_URL)
    parser.add_argument("--state-dir", type=Path, help="Override internship demo state directory.")
    parser.add_argument("--require-state", action="store_true")
    parser.add_argument("--require-imp", action="store_true")
    parser.add_argument("--output", type=Path, help="Write canonical JSON evidence to this path.")
    args = parser.parse_args()

    result = run_acceptance(
        imp_url=args.imp_url,
        state_dir=args.state_dir,
        require_state=args.require_state,
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
