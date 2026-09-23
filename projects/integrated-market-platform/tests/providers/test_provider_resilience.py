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
    MISSING_TIMESTAMP,
    MOOMOO_LAST_PRICE_MISSING,
    MOOMOO_OPEND_PROVIDER_ID,
    MOOMOO_PROTOCOL_ERROR,
    MOOMOO_SDK_MISSING,
    MOOMOO_TRANSPORT_NOT_IMPLEMENTED,
    PROVIDER_TIMEOUT,
    TEMPORARY_NETWORK_FAILURE,
    MoomooOpenDEquityQuoteProvider,
    OpenDSnapshotResult,
    VendorSdkOpenDQuoteTransport,
)
from market_platform_foundation.providers.adapters.yahoo_delayed_equity_quote import (  # noqa: E402
    MALFORMED_RECORD,
    RATE_LIMIT,
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
    HEALTHY,
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
    classify_source_disagreement,
    failure_receipt_from_provider_result,
    fallback_for_primary,
    incident_for_reason_code,
    normalize_reason_token,
    note_disconnect,
    note_process_restart,
    note_reconnect,
    project_provider_failure_receipt,
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

    def test_incident_for_reason_code_novel_tokens_fail_closed(self) -> None:
        novel = incident_for_reason_code("VENDOR_FUTURE_REASON_XYZ")
        self.assertEqual(novel.status_token, "UNKNOWN")
        self.assertEqual(novel.severity, "UNAVAILABLE")
        self.assertFalse(novel.fallback.overlay_as_hop_l1)
        self.assertEqual(novel.fallback.boundary_token, OVERLAY_ALLOWED)
        self.assertEqual(novel.details["source_reason_code"], "VENDOR_FUTURE_REASON_XYZ")
        empty = incident_for_reason_code(None)
        self.assertEqual(empty.status_token, "UNKNOWN")
        self.assertEqual(empty.severity, "UNAVAILABLE")

    def test_incident_for_reason_code_known_primary_available_only(self) -> None:
        configured = incident_for_reason_code("OPEND_SDK_PRESENT")
        self.assertEqual(configured.status_token, "OPEND_SDK_PRESENT")
        self.assertEqual(configured.severity, "HEALTHY")
        self.assertEqual(configured.fallback.boundary_token, OVERLAY_ALLOWED)
        reconnecting = incident_for_reason_code(RECONNECTING)
        self.assertEqual(reconnecting.status_token, RECONNECTING)
        self.assertEqual(reconnecting.severity, "RECOVERING")
        self.assertEqual(reconnecting.fallback.boundary_token, OVERLAY_ALLOWED)

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

    def test_reconnect_and_opend_reject_codes_are_not_internal_errors(self) -> None:
        samples = {
            RECONNECTING: CanonicalErrorCategory.PROVIDER_UNAVAILABLE,
            RESTART_RECOVERY: CanonicalErrorCategory.PROVIDER_UNAVAILABLE,
            MOOMOO_PROTOCOL_ERROR: CanonicalErrorCategory.PROVIDER_REJECTED,
            MOOMOO_LAST_PRICE_MISSING: CanonicalErrorCategory.PROVIDER_REJECTED,
            MISSING_TIMESTAMP: CanonicalErrorCategory.PROVIDER_REJECTED,
            RATE_LIMIT: CanonicalErrorCategory.RATE_LIMITED,
            MOOMOO_TRANSPORT_NOT_IMPLEMENTED: CanonicalErrorCategory.PROVIDER_UNAVAILABLE,
        }
        for code, category in samples.items():
            with self.subTest(code):
                self.assertEqual(canonical_error_category(code), category)
                self.assertNotEqual(canonical_error_category(code), CanonicalErrorCategory.INTERNAL_ERROR)


class RemainingFailureBoundaryTests(unittest.TestCase):
    def test_reason_aliases_normalize_without_inventing_ticks(self) -> None:
        aliases = {
            "TIMEOUT": PROVIDER_TIMEOUT,
            "REQUEST_TIMEOUT": PROVIDER_TIMEOUT,
            "STALE": PARTIALLY_STALE,
            "TTL_EXCEEDED": PARTIALLY_STALE,
            "ECONNRESET": TEMPORARY_NETWORK_FAILURE,
            "PROVIDER_UNREACHABLE": OPEND_UNAVAILABLE,
            "LIVE_CONNECTED_NO_DATA": EMPTY_PAYLOAD,
            MALFORMED_RECORD: MALFORMED_RESPONSE,
        }
        for raw, expected in aliases.items():
            with self.subTest(raw):
                self.assertEqual(normalize_reason_token(raw), expected)
                incident = incident_for_reason_code(raw)
                self.assertEqual(incident.status_token, expected)
                self.assertTrue(incident.operator_message)
                self.assertFalse(incident.fallback.overlay_as_hop_l1)
                self.assertEqual(incident.live_execution, "OFF")

    def test_protocol_error_keeps_specific_operator_explanation(self) -> None:
        incident = incident_for_reason_code(MOOMOO_PROTOCOL_ERROR)
        self.assertEqual(incident.status_token, MOOMOO_PROTOCOL_ERROR)
        self.assertIn("protocol", incident.operator_message.lower())
        self.assertFalse(incident.fallback.overlay_as_hop_l1)
        payload = build_provider_error_payload(MOOMOO_PROTOCOL_ERROR)
        self.assertEqual(payload["reason_code"], MOOMOO_PROTOCOL_ERROR)
        self.assertEqual(payload["provider_status_token"], MOOMOO_PROTOCOL_ERROR)
        self.assertEqual(payload["operator_explanation"], incident.operator_message)
        self.assertEqual(payload["item9_mode"], "IDLE")

    def test_missing_timestamp_explains_fail_closed_without_unknown(self) -> None:
        incident = incident_for_reason_code(MISSING_TIMESTAMP)
        self.assertEqual(incident.status_token, MISSING_TIMESTAMP)
        self.assertNotEqual(incident.status_token, "UNKNOWN")
        self.assertIn("timestamp", incident.operator_message.lower())
        self.assertIn("receive time is not substituted", incident.operator_message.lower())

    def test_fallback_never_promotes_overlay_even_when_primary_is_down(self) -> None:
        overlay_ok = fallback_for_primary(
            primary_available=False, overlay_available=True, promote_overlay_to_l1=False
        )
        self.assertFalse(overlay_ok.overlay_as_hop_l1)
        self.assertTrue(overlay_ok.overlay_role_allowed)
        self.assertEqual(overlay_ok.boundary_token, OVERLAY_ALLOWED)
        blocked = fallback_for_primary(
            primary_available=False, overlay_available=False, promote_overlay_to_l1=False
        )
        self.assertFalse(blocked.overlay_as_hop_l1)
        self.assertFalse(blocked.overlay_role_allowed)
        self.assertEqual(blocked.boundary_token, FALLBACK_BLOCKED)
        promote = fallback_for_primary(
            primary_available=False, overlay_available=True, promote_overlay_to_l1=True
        )
        self.assertFalse(promote.overlay_as_hop_l1)
        self.assertEqual(promote.boundary_token, FALLBACK_BLOCKED)

    def test_incomplete_source_comparison_is_stale_not_healthy_or_merged(self) -> None:
        incomplete = classify_source_disagreement({"primary_last_price": 10.0})
        self.assertEqual(incomplete.status_token, PARTIALLY_STALE)
        self.assertNotEqual(incomplete.status_token, HEALTHY)
        self.assertFalse(incomplete.details["merged"])
        self.assertFalse(incomplete.details["fabricated_fields"])
        self.assertTrue(incomplete.details["incomplete_comparison"])
        agree = classify_source_disagreement(
            {"primary_last_price": 10.0, "overlay_last_price": 10.0, "tolerance": 0.01}
        )
        self.assertEqual(agree.status_token, HEALTHY)
        self.assertFalse(agree.details["merged"])

    def test_reconnect_generation_is_not_prior_session(self) -> None:
        prior = ProviderSessionState(generation=7, connected=True, status_token=HEALTHY)
        dropped = note_disconnect(prior)
        recovered = note_reconnect(dropped)
        self.assertEqual(dropped.generation, 7)
        self.assertNotEqual(recovered.generation, prior.generation)
        self.assertEqual(recovered.generation, 8)
        self.assertEqual(recovered.status_token, RESTART_RECOVERY)
        self.assertNotEqual(recovered.status_token, HEALTHY)
        payload = incident_for_reason_code(RECONNECTING).to_dict()
        self.assertEqual(payload["status_token"], RECONNECTING)
        self.assertIn("prior-generation", payload["operator_message"].lower())
        self.assertEqual(payload["live_execution"], "OFF")
        self.assertEqual(payload["item9_calibration"], "NOT_CALIBRATED")

    def test_discovery_sdk_missing_operator_view_does_not_promote_overlay(self) -> None:
        listener, host, port = _loopback_listener()
        try:
            with env(IMP_MOOMOO_HOST=host, IMP_MOOMOO_PORT=str(port)):
                with patch(
                    "market_platform_foundation.providers.equity_quote_discovery.opend_sdk_available",
                    return_value=False,
                ):
                    _, discovery = discover_equity_quote_stack()
        finally:
            listener.close()
        view = equity_quote_discovery_operator_view(discovery)
        self.assertEqual(view["reason_code"], MOOMOO_SDK_MISSING)
        self.assertIn("vendor SDK", view["operator_explanation"])
        self.assertFalse(view["fallback"]["overlay_as_hop_l1"])
        self.assertEqual(view["item9_mode"], "IDLE")
        self.assertEqual(view["live_execution"], "OFF")


class AdapterGapMockTests(unittest.TestCase):
    def test_opend_nan_last_price_is_not_filled_from_bid_ask(self) -> None:
        listener, host, port = _loopback_listener()
        row = {
            "code": "US.AAPL",
            "last_price": "nan",
            "bid_price": 191.0,
            "ask_price": 191.2,
            "update_time": "2026-09-12 15:59:00.000",
        }
        try:
            with env(IMP_MOOMOO_HOST=host, IMP_MOOMOO_PORT=str(port)):
                result = MoomooOpenDEquityQuoteProvider(
                    transport=_ScriptedOpenDTransport(OpenDSnapshotResult(row=row))
                ).fetch_quote("AAPL")
        finally:
            listener.close()
        self.assertEqual(result.reason_code, MOOMOO_LAST_PRICE_MISSING)
        self.assertEqual(result.events, ())

    def test_opend_malformed_protocol_row_fails_closed(self) -> None:
        listener, host, port = _loopback_listener()
        try:
            with env(IMP_MOOMOO_HOST=host, IMP_MOOMOO_PORT=str(port)):
                result = MoomooOpenDEquityQuoteProvider(
                    transport=_ScriptedOpenDTransport(
                        OpenDSnapshotResult(reason_code=MOOMOO_PROTOCOL_ERROR)
                    )
                ).fetch_quote("AAPL")
        finally:
            listener.close()
        self.assertEqual(result.reason_code, MOOMOO_PROTOCOL_ERROR)
        self.assertEqual(result.events, ())
        mapped = incident_for_reason_code(result.reason_code)
        self.assertEqual(mapped.status_token, MOOMOO_PROTOCOL_ERROR)
        self.assertFalse(mapped.fallback.overlay_as_hop_l1)

    def test_opend_reachability_is_reprobed_per_call(self) -> None:
        listener, host, port = _loopback_listener()
        transport = _ScriptedOpenDTransport(OpenDSnapshotResult(reason_code=MOOMOO_SDK_MISSING))
        try:
            with env(IMP_MOOMOO_HOST=host, IMP_MOOMOO_PORT=str(port)):
                provider = MoomooOpenDEquityQuoteProvider(transport=transport)
                with patch(
                    "market_platform_foundation.providers.adapters.moomoo_opend_equity_quote.opend_reachable",
                    side_effect=[True, False],
                ):
                    first = provider.fetch_quote("AAPL")
                    second = provider.fetch_quote("AAPL")
        finally:
            listener.close()
        self.assertEqual(first.reason_code, MOOMOO_SDK_MISSING)
        self.assertEqual(second.reason_code, OPEND_UNAVAILABLE)
        self.assertEqual(second.events, ())

    def test_vendor_transport_maps_timeout_reset_empty_and_malformed(self) -> None:
        class _TimeoutModule:
            def fetch_snapshot(self, symbol: str, *, host: str, port: int) -> dict:
                raise TimeoutError("opend timeout")

        class _ResetModule:
            def fetch_snapshot(self, symbol: str, *, host: str, port: int) -> dict:
                raise ConnectionResetError("opend reset")

        class _MalformedModule:
            def fetch_snapshot(self, symbol: str, *, host: str, port: int) -> list:
                return ["not-a-dict"]

        class _EmptyModule:
            def fetch_snapshot(self, symbol: str, *, host: str, port: int) -> dict:
                return {"row": {}}

        transport = VendorSdkOpenDQuoteTransport()
        with patch(
            "market_platform_foundation.providers.adapters.moomoo_opend_equity_quote._load_tools_transport_module",
            return_value=_TimeoutModule(),
        ):
            self.assertEqual(
                transport.fetch_snapshot(symbol="AAPL", host="127.0.0.1", port=1).reason_code,
                PROVIDER_TIMEOUT,
            )
        with patch(
            "market_platform_foundation.providers.adapters.moomoo_opend_equity_quote._load_tools_transport_module",
            return_value=_ResetModule(),
        ):
            self.assertEqual(
                transport.fetch_snapshot(symbol="AAPL", host="127.0.0.1", port=1).reason_code,
                TEMPORARY_NETWORK_FAILURE,
            )
        with patch(
            "market_platform_foundation.providers.adapters.moomoo_opend_equity_quote._load_tools_transport_module",
            return_value=_MalformedModule(),
        ):
            self.assertEqual(
                transport.fetch_snapshot(symbol="AAPL", host="127.0.0.1", port=1).reason_code,
                MOOMOO_PROTOCOL_ERROR,
            )
        with patch(
            "market_platform_foundation.providers.adapters.moomoo_opend_equity_quote._load_tools_transport_module",
            return_value=_EmptyModule(),
        ):
            self.assertEqual(
                transport.fetch_snapshot(symbol="AAPL", host="127.0.0.1", port=1).reason_code,
                EMPTY_PAYLOAD,
            )

    def test_yahoo_disconnect_missing_timestamp_and_chart_error(self) -> None:
        def boom_os(_url: str) -> tuple[int, bytes]:
            raise OSError("overlay down")

        disconnected = YahooDelayedEquityQuoteProvider(fetch=boom_os).fetch_quote("AAPL")
        self.assertEqual(disconnected.reason_code, "PROVIDER_DISCONNECTED")
        self.assertEqual(disconnected.instrument_id, "AAPL")
        mapped = incident_for_reason_code(disconnected.reason_code)
        self.assertEqual(mapped.status_token, TEMPORARY_NETWORK_FAILURE)
        self.assertEqual(mapped.details.get("source_reason_code"), "PROVIDER_DISCONNECTED")
        self.assertFalse(mapped.fallback.overlay_as_hop_l1)
        disconnect_receipt = failure_receipt_from_provider_result(disconnected)
        self.assertEqual(disconnect_receipt["instrument_id"], "AAPL")
        self.assertEqual(disconnect_receipt["source_reason_code"], "PROVIDER_DISCONNECTED")
        self.assertEqual(disconnect_receipt["provider_status_token"], TEMPORARY_NETWORK_FAILURE)
        self.assertEqual(disconnect_receipt["evidence_class"], "SOFTWARE")

        no_time = {
            "chart": {
                "error": None,
                "result": [{"meta": {"regularMarketPrice": 191.2}, "timestamp": []}],
            }
        }
        missing = YahooDelayedEquityQuoteProvider(
            fetch=lambda url: (200, json.dumps(no_time).encode("utf-8"))
        ).fetch_quote("AAPL")
        self.assertEqual(missing.reason_code, "MISSING_TIMESTAMP")
        self.assertEqual(missing.events, ())

        chart_error = YahooDelayedEquityQuoteProvider(
            fetch=lambda url: (200, json.dumps({"chart": {"error": "denied", "result": None}}).encode("utf-8"))
        ).fetch_quote("AAPL")
        self.assertEqual(chart_error.reason_code, "PROVIDER_HTTP_ERROR")
        self.assertEqual(chart_error.events, ())
        self.assertEqual(chart_error.instrument_id, "AAPL")
        self.assertEqual(chart_error.details.get("chart_error"), "denied")
        http_incident = incident_for_reason_code(chart_error.reason_code)
        self.assertEqual(http_incident.status_token, "PROVIDER_HTTP_ERROR")
        self.assertNotEqual(http_incident.status_token, "UNKNOWN")
        self.assertEqual(http_incident.severity, "UNAVAILABLE")
        self.assertFalse(http_incident.fallback.overlay_as_hop_l1)
        http_payload = build_provider_error_payload(
            chart_error.reason_code,
            instrument_id=chart_error.instrument_id,
            details=chart_error.details,
            provider_id=chart_error.provider_id,
        )
        self.assertEqual(http_payload["provider_status_token"], "PROVIDER_HTTP_ERROR")
        self.assertEqual(http_payload["reason_code"], "PROVIDER_HTTP_ERROR")
        self.assertEqual(http_payload["instrument_id"], "AAPL")
        self.assertEqual(http_payload["failure_details"].get("chart_error"), "denied")
        self.assertEqual(
            canonical_error_category(chart_error.reason_code),
            CanonicalErrorCategory.PROVIDER_UNAVAILABLE,
        )
        self.assertNotEqual(
            canonical_error_category(chart_error.reason_code),
            CanonicalErrorCategory.INTERNAL_ERROR,
        )

        http_status = YahooDelayedEquityQuoteProvider(
            fetch=lambda url: (503, b"unavailable")
        ).fetch_quote("MSFT")
        self.assertEqual(http_status.reason_code, "PROVIDER_HTTP_ERROR")
        self.assertEqual(http_status.instrument_id, "MSFT")
        self.assertEqual(http_status.details.get("http_status"), 503)
        status_payload = build_provider_error_payload(
            http_status.reason_code,
            instrument_id=http_status.instrument_id,
            details=http_status.details,
        )
        self.assertEqual(status_payload["instrument_id"], "MSFT")
        self.assertEqual(status_payload["failure_details"]["http_status"], 503)

    def test_classify_provider_incident_ignores_primary_available_override(self) -> None:
        """Fixture flags must not mark primary L1 available on failure tokens."""
        incident = classify_provider_incident(
            {"reason_code": OPEND_UNAVAILABLE, "primary_available": True}
        )
        self.assertEqual(incident.status_token, OPEND_UNAVAILABLE)
        self.assertFalse(incident.fallback.overlay_as_hop_l1)
        self.assertEqual(incident.fallback.boundary_token, OVERLAY_ALLOWED)

    def test_classify_provider_incident_novel_reason_matches_incident_for_reason_code(self) -> None:
        novel = classify_provider_incident({"reason_code": "VENDOR_FUTURE_REASON_XYZ"})
        projected = incident_for_reason_code("VENDOR_FUTURE_REASON_XYZ")
        self.assertEqual(novel.status_token, projected.status_token)
        self.assertEqual(novel.status_token, "UNKNOWN")
        self.assertEqual(novel.details.get("source_reason_code"), "VENDOR_FUTURE_REASON_XYZ")

    def test_opend_failure_receipt_links_requested_symbol(self) -> None:
        listener, host, port = _loopback_listener()
        try:
            with env(IMP_MOOMOO_HOST=host, IMP_MOOMOO_PORT=str(port)):
                result = MoomooOpenDEquityQuoteProvider(
                    transport=_ScriptedOpenDTransport(
                        OpenDSnapshotResult(reason_code=MOOMOO_PROTOCOL_ERROR)
                    )
                ).fetch_quote("NVDA")
        finally:
            listener.close()
        self.assertEqual(result.reason_code, MOOMOO_PROTOCOL_ERROR)
        self.assertEqual(result.instrument_id, "NVDA")
        receipt = failure_receipt_from_provider_result(result)
        self.assertEqual(receipt["instrument_id"], "NVDA")
        self.assertEqual(receipt["provider_id"], MOOMOO_OPEND_PROVIDER_ID)
        self.assertEqual(receipt["provider_status_token"], MOOMOO_PROTOCOL_ERROR)
        self.assertEqual(receipt["evidence_class"], "SOFTWARE")
        self.assertEqual(receipt["live_execution"], "OFF")

    def test_project_provider_failure_receipt_preserves_alias_source(self) -> None:
        receipt = project_provider_failure_receipt(
            reason_code="PROVIDER_DISCONNECTED",
            provider_id=YAHOO_PROVIDER_ID,
            instrument_id="aapl",
            details={"http_status": 502},
        )
        self.assertEqual(receipt["instrument_id"], "AAPL")
        self.assertEqual(receipt["provider_status_token"], TEMPORARY_NETWORK_FAILURE)
        self.assertEqual(receipt["source_reason_code"], "PROVIDER_DISCONNECTED")
        self.assertEqual(receipt["failure_details"]["http_status"], 502)
        self.assertEqual(receipt["failure_details"]["source_reason_code"], "PROVIDER_DISCONNECTED")
        self.assertFalse(receipt["overlay_as_hop_l1"])


if __name__ == "__main__":
    unittest.main()
