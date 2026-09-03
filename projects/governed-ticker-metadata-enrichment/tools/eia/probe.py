"""EIA physical energy fundamentals live and offline capability probe."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.credential_audit import scan_redacted_bytes, SECRET_SCAN_RULES  # noqa: E402
from market_platform_foundation.eia.health import capability_report, live_cross_asset_contexts  # noqa: E402
from market_platform_foundation.eia.live import api_key_present, live_enabled, load_api_key  # noqa: E402
from market_platform_foundation.eia.redaction import redact_text  # noqa: E402

OUTPUT = ROOT / "evidence" / "eia" / "capability-report.json"


def _security_self_check() -> dict[str, object]:
    fake = "FAKE_TEST_SECRET"
    dirty = f"https://api.eia.gov/v2/petroleum/sum/sndw/data?api_key={fake}&frequency=weekly"
    return {
        "url_redaction": fake not in redact_text(dirty),
        "eia_api_key_present": api_key_present(),
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
    live = live_enabled() or os.environ.get("IMP_EIA_LIVE") == "1"
    if live and not api_key_present():
        print("EIA_API_KEY_PRESENT=false — aborting live probe")
        return 1

    security = _security_self_check()
    report = capability_report(live=live and api_key_present())
    report["security"] = security

    if live and api_key_present():
        report["cross_asset"] = live_cross_asset_contexts()

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(report, indent=2)
    OUTPUT.write_text(serialized, encoding="utf-8")

    leaks = _scan_output_for_leaks(serialized.encode("utf-8"), load_api_key())
    report["post_write_leak_scan"] = {"finding_count": len(leaks)}
    if leaks:
        print(f"WARNING: {len(leaks)} potential credential findings in output")
        return 2

    print(f"Wrote {OUTPUT}")
    print(f"classification={report.get('classification', 'IMPLEMENTED')}")
    print(f"EIA_API_KEY_PRESENT={str(api_key_present()).lower()}")
    if live and api_key_present():
        health = report.get("health", {})
        registry = report.get("registry", {})
        print(f"eia_api_auth_success={report.get('eia_api_auth_success', False)}")
        print(f"api_reachable={health.get('api_reachable', False)}")
        print(f"registry_observed={registry.get('observed_count', 0)}/{registry.get('total_count', 0)}")
        wpsr = report.get("wpsr", {}).get("live", {})
        wngsr = report.get("wngsr", {}).get("live", {})
        print(f"wpsr_period={wpsr.get('reference_period_end', '')} api_period={wpsr.get('api_latest_period', '')}")
        print(f"wngsr_period={wngsr.get('reference_period_end', '')} api_period={wngsr.get('api_latest_period', '')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
