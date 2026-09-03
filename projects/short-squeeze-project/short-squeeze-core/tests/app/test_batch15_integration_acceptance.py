from __future__ import annotations

import json
import threading
from pathlib import Path

from apps.research_screener.deployment import DeploymentMode
from apps.research_screener.server import build_server, find_free_port


def test_integration_acceptance_passes_against_frozen_http_application(
    tmp_path: Path,
) -> None:
    from tools.integration_acceptance import run_acceptance

    server = build_server(
        find_free_port(9420),
        export_dir=tmp_path,
        deployment_mode=DeploymentMode.FROZEN_DEMO,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base_url = f"http://127.0.0.1:{server.server_address[1]}"
        result = run_acceptance(base_url)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert result.passed is True
    assert all(check.passed for check in result.checks)
    assert result.summary["frozen_totals"] == {
        "PASS": 97,
        "FAIL": 20,
        "UNKNOWN": 208,
    }
    assert result.summary["api_version"] == "1.0.0"
    assert result.summary["schema_version"] == "batch14.integration.v1"
    assert result.summary["trading_capabilities"] == "ABSENT"
    assert str(tmp_path) not in result.to_json()


def test_frozen_acceptance_can_start_without_provider_configuration() -> None:
    from tools.integration_acceptance import run_frozen_acceptance

    result = run_frozen_acceptance()

    assert result.passed is True
    encoded = result.to_json().lower()
    assert "api_key" not in encoded
    assert "authorization" not in encoded
    assert "c:\\users\\" not in encoded


def test_acceptance_json_has_stable_machine_readable_check_ids() -> None:
    from tools.integration_acceptance import run_frozen_acceptance

    payload = json.loads(run_frozen_acceptance().to_json())
    check_ids = {check["check_id"] for check in payload["checks"]}

    assert {
        "health",
        "readiness",
        "api_contract",
        "frozen_totals",
        "methodologies",
        "integration_manifest",
        "export",
        "no_trading_endpoints",
        "no_secret_leakage",
    }.issubset(check_ids)
