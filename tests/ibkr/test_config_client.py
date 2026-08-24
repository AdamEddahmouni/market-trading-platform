from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.ibkr.client import EndpointNotAllowed, IbkrClient, LiveGateDisabled, TransportResponse
from tools.ibkr.config import ConfigError, IbkrConfig, validate_gateway_url


class RecordingTransport:
    def __init__(self, response: TransportResponse | None = None) -> None:
        self.calls: list[object] = []
        self.response = response or TransportResponse(200, {"content-type": "application/json"}, b'{"ok":true}')

    def __call__(self, request, *, ssl_context, timeout: float) -> TransportResponse:
        self.calls.append((request, ssl_context, timeout))
        return self.response


class IbkrConfigTests(unittest.TestCase):
    def test_defaults_are_disabled_and_conservative(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = IbkrConfig.from_env({}, root=Path(tmp))
        self.assertFalse(config.live_enabled)
        self.assertEqual(config.gateway_url, "https://127.0.0.1:5000/v1/api")
        self.assertEqual(config.requests_per_second, 10.0)
        self.assertEqual(config.history_min_spacing_seconds, 15.0)
        self.assertEqual(config.history_window_max, 50)
        self.assertEqual(config.penalty_box_seconds, 900.0)

    def test_https_loopback_gateway_variants_are_accepted(self) -> None:
        for value in (
            "https://127.0.0.1:5000/v1/api",
            "https://127.9.8.7:5000/v1/api/",
            "https://localhost:5000/v1/api",
            "https://[::1]:5000/v1/api",
        ):
            with self.subTest(value=value):
                self.assertEqual(validate_gateway_url(value), value.rstrip("/"))

    def test_non_loopback_or_ambiguous_gateway_urls_fail_closed(self) -> None:
        invalid = (
            "http://127.0.0.1:5000/v1/api",
            "https://gateway.interactivebrokers.com:5000/v1/api",
            "https://192.168.1.10:5000/v1/api",
            "https://localhost.example:5000/v1/api",
            "https://user:pass@127.0.0.1:5000/v1/api",
            "https://127.0.0.1:5001/v1/api",
            "https://127.0.0.1:5000/",
            "https://127.0.0.1:5000/v1/api?next=https://example.com",
            "https://127.0.0.1:5000/v1/api#fragment",
        )
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ConfigError):
                validate_gateway_url(value)

    def test_invalid_pacing_values_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cases = (
                {"IMP_IBKR_PACING_RPS": "0"},
                {"IMP_IBKR_PACING_RPS": "11"},
                {"IMP_IBKR_HIST_MIN_SPACING_SEC": "-1"},
                {"IMP_IBKR_HIST_WINDOW_MAX": "51"},
                {"IMP_IBKR_PENALTY_BOX_SEC": "899"},
            )
            for env in cases:
                with self.subTest(env=env), self.assertRaises(ConfigError):
                    IbkrConfig.from_env(env, root=root)

    def test_sub_one_request_per_second_setting_is_supported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = IbkrConfig.from_env(
                {"IMP_IBKR_LIVE": "1", "IMP_IBKR_PACING_RPS": "0.5"}, root=root
            )
            client = IbkrClient(config, transport=RecordingTransport())
            self.assertEqual(client.request_json("GET", "/iserver/auth/status"), {"ok": True})


class IbkrClientSafetyTests(unittest.TestCase):
    def _config(self, root: Path, **overrides: str) -> IbkrConfig:
        env = {"IMP_IBKR_LIVE": "1", **overrides}
        return IbkrConfig.from_env(env, root=root)

    def test_disabled_gate_stops_before_transport(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            transport = RecordingTransport()
            client = IbkrClient(IbkrConfig.from_env({}, root=Path(tmp)), transport=transport)
            with self.assertRaises(LiveGateDisabled):
                client.request_json("GET", "/iserver/auth/status")
        self.assertEqual(transport.calls, [])

    def test_non_loopback_configuration_stops_before_transport(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            transport = RecordingTransport()
            with self.assertRaises(ConfigError):
                config = self._config(Path(tmp), IMP_IBKR_GATEWAY_URL="https://example.com:5000/v1/api")
                IbkrClient(config, transport=transport)
        self.assertEqual(transport.calls, [])

    def test_only_documented_observational_routes_are_allowed(self) -> None:
        operations = (
            ("GET", "/iserver/auth/status"),
            ("POST", "/tickle"),
            ("POST", "/iserver/auth/ssodh/init"),
            ("GET", "/iserver/secdef/search"),
            ("GET", "/iserver/marketdata/snapshot"),
            ("GET", "/hmds/history"),
            ("GET", "/trsrv/secdef"),
            ("GET", "/trsrv/secdef/info"),
            ("GET", "/iserver/scanner/params"),
            ("POST", "/iserver/scanner/run"),
            ("GET", "/portfolio/accounts"),
            ("GET", "/portfolio/DU123/positions/0"),
            ("GET", "/portfolio/DU123/summary"),
        )
        with tempfile.TemporaryDirectory() as tmp:
            transport = RecordingTransport()
            client = IbkrClient(self._config(Path(tmp)), transport=transport)
            for method, path in operations:
                with self.subTest(method=method, path=path):
                    self.assertEqual(client.request_json(method, path), {"ok": True})
        self.assertEqual(len(transport.calls), len(operations))

    def test_order_execution_and_arbitrary_paths_are_rejected_before_transport(self) -> None:
        forbidden = (
            ("POST", "/iserver/account/DU123/orders"),
            ("DELETE", "/iserver/account/DU123/order/7"),
            ("POST", "/iserver/reply/abc"),
            ("GET", "/unknown"),
            ("GET", "//example.com/iserver/auth/status"),
        )
        with tempfile.TemporaryDirectory() as tmp:
            transport = RecordingTransport()
            client = IbkrClient(self._config(Path(tmp)), transport=transport)
            for method, path in forbidden:
                with self.subTest(method=method, path=path), self.assertRaises(EndpointNotAllowed):
                    client.request_json(method, path)
        self.assertEqual(transport.calls, [])

    def test_query_and_body_are_encoded_without_mutating_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            transport = RecordingTransport()
            client = IbkrClient(self._config(Path(tmp)), transport=transport)
            params = {"symbols": "AAPL", "fields": "31,84"}
            body = {"instrument": "STK", "locations": "STK.US.MAJOR"}
            self.assertEqual(
                client.request_json("POST", "/iserver/scanner/run", params=params, body=body),
                {"ok": True},
            )
            request = transport.calls[0][0]
        self.assertIn("symbols=AAPL", request.full_url)
        self.assertEqual(json.loads(request.data), body)
        self.assertEqual(params, {"symbols": "AAPL", "fields": "31,84"})
        self.assertEqual(body, {"instrument": "STK", "locations": "STK.US.MAJOR"})


if __name__ == "__main__":
    unittest.main()
