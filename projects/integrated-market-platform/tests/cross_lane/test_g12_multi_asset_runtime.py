"""G12 — canonical multi-asset runtime domain projection regressions."""

from __future__ import annotations

import sys
import time
import unittest
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.cross_lane.multi_asset_runtime import (  # noqa: E402
    RuntimeProjectionRequest,
    build_api_projection,
    probe_risk_admission,
    project_portfolio_valuation,
    project_runtime_domain,
    project_runtime_from_store,
)
from market_platform_foundation.cross_lane.runtime_status import RuntimeDomainStatus  # noqa: E402
from market_platform_foundation.market_data.observational_state import ObservationalStateStore  # noqa: E402
from market_platform_foundation.portfolio.canonical import (  # noqa: E402
    MarkDataStatus,
    PortfolioPosition,
    QuantityUnit,
    ValuationMark,
)
from market_platform_foundation.risk.financial import UNSUPPORTED_RISK_MODEL  # noqa: E402
from market_platform_foundation.xa01.compatibility import (  # noqa: E402
    register_bond,
    register_commodity_economic,
    register_commodity_proxy,
    register_commodity_spot,
    register_continuous_futures_series,
    register_crypto_pair,
    register_future_contract,
    register_future_family,
    register_option_contract,
)
from market_platform_foundation.xa01.enums import InstrumentKind  # noqa: E402
from market_platform_foundation.xa01.registry import InstrumentRegistry, reset_registry_for_tests  # noqa: E402


class G12MultiAssetRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_registry_for_tests()
        self.registry = InstrumentRegistry()

    def _descriptor(self, canonical_id: str):
        return self.registry.get(canonical_id).descriptor

    def test_01_specific_future_contract_accepted(self) -> None:
        cid = register_future_contract(
            contract_id="ES202506",
            contract_multiplier="50",
            family_root="ES",
            expiration="2025-06-20",
            registry=self.registry,
        )
        req = RuntimeProjectionRequest(
            descriptor=self._descriptor(cid),
            price=5400.0,
            multiplier=50.0,
            provider="fixture",
        )
        projection = project_runtime_domain(req)
        self.assertEqual(projection.status, RuntimeDomainStatus.AVAILABLE)
        self.assertEqual(projection.domain_payload["multiplier"], 50.0)

    def test_02_future_family_rejected(self) -> None:
        fid = register_future_family(family_root="ES", registry=self.registry)
        req = RuntimeProjectionRequest(descriptor=self._descriptor(fid))
        projection = project_runtime_domain(req)
        self.assertEqual(projection.status, RuntimeDomainStatus.UNSUPPORTED_INSTRUMENT)

    def test_03_continuous_future_rejected(self) -> None:
        cid = register_continuous_futures_series(
            family_root="ES",
            methodology="unadjusted_continuous",
            registry=self.registry,
        )
        req = RuntimeProjectionRequest(descriptor=self._descriptor(cid))
        projection = project_runtime_domain(req)
        self.assertEqual(projection.status, RuntimeDomainStatus.UNSUPPORTED_INSTRUMENT)

    def test_04_futures_multiplier_mandatory(self) -> None:
        cid = register_future_contract(
            contract_id="ES202506",
            contract_multiplier="50",
            family_root="ES",
            expiration="2025-06-20",
            registry=self.registry,
        )
        descriptor = self._descriptor(cid)
        req = RuntimeProjectionRequest(descriptor=descriptor, price=5400.0, multiplier=None)
        # economics_from_descriptor supplies multiplier from registration.
        projection = project_runtime_domain(req)
        self.assertEqual(projection.domain_payload["multiplier"], 50.0)

    def test_05_option_contract_identity_specific(self) -> None:
        oid = register_option_contract(
            option_id="NVDA20250620C00120000",
            underlying_symbol="NVDA",
            expiration="2025-06-20",
            strike="120",
            call_put="call",
            registry=self.registry,
        )
        req = RuntimeProjectionRequest(
            descriptor=self._descriptor(oid),
            underlying_id="NVDA",
            multiplier=100.0,
            chain_status="available",
        )
        projection = project_runtime_domain(req)
        self.assertEqual(projection.status, RuntimeDomainStatus.AVAILABLE)
        self.assertEqual(projection.instrument_kind, InstrumentKind.OPTION_CONTRACT.value)

    def test_06_underlying_only_option_rejected(self) -> None:
        oid = register_option_contract(
            option_id="NVDA20250620C00120000",
            underlying_symbol="NVDA",
            expiration="2025-06-20",
            strike="120",
            call_put="call",
            registry=self.registry,
        )
        req = RuntimeProjectionRequest(
            descriptor=self._descriptor(oid),
            underlying_id=oid,
            chain_status="available",
        )
        projection = project_runtime_domain(req)
        self.assertEqual(projection.status, RuntimeDomainStatus.UNSUPPORTED_INSTRUMENT)

    def test_07_missing_chain_not_empty(self) -> None:
        oid = register_option_contract(
            option_id="NVDA20250620C00120000",
            underlying_symbol="NVDA",
            expiration="2025-06-20",
            strike="120",
            call_put="call",
            registry=self.registry,
        )
        req = RuntimeProjectionRequest(
            descriptor=self._descriptor(oid),
            underlying_id="NVDA",
            chain_status="missing",
        )
        projection = project_runtime_domain(req)
        self.assertEqual(projection.status, RuntimeDomainStatus.UNAVAILABLE)
        self.assertNotEqual(projection.status, RuntimeDomainStatus.EMPTY)

    def test_08_missing_greeks_iv_not_fabricated(self) -> None:
        oid = register_option_contract(
            option_id="NVDA20250620C00120000",
            underlying_symbol="NVDA",
            expiration="2025-06-20",
            strike="120",
            call_put="call",
            registry=self.registry,
        )
        req = RuntimeProjectionRequest(
            descriptor=self._descriptor(oid),
            underlying_id="NVDA",
            chain_status="available",
            greeks={"delta": None, "gamma": None},
            iv=None,
            open_interest=None,
        )
        projection = project_runtime_domain(req)
        self.assertIsNone(projection.domain_payload["iv"])
        self.assertIsNone(projection.domain_payload["open_interest"])
        self.assertIsNone(projection.domain_payload["greeks"]["delta"])

    def test_09_crypto_base_quote_isolation(self) -> None:
        a = register_crypto_pair(
            base_asset="BTC",
            quote_asset="USD",
            venue_id="COINBASE",
            registry=self.registry,
        )
        b = register_crypto_pair(
            base_asset="BTC",
            quote_asset="USDT",
            venue_id="COINBASE",
            registry=self.registry,
        )
        self.assertNotEqual(a, b)

    def test_10_usdt_not_silently_usd(self) -> None:
        cid = register_crypto_pair(
            base_asset="BTC",
            quote_asset="USDT",
            venue_id="COINBASE",
            registry=self.registry,
        )
        req = RuntimeProjectionRequest(
            descriptor=self._descriptor(cid),
            price=50000.0,
        )
        projection = project_runtime_domain(req)
        self.assertEqual(projection.reason, "QUOTE_NOT_FIAT_USD")
        self.assertIsNone(projection.domain_payload["fx_rate"])

    def test_11_bond_typed_identity_preserved(self) -> None:
        bid = register_bond(
            cusip="9128285M8",
            issuer="US_TREASURY",
            maturity_date="2030-05-15",
            coupon="2.5",
            registry=self.registry,
        )
        req = RuntimeProjectionRequest(descriptor=self._descriptor(bid))
        projection = project_runtime_domain(req)
        self.assertEqual(projection.domain_payload["cusip"], "9128285M8")
        self.assertEqual(projection.domain_payload["issuer"], "US_TREASURY")

    def test_12_commodity_reference_tradable_distinction(self) -> None:
        gold = register_commodity_economic(commodity_code="GOLD", registry=self.registry)
        spot = register_commodity_spot(
            commodity_code="XAU",
            quote_currency="USD",
            registry=self.registry,
        )
        proxy = register_commodity_proxy(symbol="GLD", commodity_code="GOLD", registry=self.registry)
        self.assertNotEqual(gold, spot)
        self.assertNotEqual(gold, proxy)
        gold_proj = project_runtime_domain(RuntimeProjectionRequest(descriptor=self._descriptor(gold)))
        proxy_proj = project_runtime_domain(RuntimeProjectionRequest(descriptor=self._descriptor(proxy)))
        self.assertFalse(gold_proj.execution_available)
        self.assertTrue(proxy_proj.execution_available)

    def test_13_no_fake_fx(self) -> None:
        cid = register_crypto_pair(
            base_asset="BTC",
            quote_asset="EUR",
            venue_id="COINBASE",
            registry=self.registry,
        )
        req = RuntimeProjectionRequest(
            descriptor=self._descriptor(cid),
            price=45000.0,
            fx_rate=None,
        )
        projection = project_runtime_domain(req)
        self.assertIsNone(projection.domain_payload["fx_rate"])

    def test_14_stale_mark_explicit(self) -> None:
        oid = register_option_contract(
            option_id="NVDA20250620C00120000",
            underlying_symbol="NVDA",
            expiration="2025-06-20",
            strike="120",
            call_put="call",
            registry=self.registry,
        )
        req = RuntimeProjectionRequest(
            descriptor=self._descriptor(oid),
            underlying_id="NVDA",
            chain_status="available",
            stale=True,
        )
        projection = project_runtime_domain(req)
        self.assertEqual(projection.status, RuntimeDomainStatus.STALE)
        self.assertEqual(projection.freshness, "STALE")

    def test_15_canonical_portfolio_valuation_correct(self) -> None:
        cid = register_future_contract(
            contract_id="ES202506",
            contract_multiplier="50",
            family_root="ES",
            expiration="2025-06-20",
            registry=self.registry,
        )
        position = PortfolioPosition(
            instrument_id=cid,
            asset_class="FUTURE",
            instrument_kind="FUTURE_CONTRACT",
            quantity=Decimal("2"),
            quantity_unit=QuantityUnit.CONTRACTS,
            native_currency="USD",
            multiplier=Decimal("50"),
        )
        mark = ValuationMark(
            instrument_id=cid,
            price=Decimal("5400"),
            currency="USD",
            data_status=MarkDataStatus.FRESH,
            source_time_ns=1000,
        )
        req = RuntimeProjectionRequest(
            descriptor=self._descriptor(cid),
            position=position,
            mark=mark,
        )
        result = project_portfolio_valuation(req)
        self.assertEqual(result["status"], "COMPLETE")
        self.assertIsNotNone(result["valuation"])
        self.assertEqual(result["valuation"]["notional_native"], "540000")

    def test_16_unsupported_risk_model_fails_closed(self) -> None:
        cid = register_future_contract(
            contract_id="ES202506",
            contract_multiplier="50",
            family_root="ES",
            expiration="2025-06-20",
            registry=self.registry,
        )
        req = RuntimeProjectionRequest(
            descriptor=self._descriptor(cid),
            pretrade_quantity=1,
            account_cash_minor=1_000_000_00,
        )
        risk = probe_risk_admission(req)
        self.assertFalse(risk["allowed"])
        self.assertIn(risk["reason"], {UNSUPPORTED_RISK_MODEL, "MARGIN_MISSING"})

    def test_17_provider_identity_does_not_replace_xa01(self) -> None:
        cid = register_future_contract(
            contract_id="ES202506",
            contract_multiplier="50",
            family_root="ES",
            expiration="2025-06-20",
            registry=self.registry,
        )
        req = RuntimeProjectionRequest(
            descriptor=self._descriptor(cid),
            provider="ibkr.observational",
            price=5400.0,
        )
        projection = project_runtime_domain(req)
        self.assertEqual(projection.instrument_id, cid)
        self.assertNotEqual(projection.instrument_id, "ibkr.observational")

    def test_18_runtime_status_structured(self) -> None:
        cid = register_future_contract(
            contract_id="ES202506",
            contract_multiplier="50",
            family_root="ES",
            expiration="2025-06-20",
            registry=self.registry,
        )
        req = RuntimeProjectionRequest(descriptor=self._descriptor(cid), price=5400.0)
        projection = project_runtime_domain(req)
        body = projection.to_dict()
        for key in ("status", "instrument_id", "instrument_kind", "provenance", "domain_payload"):
            self.assertIn(key, body)

    def test_19_empty_not_unavailable(self) -> None:
        oid = register_option_contract(
            option_id="NVDA20250620C00120000",
            underlying_symbol="NVDA",
            expiration="2025-06-20",
            strike="120",
            call_put="call",
            registry=self.registry,
        )
        req = RuntimeProjectionRequest(
            descriptor=self._descriptor(oid),
            underlying_id="NVDA",
            chain_status="empty",
        )
        projection = project_runtime_domain(req)
        self.assertEqual(projection.status, RuntimeDomainStatus.EMPTY)

    def test_20_api_preserves_canonical_identity(self) -> None:
        cid = register_future_contract(
            contract_id="ES202506",
            contract_multiplier="50",
            family_root="ES",
            expiration="2025-06-20",
            registry=self.registry,
        )
        req = RuntimeProjectionRequest(descriptor=self._descriptor(cid), price=5400.0)
        api = build_api_projection(project_runtime_domain(req))
        self.assertEqual(api["canonical_instrument_id"], cid)
        self.assertIn("provider_provenance", api)

    def test_21_query_key_isolation_concept(self) -> None:
        equity = "AAPL"
        future = register_future_contract(
            contract_id="ES202506",
            contract_multiplier="50",
            family_root="ES",
            expiration="2025-06-20",
            registry=self.registry,
        )
        option = register_option_contract(
            option_id="NVDA20250620C00120000",
            underlying_symbol="NVDA",
            expiration="2025-06-20",
            strike="120",
            call_put="call",
            registry=self.registry,
        )
        keys = {
            ("equity", equity, "PAPER", "a1"),
            ("future", future, "PAPER", "a1"),
            ("option", option, "PAPER", "a1"),
        }
        self.assertEqual(len(keys), 3)

    def test_22_no_execution_authority(self) -> None:
        cid = register_future_contract(
            contract_id="ES202506",
            contract_multiplier="50",
            family_root="ES",
            expiration="2025-06-20",
            registry=self.registry,
        )
        req = RuntimeProjectionRequest(descriptor=self._descriptor(cid), price=5400.0)
        projection = project_runtime_domain(req)
        self.assertFalse(projection.execution_available)
        risk = probe_risk_admission(req)
        self.assertFalse(risk["execution_authority"])

    def test_23_no_src_tools_dependency_regression(self) -> None:
        import ast

        cross_lane_root = ROOT / "src" / "market_platform_foundation" / "cross_lane"
        offenders: list[str] = []
        for path in cross_lane_root.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("tools."):
                    offenders.append(f"{path.name}:{node.lineno}")
        self.assertEqual(offenders, [])

    def test_24_ibkr_entitlement_does_not_block_unrelated_runtime(self) -> None:
        cid = register_future_contract(
            contract_id="ES202506",
            contract_multiplier="50",
            family_root="ES",
            expiration="2025-06-20",
            registry=self.registry,
        )
        store = ObservationalStateStore()
        req = RuntimeProjectionRequest(
            descriptor=self._descriptor(cid),
            price=5400.0,
            multiplier=50.0,
            provider="fixture",
            source_time_ns=1000,
        )
        projection = project_runtime_from_store(req, store)
        self.assertEqual(projection.status, RuntimeDomainStatus.AVAILABLE)

    def test_g12_runtime_performance_measured(self) -> None:
        cid = register_future_contract(
            contract_id="ES202506",
            contract_multiplier="50",
            family_root="ES",
            expiration="2025-06-20",
            registry=self.registry,
        )
        req = RuntimeProjectionRequest(descriptor=self._descriptor(cid), price=5400.0)
        start = time.perf_counter()
        for _ in range(5000):
            project_runtime_domain(req)
        elapsed_ms = (time.perf_counter() - start) * 1000
        self.assertLess(elapsed_ms, 5000.0, f"runtime projection too slow: {elapsed_ms:.2f}ms")


if __name__ == "__main__":
    unittest.main()
