"""Run integration acceptance checks against a local or deployed application."""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

API_VERSION = "1.0.0"
SCHEMA_VERSION = "batch14.integration.v1"
FROZEN_TOTALS = {"PASS": 97, "FAIL": 20, "UNKNOWN": 208}
METHODOLOGY_IDS = {
    "legacy_prime_setup",
    "peer_reference_methodology",
    "adam_evidence_gated_prime.v1",
}


@dataclass(frozen=True, slots=True)
class AcceptanceCheck:
    check_id: str
    passed: bool
    message: str


@dataclass(frozen=True, slots=True)
class AcceptanceResult:
    checks: tuple[AcceptanceCheck, ...]
    summary: dict[str, Any]

    @property
    def passed(self) -> bool:
        return all(check.passed for check in self.checks)

    def public_dict(self) -> dict[str, Any]:
        return {
            "status": "PASS" if self.passed else "FAIL",
            "checks": [asdict(check) for check in self.checks],
            "summary": self.summary,
        }

    def to_json(self) -> str:
        return json.dumps(self.public_dict(), sort_keys=True)


def _request(
    base_url: str,
    path: str,
    *,
    method: str = "GET",
) -> tuple[int, Any]:
    request = Request(base_url.rstrip("/") + path, method=method)
    try:
        with urlopen(request, timeout=20) as response:
            body = response.read()
            content_type = response.headers.get("Content-Type", "")
            return response.status, (
                json.loads(body)
                if "json" in content_type or body.lstrip().startswith((b"{", b"["))
                else body.decode("utf-8", errors="replace")
            )
    except HTTPError as exc:
        return exc.code, None


def _check(
    checks: list[AcceptanceCheck],
    check_id: str,
    condition: bool,
    success: str,
    failure: str,
) -> None:
    checks.append(AcceptanceCheck(check_id, bool(condition), success if condition else failure))


def run_acceptance(base_url: str) -> AcceptanceResult:
    checks: list[AcceptanceCheck] = []
    captured: list[Any] = []
    summary: dict[str, Any] = {
        "api_version": None,
        "schema_version": None,
        "frozen_totals": None,
        "trading_capabilities": "UNKNOWN",
    }
    try:
        health_status, health = _request(base_url, "/health")
        captured.append(health)
        _check(
            checks,
            "health",
            health_status == 200 and isinstance(health, dict) and health.get("status") == "OK",
            "Health endpoint is operational.",
            "Health endpoint failed.",
        )

        ready_status, ready = _request(base_url, "/ready")
        captured.append(ready)
        ready_data = ready.get("data", {}) if isinstance(ready, dict) else {}
        _check(
            checks,
            "readiness",
            ready_status == 200 and ready_data.get("application_operational") is True,
            "Readiness endpoint reports the application operational.",
            "Readiness endpoint is not operational.",
        )

        if isinstance(health, dict):
            summary["api_version"] = health.get("api_version")
            summary["schema_version"] = health.get("schema_version")
        _check(
            checks,
            "api_contract",
            summary["api_version"] == API_VERSION
            and summary["schema_version"] == SCHEMA_VERSION,
            "API and schema versions match.",
            "API or schema version mismatch.",
        )

        frozen_status, frozen = _request(base_url, "/api/frozen/candidates")
        captured.append(frozen)
        frozen_data = frozen.get("data", {}) if isinstance(frozen, dict) else {}
        totals = frozen_data.get("outcome_totals")
        summary["frozen_totals"] = totals
        _check(
            checks,
            "frozen_totals",
            frozen_status == 200
            and frozen_data.get("row_count") == 13
            and totals == FROZEN_TOTALS
            and frozen_data.get("phase3e_started") is False,
            "Frozen candidates and exact totals match.",
            "Frozen candidates, totals, or Phase 3E state mismatch.",
        )

        methodology_status, methodologies = _request(base_url, "/api/methodologies")
        captured.append(methodologies)
        methodology_data = (
            methodologies.get("data", {}) if isinstance(methodologies, dict) else {}
        )
        _check(
            checks,
            "methodologies",
            methodology_status == 200
            and set(methodology_data.get("methodology_ids", [])) == METHODOLOGY_IDS,
            "Methodology identifiers match.",
            "Methodology identifiers mismatch.",
        )

        manifest_status, manifest = _request(base_url, "/api/v1/integration/manifest")
        captured.append(manifest)
        manifest_data = manifest.get("data", {}) if isinstance(manifest, dict) else {}
        prohibited = manifest_data.get("prohibited_capabilities", {})
        _check(
            checks,
            "integration_manifest",
            manifest_status == 200
            and manifest_data.get("api_version") == API_VERSION
            and manifest_data.get("schema_version") == SCHEMA_VERSION
            and prohibited
            == {
                "trading": "UNSUPPORTED",
                "orders": "UNSUPPORTED",
                "account_access": "UNSUPPORTED",
            },
            "Integration manifest matches the stable contract.",
            "Integration manifest mismatch.",
        )

        export_status, exported = _request(
            base_url,
            "/api/export?mode=FROZEN_RESEARCH",
            method="POST",
        )
        captured.append(exported)
        _check(
            checks,
            "export",
            export_status == 200
            and isinstance(exported, dict)
            and exported.get("row_count") == 13,
            "Frozen research export succeeds.",
            "Frozen research export failed.",
        )

        prohibited_statuses = [
            _request(base_url, path)[0]
            for path in (
                "/api/orders",
                "/api/account",
                "/api/positions",
                "/api/trading",
            )
        ]
        no_trading = all(status == 404 for status in prohibited_statuses)
        summary["trading_capabilities"] = "ABSENT" if no_trading else "PRESENT"
        _check(
            checks,
            "no_trading_endpoints",
            no_trading,
            "Trading and account endpoints are absent.",
            "A prohibited trading or account endpoint responded.",
        )

        scanner_status, scanner = _request(base_url, "/")
        captured.append(scanner)
        _check(
            checks,
            "scanner",
            scanner_status == 200
            and isinstance(scanner, str)
            and "Short Squeeze Scanner" in scanner,
            "Default Scanner is available.",
            "Default Scanner is unavailable.",
        )

        advanced_status, advanced = _request(base_url, "/advanced")
        captured.append(advanced)
        _check(
            checks,
            "advanced_research",
            advanced_status == 200
            and isinstance(advanced, str)
            and "Short Squeeze Research Screener" in advanced,
            "Advanced Research dashboard is available.",
            "Advanced Research dashboard is unavailable.",
        )

        encoded = json.dumps(captured, default=str)
        leak_patterns = (
            re.compile(r"(?i)authorization:\s*bearer\s+\S+"),
            re.compile(r"(?i)\b[A-Z]:\\Users\\"),
            re.compile(r"(?i)https?://[^/\s:@]+:[^/\s@]+@"),
            re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
        )
        _check(
            checks,
            "no_secret_leakage",
            not any(pattern.search(encoded) for pattern in leak_patterns),
            "No obvious secret or local-path leakage detected.",
            "Potential secret or local-path leakage detected.",
        )
    except (OSError, URLError, ValueError, json.JSONDecodeError):
        checks.append(
            AcceptanceCheck(
                "transport",
                False,
                "Application could not be reached or returned an invalid response.",
            )
        )
    return AcceptanceResult(tuple(checks), summary)


def run_frozen_acceptance() -> AcceptanceResult:
    from apps.research_screener.deployment import DeploymentMode
    from apps.research_screener.server import build_server, find_free_port

    with tempfile.TemporaryDirectory(prefix="squeeze-acceptance-") as directory:
        server = build_server(
            find_free_port(9470),
            export_dir=Path(directory),
            deployment_mode=DeploymentMode.FROZEN_DEMO,
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base_url = f"http://127.0.0.1:{server.server_address[1]}"
            return run_acceptance(base_url)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("frozen", "local"), default="frozen")
    parser.add_argument("--url")
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    result = (
        run_acceptance(args.url or "http://127.0.0.1:8787")
        if args.url or args.mode == "local"
        else run_frozen_acceptance()
    )
    if args.as_json:
        print(result.to_json())
    else:
        print(f"INTEGRATION_ACCEPTANCE: {'PASS' if result.passed else 'FAIL'}")
        for check in result.checks:
            print(f"{'PASS' if check.passed else 'FAIL'} {check.check_id}: {check.message}")
    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())


__all__ = [
    "AcceptanceCheck",
    "AcceptanceResult",
    "main",
    "run_acceptance",
    "run_frozen_acceptance",
]
