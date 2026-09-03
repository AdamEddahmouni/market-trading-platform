"""Live CLOUD_PROVIDER_MODE scanner soak for the squeeze integration lane."""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.donor_bridge.squeeze_client import (  # noqa: E402
    fetch_donor_deployment_mode,
    is_available,
)

DEFAULT_DONOR_URL = "http://127.0.0.1:8787"
DEFAULT_IMP_URL = "http://127.0.0.1:8766"
DEFAULT_OUTPUT = ROOT / "evidence" / "integration" / "squeeze-cloud-soak.json"


@dataclass(frozen=True, slots=True)
class SoakSample:
    iteration: int
    donor_mode: str | None
    donor_row_count: int
    donor_evaluable_count: int
    donor_stale_count: int
    donor_adam_classes: dict[str, int]
    imp_scanner_available: bool
    imp_scanner_row_count: int
    imp_explore_available: bool
    imp_explore_row_count: int
    refresh_triggered: bool
    refresh_errors: int
    notes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SoakReport:
    started_at: str
    finished_at: str
    donor_url: str
    imp_url: str
    iterations: int
    interval_seconds: float
    trigger_refresh: bool
    samples: tuple[SoakSample, ...]
    summary: dict[str, Any]

    def public_dict(self) -> dict[str, Any]:
        return {
            "lane": "short-squeeze-cloud-soak",
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "donor_url": self.donor_url,
            "imp_url": self.imp_url,
            "iterations": self.iterations,
            "interval_seconds": self.interval_seconds,
            "trigger_refresh": self.trigger_refresh,
            "samples": [asdict(sample) for sample in self.samples],
            "summary": self.summary,
        }


def _request_json(url: str, *, method: str = "GET", timeout: float = 180.0) -> dict[str, Any]:
    request = Request(url, method=method)
    with urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected object JSON from {url}")
    return payload


def _finviz_provider_detail(donor_url: str) -> str | None:
    try:
        payload = _request_json(f"{donor_url.rstrip('/')}/api/providers", timeout=30.0)
    except (HTTPError, URLError, ValueError):
        return None
    providers = payload.get("providers") if isinstance(payload.get("providers"), list) else []
    for item in providers:
        if not isinstance(item, dict):
            continue
        if str(item.get("name") or "") == "Finviz Elite":
            detail = str(item.get("detail") or "").strip()
            return detail or None
    return None


def _finviz_auth_blocker(donor_url: str) -> str | None:
    detail = _finviz_provider_detail(donor_url)
    if not detail:
        return None
    lowered = detail.lower()
    if "token expired" in lowered or "401" in detail or "not configured" in lowered:
        return detail
    return None


def _class_counts(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        key = str(row.get(field) or "UNKNOWN")
        counts[key] = counts.get(key, 0) + 1
    return counts


def _donor_sample(donor_url: str) -> tuple[int, int, int, dict[str, int], tuple[str, ...]]:
    payload = _request_json(f"{donor_url.rstrip('/')}/api/current/candidates")
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    rows = data.get("rows") if isinstance(data.get("rows"), list) else []
    row_dicts = [row for row in rows if isinstance(row, dict)]
    stale = sum(1 for row in row_dicts if bool(row.get("stale")))
    evaluable = sum(
        1
        for row in row_dicts
        if str(row.get("adam_classification") or "") not in {"UNEVALUABLE", "CONFLICTED", ""}
    )
    notes: list[str] = []
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    last_error = summary.get("last_refresh_error")
    if last_error:
        notes.append(str(last_error))
    providers = data.get("providers") if isinstance(data.get("providers"), list) else []
    configured = [p for p in providers if isinstance(p, dict) and p.get("state") == "OK"]
    if configured:
        notes.append(f"ok_providers={len(configured)}")
    return (
        len(row_dicts),
        evaluable,
        stale,
        _class_counts(row_dicts, "adam_classification"),
        tuple(notes),
    )


def _imp_sample(imp_url: str) -> tuple[bool, int, bool, int]:
    scanner_status, scanner_payload = _imp_json(imp_url, "/explore/squeeze/scanner")
    explore_status, explore_payload = _imp_json(imp_url, "/explore/squeeze")
    scanner_available = scanner_status == 200 and bool(scanner_payload.get("available"))
    explore_available = explore_status == 200 and bool(explore_payload.get("available"))
    scanner_rows = int(scanner_payload.get("row_count") or 0) if scanner_available else 0
    explore_rows = int(explore_payload.get("row_count") or 0) if explore_available else 0
    return scanner_available, scanner_rows, explore_available, explore_rows


def _imp_json(base_url: str, path: str) -> tuple[int | None, dict[str, Any]]:
    url = base_url.rstrip("/") + path
    try:
        payload = _request_json(url)
        return 200, payload
    except HTTPError as exc:
        return exc.code, {}
    except URLError:
        return None, {}


def run_soak(
    *,
    donor_url: str,
    imp_url: str,
    iterations: int,
    interval_seconds: float,
    trigger_refresh: bool,
    require_evaluable: bool = False,
) -> SoakReport:
    started = datetime.now(UTC)
    samples: list[SoakSample] = []
    donor_mode = (
        fetch_donor_deployment_mode(base_url=donor_url) if is_available(base_url=donor_url) else None
    )

    for iteration in range(1, iterations + 1):
        refresh_triggered = False
        refresh_errors = 0
        if trigger_refresh and iteration == 1:
            try:
                refresh_payload = _request_json(
                    f"{donor_url.rstrip('/')}/api/current/refresh",
                    method="POST",
                    timeout=120.0,
                )
                refresh_triggered = True
                data = refresh_payload.get("data") if isinstance(refresh_payload.get("data"), dict) else {}
                errors = data.get("errors") if isinstance(data.get("errors"), list) else []
                refresh_errors = len(errors)
            except (HTTPError, URLError, ValueError):
                refresh_triggered = True
                refresh_errors = -1

        row_count, evaluable, stale, classes, notes = _donor_sample(donor_url)
        imp_scanner_ok, imp_scanner_rows, imp_explore_ok, imp_explore_rows = _imp_sample(imp_url)
        samples.append(
            SoakSample(
                iteration=iteration,
                donor_mode=donor_mode,
                donor_row_count=row_count,
                donor_evaluable_count=evaluable,
                donor_stale_count=stale,
                donor_adam_classes=classes,
                imp_scanner_available=imp_scanner_ok,
                imp_scanner_row_count=imp_scanner_rows,
                imp_explore_available=imp_explore_ok,
                imp_explore_row_count=imp_explore_rows,
                refresh_triggered=refresh_triggered,
                refresh_errors=refresh_errors,
                notes=notes,
            )
        )
        if iteration < iterations:
            time.sleep(interval_seconds)

    finished = datetime.now(UTC)
    row_counts = [sample.donor_row_count for sample in samples]
    scanner_counts = [sample.imp_scanner_row_count for sample in samples]
    stable_rows = len(set(row_counts)) == 1 and row_counts[0] > 0
    stable_scanner = len(set(scanner_counts)) == 1 and scanner_counts[0] == row_counts[0]
    finviz_blocker = _finviz_auth_blocker(donor_url)
    summary = {
        "status": "PASS" if stable_rows and stable_scanner and samples[-1].imp_scanner_available else "FAIL",
        "donor_mode": donor_mode,
        "stable_donor_row_count": stable_rows,
        "stable_imp_scanner_rows": stable_scanner,
        "final_donor_row_count": row_counts[-1] if row_counts else 0,
        "final_imp_scanner_row_count": scanner_counts[-1] if scanner_counts else 0,
        "final_evaluable_count": samples[-1].donor_evaluable_count if samples else 0,
        "final_stale_count": samples[-1].donor_stale_count if samples else 0,
        "finviz_provider_detail": _finviz_provider_detail(donor_url),
        "finviz_auth_blocker": finviz_blocker,
        "limitations": [
            "Soak validates lane stability, not predictive squeeze performance.",
            "SEC-only cloud deployments may keep Adam classifications UNEVALUABLE without Finviz/IBKR.",
        ],
    }
    if finviz_blocker and require_evaluable:
        summary["status"] = "FAIL"
        summary["evaluable_blocked_by_finviz_auth"] = True
    if require_evaluable and (not samples or samples[-1].donor_evaluable_count <= 0):
        summary["status"] = "FAIL"
        summary["evaluable_required"] = True
    return SoakReport(
        started_at=started.isoformat().replace("+00:00", "Z"),
        finished_at=finished.isoformat().replace("+00:00", "Z"),
        donor_url=donor_url,
        imp_url=imp_url,
        iterations=iterations,
        interval_seconds=interval_seconds,
        trigger_refresh=trigger_refresh,
        samples=tuple(samples),
        summary=summary,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--donor-url", default=DEFAULT_DONOR_URL)
    parser.add_argument("--imp-url", default=DEFAULT_IMP_URL)
    parser.add_argument("--iterations", type=int, default=3)
    parser.add_argument("--interval-seconds", type=float, default=5.0)
    parser.add_argument("--trigger-refresh", action="store_true")
    parser.add_argument(
        "--require-evaluable",
        action="store_true",
        help="Fail unless final sample has evaluable Adam classifications",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    if not is_available(base_url=args.donor_url):
        print(f"Donor not reachable at {args.donor_url}")
        return 2

    report = run_soak(
        donor_url=args.donor_url,
        imp_url=args.imp_url,
        iterations=max(1, args.iterations),
        interval_seconds=max(0.0, args.interval_seconds),
        trigger_refresh=bool(args.trigger_refresh),
        require_evaluable=bool(args.require_evaluable),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report.public_dict(), sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {args.output.resolve()}")
    print(f"Status: {report.summary['status']}")
    return 0 if report.summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
