from __future__ import annotations

import socket
import unittest

from market_platform_foundation.market_data.live_runtime import LiveObservationalRuntime
from market_platform_foundation.market_data.provider_lifecycle import ProviderConnectionState
from market_platform_foundation.platform.operator_diagnostics.service_liveness import (
    classify_loopback_service_liveness,
    classify_observational_market_data_liveness,
    classify_platform_services_liveness,
    compose_readiness_vs_liveness,
)


class RuntimeServiceLivenessTests(unittest.TestCase):
    def test_healthy_progress_when_subscribed_and_receiving(self) -> None:
        view = classify_observational_market_data_liveness(
            live_enabled=True,
            moomoo_configured=True,
            provider_id="moomoo.opend.observational",
            provider_role="MARKET_DATA",
            process_id=1234,
            connection_state="CONNECTED",
            opend_loopback_reachable=True,
            probe_stale=False,
            receiving=True,
            entitled=True,
            active_subscription_count=1,
            last_successful_event_ns=1,
            max_subscribed_freshness_ms=100,
            quote_stale_threshold_ms=5000,
        )
        self.assertEqual(view["status"], "HEALTHY")
        self.assertTrue(view["healthy"])

    def test_terminal_failure_provider_down(self) -> None:
        view = classify_observational_market_data_liveness(
            live_enabled=True,
            moomoo_configured=True,
            provider_id="moomoo.opend.observational",
            provider_role="MARKET_DATA",
            process_id=1234,
            connection_state="DISCONNECTED",
            opend_loopback_reachable=False,
            probe_stale=False,
            receiving=False,
            entitled=False,
            active_subscription_count=0,
            last_successful_event_ns=None,
            max_subscribed_freshness_ms=None,
            quote_stale_threshold_ms=5000,
        )
        self.assertEqual(view["status"], "PROVIDER_DOWN")
        self.assertFalse(view["healthy"])

    def test_http_dead_vs_port_bound_not_healthy(self) -> None:
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        _host, port = listener.getsockname()
        try:
            row = classify_loopback_service_liveness(
                service_name="api",
                port_bound=True,
                http_alive=False,
                process_alive=False,
                identity_owned=False,
            )
        finally:
            listener.close()
        self.assertTrue(row["port_bound"])
        self.assertEqual(row["status"], "UNAVAILABLE")
        self.assertFalse(row["healthy"])

        starting = classify_loopback_service_liveness(
            service_name="api",
            port_bound=True,
            http_alive=False,
            process_alive=True,
            identity_owned=True,
        )
        self.assertEqual(starting["status"], "UNREADY")
        self.assertEqual(starting["reason"], "TRANSPORT_UP_APPLICATION_NOT_PROGRESSED")
        self.assertFalse(starting["healthy"])

    def test_bound_port_without_progress_on_market_data(self) -> None:
        view = classify_observational_market_data_liveness(
            live_enabled=True,
            moomoo_configured=True,
            provider_id="moomoo.opend.observational",
            provider_role="MARKET_DATA",
            process_id=99,
            connection_state="CONNECTING",
            opend_loopback_reachable=True,
            probe_stale=False,
            receiving=False,
            entitled=True,
            active_subscription_count=0,
            last_successful_event_ns=None,
            max_subscribed_freshness_ms=None,
            quote_stale_threshold_ms=5000,
        )
        self.assertTrue(view["transport_up"])
        self.assertFalse(view["healthy"])
        self.assertEqual(view["status"], "UNREADY")

        bound_only = classify_observational_market_data_liveness(
            live_enabled=True,
            moomoo_configured=True,
            provider_id="moomoo.opend.observational",
            provider_role="MARKET_DATA",
            process_id=99,
            connection_state="DISABLED",
            opend_loopback_reachable=True,
            probe_stale=False,
            receiving=False,
            entitled=True,
            active_subscription_count=0,
            last_successful_event_ns=None,
            max_subscribed_freshness_ms=None,
            quote_stale_threshold_ms=5000,
        )
        self.assertEqual(bound_only["reason"], "TRANSPORT_UP_APPLICATION_NOT_PROGRESSED")
        self.assertNotEqual(bound_only["status"], "HEALTHY")

    def test_stale_heartbeat_when_subscribed_cycle_elapsed(self) -> None:
        view = classify_observational_market_data_liveness(
            live_enabled=True,
            moomoo_configured=True,
            provider_id="moomoo.opend.observational",
            provider_role="MARKET_DATA",
            process_id=1,
            connection_state="CONNECTED",
            opend_loopback_reachable=True,
            probe_stale=False,
            receiving=False,
            entitled=True,
            active_subscription_count=2,
            last_successful_event_ns=100,
            max_subscribed_freshness_ms=9000,
            quote_stale_threshold_ms=5000,
        )
        self.assertEqual(view["status"], "STALE")
        self.assertFalse(view["healthy"])

    def test_expected_idle_not_stale_without_subscription(self) -> None:
        view = classify_observational_market_data_liveness(
            live_enabled=True,
            moomoo_configured=True,
            provider_id="moomoo.opend.observational",
            provider_role="MARKET_DATA",
            process_id=1,
            connection_state="CONNECTED",
            opend_loopback_reachable=True,
            probe_stale=False,
            receiving=False,
            entitled=True,
            active_subscription_count=0,
            last_successful_event_ns=None,
            max_subscribed_freshness_ms=None,
            quote_stale_threshold_ms=5000,
        )
        self.assertEqual(view["status"], "NOT_APPLICABLE")
        self.assertEqual(view["expected_cycle"], "NOT_APPLICABLE")

    def test_probe_stale_dependency(self) -> None:
        view = classify_observational_market_data_liveness(
            live_enabled=True,
            moomoo_configured=True,
            provider_id="moomoo.opend.observational",
            provider_role="MARKET_DATA",
            process_id=1,
            connection_state="CONNECTED",
            opend_loopback_reachable=True,
            probe_stale=True,
            receiving=True,
            entitled=True,
            active_subscription_count=1,
            last_successful_event_ns=1,
            max_subscribed_freshness_ms=10,
            quote_stale_threshold_ms=5000,
        )
        self.assertEqual(view["status"], "PROBE_STALE")
        self.assertFalse(view["healthy"])

    def test_runtime_observational_liveness_view_after_fixture(self) -> None:
        from market_platform_foundation.market_data.capability_registry import ProviderDimensions

        runtime = LiveObservationalRuntime()
        runtime.lifecycle.connection_state = ProviderConnectionState.CONNECTED
        runtime.lifecycle.record_event(1_000_000)
        runtime.capability_registry.is_stale = False
        runtime.capability_registry.dimensions = ProviderDimensions(
            configured=True,
            connected=True,
            entitled=True,
            receiving=True,
            healthy=True,
        )
        view = runtime.observational_liveness_view()
        self.assertEqual(view["provider_role"], "MARKET_DATA")
        self.assertIn("process_id", view)

    def test_compose_readiness_vs_liveness_restart_stable(self) -> None:
        resilience = {
            "readiness_vs_liveness": {
                "readiness": {"item9_status": "IDLE"},
                "liveness": {"provider_reachable": True},
            }
        }
        lifecycle = {
            "services": [
                {
                    "name": "api",
                    "health": {
                        "port_bound": True,
                        "http_alive": True,
                        "process_alive": True,
                        "identity_owned": True,
                    },
                }
            ]
        }
        provider_health = {
            "service_liveness": {
                "status": "NOT_APPLICABLE",
                "healthy": False,
            }
        }
        first = compose_readiness_vs_liveness(
            resilience=resilience,
            lifecycle=lifecycle,
            provider_health=provider_health,
        )
        second = compose_readiness_vs_liveness(
            resilience=resilience,
            lifecycle=lifecycle,
            provider_health=provider_health,
        )
        self.assertEqual(first, second)
        self.assertEqual(first["liveness"]["platform_status"], "HEALTHY")

    def test_platform_partial_when_any_service_unready(self) -> None:
        payload = classify_platform_services_liveness(
            [
                {
                    "name": "api",
                    "health": {
                        "port_bound": True,
                        "http_alive": True,
                        "process_alive": True,
                        "identity_owned": True,
                    },
                },
                {
                    "name": "ui",
                    "health": {
                        "port_bound": True,
                        "http_alive": False,
                        "process_alive": True,
                        "identity_owned": True,
                    },
                },
            ]
        )
        self.assertEqual(payload["status"], "UNREADY")


if __name__ == "__main__":
    unittest.main()
