"""Regression: offline unit tests must not depend on live OpenD or installed SDK."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from market_platform_foundation.providers.adapters.moomoo_opend_equity_quote import (  # noqa: E402
    OPEND_UNAVAILABLE,
    MoomooOpenDEquityQuoteProvider,
)
from market_platform_foundation.providers.equity_quote_selection import opend_readiness  # noqa: E402
from tests.support.hermetic_environment import (  # noqa: E402
    cleared_moomoo_endpoint_env,
    unreachable_opend_env,
    vendor_sdk_absent,
)


class OfflineOpenDHermeticityTests(unittest.TestCase):
    def test_readiness_unreachable_with_injected_closed_port(self) -> None:
        with unreachable_opend_env():
            readiness = opend_readiness()
        self.assertTrue(readiness.loopback)
        self.assertFalse(readiness.reachable)

    def test_fetch_quote_fail_closed_when_opend_injected_unreachable(self) -> None:
        with cleared_moomoo_endpoint_env():
            result = MoomooOpenDEquityQuoteProvider().fetch_quote("AAPL")
        self.assertEqual(result.status, "unavailable")
        self.assertEqual(result.reason_code, OPEND_UNAVAILABLE)

    def test_sdk_absent_injection_does_not_require_uninstalling_moomoo_api(self) -> None:
        from tools.moomoo.opend_quote_transport import MOOMOO_SDK_MISSING, fetch_snapshot

        with vendor_sdk_absent(), unreachable_opend_env():
            payload = fetch_snapshot("AAPL", host="127.0.0.1", port=1)
        self.assertEqual(payload["reason_code"], MOOMOO_SDK_MISSING)


if __name__ == "__main__":
    unittest.main()
