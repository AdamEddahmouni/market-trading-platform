"""Regression tests for donor availability probe timeout and cache."""

from __future__ import annotations

import time
import unittest
from unittest import mock

from market_platform_foundation.donor_bridge import futures_client, squeeze_client


class DonorAvailabilityProbeTests(unittest.TestCase):
    def setUp(self) -> None:
        squeeze_client.clear_availability_probe_cache()
        futures_client.clear_availability_probe_cache()

    def tearDown(self) -> None:
        squeeze_client.clear_availability_probe_cache()
        futures_client.clear_availability_probe_cache()

    def test_squeeze_is_available_uses_short_probe_timeout(self) -> None:
        with mock.patch.object(
            squeeze_client,
            "fetch_health",
            side_effect=ConnectionError("offline"),
        ) as fetch_health:
            self.assertFalse(squeeze_client.is_available())
            fetch_health.assert_called_once()
            self.assertEqual(
                fetch_health.call_args.kwargs.get("timeout"),
                squeeze_client.AVAILABILITY_PROBE_TIMEOUT,
            )

    def test_squeeze_probe_cache_avoids_repeat_health_checks(self) -> None:
        with mock.patch.object(
            squeeze_client,
            "fetch_health",
            return_value={"status": "OK"},
        ) as fetch_health:
            self.assertTrue(squeeze_client.is_available())
            self.assertTrue(squeeze_client.is_available())
            fetch_health.assert_called_once()

    def test_futures_probe_cache_avoids_repeat_health_checks(self) -> None:
        with mock.patch.object(
            futures_client,
            "fetch_json",
            return_value={"status": "OK"},
        ) as fetch_json:
            self.assertTrue(futures_client.is_available())
            self.assertTrue(futures_client.is_available())
            fetch_json.assert_called_once()
            self.assertEqual(
                fetch_json.call_args.kwargs.get("timeout"),
                futures_client.AVAILABILITY_PROBE_TIMEOUT,
            )


if __name__ == "__main__":
    unittest.main()
