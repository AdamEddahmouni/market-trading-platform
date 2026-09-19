"""Offline provider resilience: fixtures, mocks, fallback boundaries.

Does not contact live brokers, start collectors, calibrate Item 9, or enable Live.
"""

from __future__ import annotations

import json
import socket
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.operations.runtime_resilience_diagnostic import (  # noqa: E402
    build_runtime_resilience_diagnostic,
)
from market_platform_foundation.providers.adapters.moomoo_opend_equity_quote import (  # noqa: E402
    EMPTY_PAYLOAD,
    MOOMOO_OPEND_PROVIDER_ID,
    PROVIDER_TIMEOUT,
    TEMPORARY_NETWORK_FAILURE,
    MoomooOpenDEquityQuoteProvider,
    OpenDSnapshotResult,
)
from market_platform_foundation.providers.adapters.yahoo_delayed_equity_quote import (  # noqa: E402
    YAHOO_PROVIDER_ID,
    YahooDelayedEquityQuoteProvider,
)
from market_platform_foundation.providers.equity_quote_discovery import (  # noqa: E402
    discover_equity_quote_stack,
    equity_quote_discovery_operator_view,
)
from market_platform_foundation.providers.equity_quote_selection import (  # noqa: E402
    OpenDReadiness,
    delayed_cloud_overlay_provider,
    primary_equity_quote_provider,
)
from market_platform_foundation.providers.resilience import (  # noqa: E402
    DELAYED_DATA,
    FALLBACK_BLOCKED,
    MALFORMED_RESPONSE,
    OPEND_UNAVAILABLE,
    OVERLAY_ALLOWED,
    PARTIALLY_STALE,
    RECONNECTING,
    RESTART_RECOVERY,
    SOURCE_DISAGREEMENT,
    ProviderSessionState,
    classify_opend_connectivity,
    classify_provider_incident,
    incident_for_reason_code,
    note_disconnect,
    note_process_restart,
    note_reconnect,
)
from market_platform_foundation.ui_api.errors import (  # noqa: E402
    CanonicalErrorCategory,
    build_provider_error_payload,
    canonical_error_category,
)
from tests.support.hermetic_environment import env, unreachable_opend_env  # noqa: E402

_FIXTURE_PATH = ROOT / "tests/fixtures/providers/resilience/incidents.json"

_EXPECTED_TOKENS = {
    "opend_unavailable": OPEND_UNAVAILABLE,
    "delayed_data": DELAYED_DATA,
    "partially_stale": PARTIALLY_STALE,
    "source_disagreement": SOURCE_DISAGREEMENT,
    "reconnect": RECONNECTING,
    "timeout": PROVIDER_TIMEOUT,
    "empty_payload": EMPTY_PAYLOAD,
    "malformed_response": MALFORMED_RESPONSE,
    "temporary_network_failure": TEMPORARY_NETWORK_FAILURE,
    "restart_recovery": RESTART_RECOVERY,
    "fallback_blocked": FALLBACK_BLOCKED,
}


class _ScriptedOpenDTransport:
    def __init__(self, result: OpenDSnapshotResult | BaseException) -> None:
        self.result = result

    def fetch_snapshot(self, *, symbol: str, host: str, port: int) -> OpenDSnapshotResult:
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result


def _loopback_listener() -> tuple[socket.socket, str, int]:
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", 0))
    listener.listen(8)
    host, port = listener.getsockname()
    return listener, host, port


class ProviderResilienceFixtureTests(unittest.TestCase):
    def test_fixture_scenarios_cover_lane_f_matrix(self) -> None:
        payload = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(payload["live_execution"], "OFF")
        self.assertEqual(payload["item9_mode"], "IDLE")
        self.assertEqual(payload["item9_calibration"], "NOT_CALIBRATED")
        seen = {row["id"] for row in payload["scenarios"]}
        self.assertEqual(seen, set(_EXPECTED_TOKENS))
        for row in payload["scenarios"]:
            incident = classify_provider_incident(row)
            with self.subTest(row["id"]):
                self.assertEqual(incident.status_token, _EXPECTED_TOKENS[row["id"]])
                self.assertTrue(incident.operator_message)
                self.assertFalse(incident.fallback.overlay_as_hop_l1)
                self.assertEqual(incident.live_execution, "OFF")
                self.assertTrue(incident.preserves_item9_idle)
                snapshot = incident.to_dict()
                self.assertEqual(snapshot["item9_mode"], "IDLE")
                self.assertNotEqual(snapshot["item9_mode"], "DEGRADED")
                self.assertEqual(snapshot["item9_calibration"], "NOT_CALIBRATED")

    def test_opend_down_does_not_promote_yahoo_to_hop_l1(self) -> None:
        with unreachable_opend_env():
            primary = primary_equity_quote_provider()
            overlay = delayed_cloud_overlay_provider()
            result = primary.fetch_quote("AAPL")
        self.assertEqual(primary.provider_id, MOOMOO_OPEND_PROVIDER_ID)
        self.assertEqual(overlay.provider_id, YAHOO_PROVIDER_ID)
        self.assertEqual(result.reason_code, OPEND_UNAVAILABLE)
        incident = classify_provider_incident(
            {"scenario": "opend_unavailable", "promote_overlay_to_l1": True}
        )
        self.assertEqual(incident.status_token, FALLBACK_BLOCKED)
        self.assertFalse(incident.fallback.overlay_as_hop_l1)

    def test_source_disagreement_does_not_merge_prices(self) -> None:
        incident = classify_provider_incident(
            {
                "scenario": "source_disagreement",
                "primary_last_price": 10.0,
                "overlay_last_price": 11.5,
            }
        )
        self.assertEqual(incident.status_token, SOURCE_DISAGREEMENT)
        self.assertFalse(incident.details["merged"])
        self.assertEqual(incident.details["primary_last_price"], 10.0)
        self.assertEqual(incident.details["overlay_last_price"], 11.5)

    def test_partially_stale_does_not_fabricate_fields(self) -> None:
        incident = classify_provider_incident({"scenario": "partially_stale"})
        self.assertEqual(incident.status_token, PARTIALLY_STALE)
        self.assertFalse(incident.details["fabricated_fields"])

    def test_reconnect_and_restart_advance_generation(self) -> None:
        state = ProviderSessionState(generation=3, connected=True, status_token="HEALTHY")
        dropped = note_disconnect(state)
        self.assertEqual(dropped.status_token, RECONNECTING)
        self.assertFalse(dropped.connected)
        self.assertEqual(dropped.generation, 3)
        recovered = note_reconnect(dropped)
        self.assertEqual(recovered.generation, 4)
        self.assertEqual(recovered.status_token, RESTART_RECOVERY)
        restarted = note_process_restart(recovered)
        self.assertEqual(restarted.generation, 5)
        self.assertEqual(restarted.status_token, RESTART_RECOVERY)

    def test_classify_opend_connectivity_tokens(self) -> None:
        down = classify_opend_connectivity(
            OpenDReadiness(host="127.0.0.1", port=1, loopback=True, reachable=False)
        )
        self.assertEqual(down.status_token, OPEND_UNAVAILABLE)
        self.assertEqual(down.fallback.boundary_token, OVERLAY_ALLOWED)
        self.assertFalse(down.fallback.overlay_as_hop_l1)
        up = classify_opend_connectivity(
            OpenDReadiness(host="127.0.0.1", port=11111, loopback=True, reachable=True)
        )
        self.assertEqual(up.status_token, "OPEND_REACHABLE")


class AdapterResilienceMockTests(unittest.TestCase):
    def test_yahoo_empty_timeout_reset_malformed(self) -> None:
        empty = YahooDelayedEquityQuoteProvider(fetch=lambda url: (200, b""))
        self.assertEqual(empty.fetch_quote("AAPL").reason_code, EMPTY_PAYLOAD)

        def boom_timeout(_url: str) -> tuple[int, bytes]:
            raise TimeoutError("slow")

        timed = YahooDelayedEquityQuoteProvider(fetch=boom_timeout)
        self.assertEqual(timed.fetch_quote("AAPL").reason_code, PROVIDER_TIMEOUT)

        def boom_reset(_url: str) -> tuple[int, bytes]:
            raise ConnectionResetError("reset")

        reset = YahooDelayedEquityQuoteProvider(fetch=boom_reset)
        self.assertEqual(reset.fetch_quote("AAPL").reason_code, TEMPORARY_NETWORK_FAILURE)

        malformed = YahooDelayedEquityQuoteProvider(fetch=lambda url: (200, b"{not-json"))
        self.assertEqual(malformed.fetch_quote("AAPL").reason_code, "MALFORMED_RECORD")
        mapped = classify_provider_incident({"reason_code": "MALFORMED_RECORD"})
        self.assertEqual(mapped.status_token, MALFORMED_RESPONSE)

    def test_opend_empty_timeout_reset_with_loopback_listener(self) -> None:
        listener, host, port = _loopback_listener()
        try:
            with env(IMP_MOOMOO_HOST=host, IMP_MOOMOO_PORT=str(port)):
                empty = MoomooOpenDEquityQuoteProvider(
                    transport=_ScriptedOpenDTransport(OpenDSnapshotResult(row={}))
                ).fetch_quote("AAPL")
                timed = MoomooOpenDEquityQuoteProvider(
                    transport=_ScriptedOpenDTransport(TimeoutError("opend timeout"))
                ).fetch_quote("AAPL")
                reset = MoomooOpenDEquityQuoteProvider(
                    transport=_ScriptedOpenDTransport(ConnectionResetError("opend reset"))
                ).fetch_quote("AAPL")
        finally:
            listener.close()
        self.assertEqual(empty.reason_code, EMPTY_PAYLOAD)
        self.assertEqual(timed.reason_code, PROVIDER_TIMEOUT)
        self.assertEqual(reset.reason_code, TEMPORARY_NETWORK_FAILURE)
        self.assertEqual(empty.events, ())


class ReasonCodeProjectionTests(unittest.TestCase):
    def test_incident_for_reason_code_sdk_and_loopback_messages(self) -> None:
        sdk = incident_for_reason_code("MOOMOO_SDK_MISSING")
        self.assertEqual(sdk.status_token, "MOOMOO_SDK_MISSING")
        self.assertIn("vendor SDK", sdk.operator_message)
        self.assertFalse(sdk.fallback.overlay_as_hop_l1)
        blocked = incident_for_reason_code("OPEND_NON_LOOPBACK_BLOCKED")
        self.assertIn("loopback", blocked.operator_message.lower())

    def test_build_provider_error_payload_is_additive(self) -> None:
        payload = build_provider_error_payload(OPEND_UNAVAILABLE)
        self.assertEqual(payload["reason_code"], OPEND_UNAVAILABLE)
        self.assertEqual(payload["error_category"], CanonicalErrorCategory.PROVIDER_UNAVAILABLE.value)
        self.assertEqual(payload["operator_explanation"], payload["error"])
        self.assertFalse(payload["overlay_as_hop_l1"])
        self.assertEqual(payload["live_execution"], "OFF")
        self.assertEqual(payload["item9_mode"], "IDLE")

    def test_discovery_operator_view_when_opend_down(self) -> None:
        with unreachable_opend_env():
            _, discovery = discover_equity_quote_stack()
        view = equity_quote_discovery_operator_view(discovery)
        self.assertEqual(view["reason_code"], OPEND_UNAVAILABLE)
        self.assertIn("not hop L1", view["operator_explanation"])
        self.assertFalse(view["fallback"]["overlay_as_hop_l1"])
        self.assertEqual(view["item9_mode"], "IDLE")


class DiagnosticAndTaxonomyTests(unittest.TestCase):
    def test_runtime_diagnostic_exposes_operator_tokens(self) -> None:
        readiness = OpenDReadiness(host="127.0.0.1", port=1, loopback=True, reachable=False)
        with tempfile.TemporaryDirectory() as tmp:
            imp_root = Path(tmp)
            (imp_root / "phase0-dependency-lock.json").write_text("{}", encoding="utf-8")
            with patch(
                "market_platform_foundation.operations.runtime_resilience_diagnostic.opend_readiness",
                return_value=readiness,
            ):
                report = build_runtime_resilience_diagnostic(
                    imp_root,
                    active_collector_probe=lambda: (False, []),
                )
        connectivity = report["provider_connectivity"]
        self.assertEqual(connectivity["status_token"], OPEND_UNAVAILABLE)
        self.assertIn("Yahoo delayed overlay is not hop L1", connectivity["operator_message"])
        self.assertFalse(connectivity["fallback"]["overlay_as_hop_l1"])
        self.assertEqual(connectivity["live_execution"], "OFF")
        self.assertEqual(connectivity["item9_mode"], "IDLE")
        self.assertEqual(connectivity["item9_calibration"], "NOT_CALIBRATED")

    def test_reason_codes_map_to_canonical_categories(self) -> None:
        samples = {
            OPEND_UNAVAILABLE: CanonicalErrorCategory.PROVIDER_UNAVAILABLE,
            EMPTY_PAYLOAD: CanonicalErrorCategory.PROVIDER_UNAVAILABLE,
            TEMPORARY_NETWORK_FAILURE: CanonicalErrorCategory.PROVIDER_UNAVAILABLE,
            PROVIDER_TIMEOUT: CanonicalErrorCategory.TIMEOUT,
            MALFORMED_RESPONSE: CanonicalErrorCategory.PROVIDER_REJECTED,
            PARTIALLY_STALE: CanonicalErrorCategory.STALE_DATA,
            DELAYED_DATA: CanonicalErrorCategory.STALE_DATA,
            SOURCE_DISAGREEMENT: CanonicalErrorCategory.PROVIDER_REJECTED,
            FALLBACK_BLOCKED: CanonicalErrorCategory.UNSUPPORTED_CAPABILITY,
        }
        for code, category in samples.items():
            with self.subTest(code):
                self.assertEqual(canonical_error_category(code), category)


if __name__ == "__main__":
    unittest.main()
