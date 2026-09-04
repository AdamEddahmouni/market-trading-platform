"""FRED / ALFRED live and offline capability probe."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.credential_audit import scan_redacted_bytes, SECRET_SCAN_RULES  # noqa: E402
from market_platform_foundation.fred.health import capability_report  # noqa: E402
from market_platform_foundation.fred.live import api_key_present, live_enabled, load_api_key  # noqa: E402
from market_platform_foundation.fred.redaction import redact_text  # noqa: E402

OUTPUT = ROOT / "evidence" / "fred" / "capability-report.json"


def _security_self_check() -> dict[str, object]:
    fake = "FAKE_TEST_SECRET"
    v1_dirty = f"https://api.stlouisfed.org/fred/series?api_key={fake}&series_id=DFF"
    v2_dirty = f"Authorization: Bearer {fake}"
    v1_ok = fake not in redact_text(v1_dirty)
    v2_ok = fake not in redact_text(v2_dirty)
    return {
        "v1_url_redaction": v1_ok,
        "v2_bearer_redaction": v2_ok,
        "fred_api_key_present": api_key_present(),
    }


def _scan_output_for_leaks(payload: bytes, api_key: str) -> list[dict[str, str]]:
    if not api_key:
        return []
    findings = scan_redacted_bytes(payload, "PROBE-OUTPUT", "WORKTREE", SECRET_SCAN_RULES)
    if api_key.encode() in payload:
        findings.append(
            {
                "opaque_path_id": "PROBE-OUTPUT",
                "revision_id": "WORKTREE",
                "rule_id": "RAW_KEY_LEAK",
                "sanitized_location": "LINE-REDACTED",
            }
        )
    return findings


def main() -> int:
    live = live_enabled() or os.environ.get("IMP_FRED_LIVE") == "1"
    if live and not api_key_present():
        print("FRED_API_KEY_PRESENT=false — aborting live probe")
        return 1

    security = _security_self_check()
    report = capability_report(live=live and api_key_present())
    report["security"] = security

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(report, indent=2)
    OUTPUT.write_text(serialized, encoding="utf-8")

    leaks = _scan_output_for_leaks(serialized.encode("utf-8"), load_api_key())
    report["post_write_leak_scan"] = {"finding_count": len(leaks)}
    if leaks:
        print(f"WARNING: {len(leaks)} potential credential findings in output — review required")
        return 2

    print(f"Wrote {OUTPUT}")
    print(f"classification={report.get('classification', 'IMPLEMENTED')}")
    print(f"FRED_API_KEY_PRESENT={str(api_key_present()).lower()}")
    if live and api_key_present():
        health = report.get("health", {})
        print(f"v1_auth_success={health.get('V1_REACHABLE', False)}")
        print(f"v2_auth_success={health.get('V2_REACHABLE', False)}")
        audit = report.get("registry_audit", {}).get("by_status", {})
        print(f"registry_verified_live={audit.get('VERIFIED_LIVE', 0)}")
        print(f"registry_mismatch={audit.get('MISMATCH', 0)}")
        alfred = report.get("alfred_revision_proof", {})
        print(f"alfred_pit_status={alfred.get('status', 'unknown')}")
        recon = report.get("reconciliation", {}).get("live", {})
        print(f"v1_v2_match={recon.get('match', False)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
