from __future__ import annotations

import importlib.util
import socket
import sys
import types
import unittest
from pathlib import Path


def _load_service_liveness():
    """Load service_liveness without executing operator_diagnostics.__init__.

    Package ``__init__`` pulls snapshot → local_state and hits a circular import
    introduced by the durable opportunity book. Classifier unit tests must not
    depend on that package side effect. Parent packages stay real imports.
    """
    module_name = "market_platform_foundation.platform.operator_diagnostics.service_liveness"
    if module_name in sys.modules:
        return sys.modules[module_name]

    import market_platform_foundation.platform  # noqa: F401 — real parents only

    repo_src = Path(__file__).resolve().parents[2] / "src"
    pkg_name = "market_platform_foundation.platform.operator_diagnostics"
    if pkg_name not in sys.modules:
        stub = types.ModuleType(pkg_name)
        stub.__path__ = [
            str(repo_src / "market_platform_foundation" / "platform" / "operator_diagnostics")
        ]
        sys.modules[pkg_name] = stub

    path = (
        repo_src
        / "market_platform_foundation"
        / "platform"
        / "operator_diagnostics"
        / "service_liveness.py"
    )
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load service_liveness from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_sl = _load_service_liveness()
classify_loopback_service_liveness = _sl.classify_loopback_service_liveness
classify_observational_market_data_liveness = _sl.classify_observational_market_data_liveness
classify_platform_services_liveness = _sl.classify_platform_services_liveness
compose_readiness_vs_liveness = _sl.compose_readiness_vs_liveness


def _market_view(**overrides: object) -> dict:
    payload = {
        "live_enabled": True,
        "moomoo_configured": True,
        "provider_id": "moomoo.opend.observational",
        "provider_role": "MARKET_DATA",
        "process_id": 1234,
        "connection_state": "CONNECTED",
        "opend_loopback_reachable": True,
        "probe_stale": False,
        "receiving": True,
        "entitled": True,
        "active_subscription_count": 1,
        "last_successful_event_ns": 1,
        "max_subscribed_freshness_ms": 100,
        "quote_stale_threshold_ms": 5000,
    }
    payload.update(overrides)
    return classify_observational_market_data_liveness(**payload)  # type: ignore[arg-type]


class RuntimeServiceLivenessTests(unittest.TestCase):
    def test_healthy_progress_when_subscribed_and_receiving(self) -> None:
        view = _market_view()
        self.assertEqual(view["status"], "HEALTHY")
        self.assertTrue(view["healthy"])

    def test_terminal_failure_provider_down(self) -> None:
        view = _market_view(
            connection_state="DISCONNECTED",
            opend_loopback_reachable=False,
            receiving=False,
            entitled=False,
            active_subscription_count=0,
            last_successful_event_ns=None,
            max_subscribed_freshness_ms=None,
        )
        self.assertEqual(view["status"], "PROVIDER_DOWN")
        self.assertFalse(view["healthy"])

    def test_http_dead_vs_port_bound_not_healthy(self) -> None:
        """Bound TCP listener is transport-up; HTTP-dead / process-dead stay non-HEALTHY."""
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        host, port = listener.getsockname()
        try:
            # Prove the port is actually bound: connect succeeds (transport up).
            probe = socket.create_connection((host, port), timeout=0.5)
            probe.close()

            zombie = classify_loopback_service_liveness(
                service_name="api",
                port_bound=True,
                http_alive=False,
                process_alive=False,
                identity_owned=False,
            )
            self.assertTrue(zombie["port_bound"])
            self.assertTrue(zombie["transport_up"])
            self.assertEqual(zombie["status"], "UNAVAILABLE")
            self.assertEqual(zombie["reason"], "PORT_BOUND_WITHOUT_PROCESS")
            self.assertFalse(zombie["healthy"])

            # Process alive + owned identity, port bound, HTTP dead: not HEALTHY.
            http_dead = classify_loopback_service_liveness(
                service_name="api",
                port_bound=True,
                http_alive=False,
                process_alive=True,
                identity_owned=True,
            )
            self.assertEqual(http_dead["status"], "UNREADY")
            self.assertEqual(http_dead["reason"], "TRANSPORT_UP_APPLICATION_NOT_PROGRESSED")
            self.assertFalse(http_dead["healthy"])
            self.assertFalse(http_dead["application_progress"])
        finally:
            listener.close()

    def test_process_identity_mismatch_not_healthy(self) -> None:
        """Platform service identity participates in classification."""
        row = classify_loopback_service_liveness(
            service_name="api",
            port_bound=True,
            http_alive=True,
            process_alive=True,
            identity_owned=False,
        )
        self.assertEqual(row["status"], "UNREADY")
        self.assertEqual(row["reason"], "PROCESS_IDENTITY_MISMATCH")
        self.assertFalse(row["healthy"])
        self.assertFalse(row["application_progress"])

    def test_bound_port_without_progress_on_market_data(self) -> None:
        view = _market_view(
            process_id=99,
            connection_state="CONNECTING",
            receiving=False,
            active_subscription_count=0,
            last_successful_event_ns=None,
            max_subscribed_freshness_ms=None,
        )
        self.assertTrue(view["transport_up"])
        self.assertFalse(view["healthy"])
        self.assertEqual(view["status"], "UNREADY")

        bound_only = _market_view(
            process_id=99,
            connection_state="DISABLED",
            receiving=False,
            active_subscription_count=0,
            last_successful_event_ns=None,
            max_subscribed_freshness_ms=None,
        )
        self.assertEqual(bound_only["reason"], "TRANSPORT_UP_APPLICATION_NOT_PROGRESSED")
        self.assertNotEqual(bound_only["status"], "HEALTHY")

    def test_stale_heartbeat_when_subscribed_cycle_elapsed(self) -> None:
        view = _market_view(
            process_id=1,
            receiving=False,
            active_subscription_count=2,
            last_successful_event_ns=100,
            max_subscribed_freshness_ms=9000,
        )
        self.assertEqual(view["status"], "STALE")
        self.assertFalse(view["healthy"])

    def test_receiving_true_stale_when_freshness_past_threshold(self) -> None:
        view = _market_view(
            receiving=True,
            active_subscription_count=2,
            last_successful_event_ns=100,
            max_subscribed_freshness_ms=9000,
            quote_stale_threshold_ms=5000,
        )
        self.assertEqual(view["status"], "STALE")
        self.assertEqual(view["reason"], "QUOTE_STALE")
        self.assertTrue(view["application_progress"])
        self.assertFalse(view["healthy"])

    def test_subscribed_receiving_without_freshness_fail_closed(self) -> None:
        view = _market_view(
            receiving=True,
            active_subscription_count=1,
            last_successful_event_ns=1,
            max_subscribed_freshness_ms=None,
        )
        self.assertEqual(view["status"], "UNAVAILABLE")
        self.assertEqual(view["reason"], "FRESHNESS_UNAVAILABLE")
        self.assertFalse(view["healthy"])

    def test_subscribed_not_receiving_without_freshness_fail_closed(self) -> None:
        view = _market_view(
            receiving=False,
            active_subscription_count=1,
            last_successful_event_ns=50,
            max_subscribed_freshness_ms=None,
        )
        self.assertEqual(view["status"], "UNAVAILABLE")
        self.assertEqual(view["reason"], "FRESHNESS_UNAVAILABLE")
        self.assertFalse(view["healthy"])

    def test_expected_idle_not_stale_without_subscription(self) -> None:
        view = _market_view(
            process_id=1,
            receiving=False,
            active_subscription_count=0,
            last_successful_event_ns=None,
            max_subscribed_freshness_ms=None,
        )
        self.assertEqual(view["status"], "NOT_APPLICABLE")
        self.assertEqual(view["expected_cycle"], "NOT_APPLICABLE")
        self.assertFalse(view["healthy"])

    def test_receiving_with_zero_subscriptions_not_healthy(self) -> None:
        view = _market_view(
            receiving=True,
            active_subscription_count=0,
            last_successful_event_ns=1,
            max_subscribed_freshness_ms=10,
        )
        self.assertEqual(view["status"], "NOT_APPLICABLE")
        self.assertEqual(view["reason"], "NO_ACTIVE_SUBSCRIPTION_CYCLE")
        self.assertFalse(view["healthy"])
        self.assertFalse(view["application_progress"])

    def test_subscribed_not_entitled_unready(self) -> None:
        view = _market_view(entitled=False, receiving=True, active_subscription_count=1)
        self.assertEqual(view["status"], "UNREADY")
        self.assertEqual(view["reason"], "NOT_ENTITLED")
        self.assertFalse(view["healthy"])

    def test_probe_stale_dependency(self) -> None:
        view = _market_view(probe_stale=True, max_subscribed_freshness_ms=10)
        self.assertEqual(view["status"], "PROBE_STALE")
        self.assertFalse(view["healthy"])

    def test_market_data_process_id_is_diagnostic_only(self) -> None:
        """Serving-process PID must not flip HEALTHY when freshness is good."""
        with_pid = _market_view(process_id=99999)
        without_pid = _market_view(process_id=None)
        self.assertEqual(with_pid["status"], without_pid["status"])
        self.assertEqual(with_pid["healthy"], without_pid["healthy"])
        self.assertEqual(with_pid["status"], "HEALTHY")

    def test_runtime_observational_liveness_view_after_fixture(self) -> None:
        # Import after classifier is registered so lazy import inside the view
        # resolves to the preloaded module without executing package __init__.
        from market_platform_foundation.market_data.capability_registry import ProviderDimensions
        from market_platform_foundation.market_data.live_runtime import LiveObservationalRuntime
        from market_platform_foundation.market_data.provider_lifecycle import ProviderConnectionState

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
        # Fixture has zero active subscriptions: expected idle, not HEALTHY.
        self.assertEqual(view["status"], "NOT_APPLICABLE")
        self.assertEqual(view["expected_cycle"], "NOT_APPLICABLE")
        self.assertFalse(view["healthy"])

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
