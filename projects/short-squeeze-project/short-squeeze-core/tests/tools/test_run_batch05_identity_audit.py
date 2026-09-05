"""Identity audit for Batch 05 external discovery."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from tools.ibkr_historical_export.models import ContractCandidate
from tools.ibkr_historical_export.statuses import ContractStatus
from tools.run_batch05_identity_audit import run_audit


def _candidate(symbol: str, con_id: int) -> ContractCandidate:
    return ContractCandidate(
        con_id=con_id,
        symbol=symbol,
        local_symbol=symbol,
        sec_type="STK",
        currency="USD",
        exchange="SMART",
        primary_exchange="NASDAQ",
        trading_class=symbol,
        long_name=f"{symbol} Corp",
        time_zone_id="US/Eastern",
        trading_hours="",
        liquid_hours="",
        valid_exchanges="NASDAQ",
    )


def test_run_audit_passes_for_resolved_contracts(tmp_path: Path) -> None:
    discovery = tmp_path / "rows.json"
    discovery.write_text(
        json.dumps(
            {
                "rows": [
                    {"ticker": "AACB", "observed_at": "2026-08-17T22:09:23.412932Z"},
                    {"ticker": "AACG", "observed_at": "2026-08-17T22:09:23.412932Z"},
                ],
            }
        ),
        encoding="utf-8",
    )
    private = tmp_path / "private"
    private.mkdir()

    resolution = MagicMock()
    resolution.status = ContractStatus.CONTRACT_RESOLVED
    resolution.reason = "unique conId 1"
    resolution.resolved = _candidate("AACB", 1)
    resolution.candidates = (resolution.resolved,)

    session = MagicMock()
    connection = MagicMock()
    connection.attempts = []

    with patch(
        "tools.run_batch05_identity_audit.probe_and_connect",
        return_value=(session, connection),
    ), patch(
        "tools.run_batch05_identity_audit.qualify_contract",
        return_value=resolution,
    ), patch(
        "tools.run_batch05_identity_audit.AUDIT_OUT",
        tmp_path / "audit.json",
    ):
        audit = run_audit(discovery_path=discovery, private_root=private)

    assert audit["status"] == "PASS"
    assert audit["symbols"] == ["AACB", "AACG"]
    assert all(
        row["contract_status"] == ContractStatus.CONTRACT_RESOLVED.value
        for row in audit["contract_resolutions"]
    )
    updated = json.loads(discovery.read_text(encoding="utf-8"))
    assert updated["status"] == "IDENTITY_AUDIT_COMPLETE"
