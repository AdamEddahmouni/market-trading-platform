from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.ibkr.config import IbkrConfig
from tools.ibkr.probe import CapabilityProbe, main, write_report
from tools.ibkr import probe as probe_module


class FakeClient:
    def __init__(self, responses: dict[str, object]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, str, object, object]] = []

    def request_json(self, method: str, path: str, *, params=None, body=None):
        self.calls.append((method, path, params, body))
        value = self.responses[path]
        if isinstance(value, list) and path == "/iserver/marketdata/snapshot":
            selected = value.pop(0)
        else:
            selected = value
        if isinstance(selected, BaseException):
            raise selected
        return selected


def successful_responses() -> dict[str, object]:
    return {
        "/iserver/auth/status": {"connected": True, "authenticated": True},
        "/iserver/secdef/search": [{"symbol": "AAPL", "conid": 265598}],
        "/iserver/marketdata/snapshot": [[], [{"conid": 265598, "31": "225.00"}]],
        "/hmds/history": {"symbol": "AAPL", "data": [{"t": 1, "c": 225.0}]},
        "/trsrv/secdef": {"secdef": ["AAPL"]},
        "/iserver/scanner/params": {"instrument_list": []},
        "/portfolio/accounts": [{"accountId": "DU-REDACT-IN-REPORT"}],
    }


class CapabilityProbeTests(unittest.TestCase):
    def test_tws_config_selects_tws_client_factory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = IbkrConfig.from_env(
                {"IMP_IBKR_LIVE": "1", "IMP_IBKR_TRANSPORT": "tws"},
                root=Path(tmp),
            )
        expected = object()
        with patch.object(probe_module, "TwsIbkrClient", return_value=expected) as factory:
            self.assertIs(probe_module.build_client(config), expected)
        factory.assert_called_once_with(config)

    def test_report_includes_client_transport_identity(self) -> None:
        client = FakeClient(successful_responses())
        client.transport = "tws"
        client.provider = "IBKR_TWS_GATEWAY"
        report = CapabilityProbe(client).run("AAPL")
        self.assertEqual(report["transport"], "tws")
        self.assertEqual(report["provider"], "IBKR_TWS_GATEWAY")

    def test_successful_probe_records_observed_capabilities_and_snapshot_preflight(self) -> None:
        client = FakeClient(successful_responses())
        probe = CapabilityProbe(client, observed_at=lambda: "2026-08-24T12:00:00Z")
        report = probe.run("AAPL")
        self.assertEqual(report["classification"], "OBSERVED_CAPABILITY_REPORT_NOT_ADMITTED")
        self.assertEqual(report["observed_at"], "2026-08-24T12:00:00Z")
        self.assertEqual(report["resolved_contract"]["conid"], 265598)
        self.assertTrue(
            all(
                row["evidence_class"] == "OBSERVED" and row["status"] == "AVAILABLE"
                for row in report["capabilities"].values()
            )
        )
        snapshots = [call for call in client.calls if call[1] == "/iserver/marketdata/snapshot"]
        self.assertEqual(len(snapshots), 2)
        self.assertEqual(snapshots[0][2]["conids"], "265598")

    def test_contract_search_failure_skips_only_conid_dependent_surfaces(self) -> None:
        responses = successful_responses()
        responses["/iserver/secdef/search"] = RuntimeError("search unavailable")
        client = FakeClient(responses)
        report = CapabilityProbe(client).run("AAPL")
        capabilities = report["capabilities"]
        self.assertEqual(capabilities["contract_search"]["status"], "ERROR")
        self.assertEqual(capabilities["delayed_snapshot"]["evidence_class"], "UNTESTED")
        self.assertEqual(capabilities["historical_bars"]["evidence_class"], "UNTESTED")
        self.assertEqual(capabilities["option_definitions"]["status"], "AVAILABLE")
        self.assertEqual(capabilities["scanner_parameters"]["status"], "AVAILABLE")
        self.assertEqual(capabilities["portfolio_accounts"]["status"], "AVAILABLE")
        called_paths = [call[1] for call in client.calls]
        self.assertNotIn("/hmds/history", called_paths)
        self.assertNotIn("/iserver/marketdata/snapshot", called_paths)

    def test_unauthenticated_gateway_stops_after_auth_status(self) -> None:
        responses = successful_responses()
        responses["/iserver/auth/status"] = {"connected": True, "authenticated": False}
        client = FakeClient(responses)
        report = CapabilityProbe(client).run("AAPL")
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(report["capabilities"]["session"]["status"], "UNAVAILABLE")
        self.assertTrue(
            all(
                row["evidence_class"] == "UNTESTED"
                for name, row in report["capabilities"].items()
                if name != "session"
            )
        )

    def test_report_writer_redacts_secrets_and_account_identifiers(self) -> None:
        report = CapabilityProbe(FakeClient(successful_responses())).run("AAPL")
        report["diagnostic"] = "Authorization: Bearer report-secret"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "capability-report.json"
            write_report(path, report)
            content = path.read_text(encoding="utf-8")
            parsed = json.loads(content)
        self.assertNotIn("report-secret", content)
        self.assertNotIn("DU-REDACT-IN-REPORT", content)
        self.assertEqual(parsed["capabilities"]["portfolio_accounts"]["status"], "AVAILABLE")

    def test_disabled_cli_constructs_no_client_and_makes_no_calls(self) -> None:
        constructed: list[object] = []

        def factory(config):
            constructed.append(config)
            raise AssertionError("client must not be constructed")

        with tempfile.TemporaryDirectory() as tmp:
            result = main(
                ["--output", str(Path(tmp) / "report.json")],
                env={},
                client_factory=factory,
            )
        self.assertEqual(result, 2)
        self.assertEqual(constructed, [])


if __name__ == "__main__":
    unittest.main()
