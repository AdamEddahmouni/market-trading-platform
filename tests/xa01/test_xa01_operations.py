"""XA-01 operations and registry validation tests."""

from __future__ import annotations

import unittest

from market_platform_foundation.xa01.compatibility import register_equity
from market_platform_foundation.xa01.operations import execute
from market_platform_foundation.xa01.registry import InstrumentRegistry, configure_registry, reset_registry_for_tests


class Xa01OperationsTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_registry_for_tests()

    def test_operations_status_and_validate(self) -> None:
        registry = InstrumentRegistry()
        configure_registry(registry)
        register_equity(symbol="AAPL", registry=registry)
        status = execute("XA01.OP.STATUS")
        self.assertEqual(status.outcome_code, "OK")
        validate = execute("XA01.OP.VALIDATE_REGISTRY")
        self.assertEqual(validate.outcome_code, "OK")
        domains = execute("XA01.OP.LIST_DOMAINS")
        self.assertIn("COMMODITY", domains.verification["domains"])
