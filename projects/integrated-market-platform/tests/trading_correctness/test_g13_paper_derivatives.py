"""G13 — canonical multi-asset Paper execution for options and futures."""

from __future__ import annotations

import json
import time
import unittest
from decimal import Decimal
from pathlib import Path

from market_platform_foundation.paper.execution import (
    cancel_interactive_order,
    replace_interactive_order,
    submit_interactive_order,
)
from market_platform_foundation.paper.ledger import PaperExecutionLedger
from market_platform_foundation.paper.contracts import build_instrument_ref
from market_platform_foundation.paper.eligibility import (
    InstrumentAdmissionError,
    admit_order_instrument,
)
from market_platform_foundation.portfolio.instrument_economics import economics_from_descriptor
from market_platform_foundation.portfolio.accounting import option_premium
from market_platform_foundation.portfolio.paper_adapter import paper_snapshot_to_canonical
from market_platform_foundation.portfolio.paper_fill import apply_paper_fill_to_portfolio
from market_platform_foundation.portfolio.canonical import QuantityUnit
from market_platform_foundation.portfolio.canonical import CanonicalPortfolio, PortfolioKey
from market_platform_foundation.risk.margin_facts import (
    MARGIN_MISSING,
    MarginRequirementFacts,
    admit_margin_facts,
    margin_facts_from_fixture_row,
)
from market_platform_foundation.risk.policy import DEFAULT_RISK_POLICY
from market_platform_foundation.paper.preview import (
    PreviewError,
    PreviewErrorCode,
    PreviewStore,
    portfolio_state_revision,
    verify_preview_submit,
)
from market_platform_foundation.risk.financial import INSUFFICIENT_SETTLEMENT_CURRENCY
from market_platform_foundation.risk.pretrade import PreTradeRiskContext, evaluate_pretrade
from market_platform_foundation.xa01.compatibility import (
    register_future_contract,
    register_future_family,
    register_option_contract,
    register_continuous_futures_series,
)
from market_platform_foundation.xa01.registry import InstrumentRegistry, reset_registry_for_tests


POLICY = {
    **DEFAULT_RISK_POLICY,
    "commission_minor_per_share": 0,
    "fee_minor_per_order": 0,
    "initial_cash_minor": 500_000_00,
    "max_order_shares": 5_000,
    "max_position_shares": 20_000,
    "participation_cap_numerator": 1,
    "participation_cap_denominator": 1,
    "policy_version": "g13-test",
    "risk_policy_identity_hash": "g13-policy",
}


def _bars(price: str = "1.85", volume: int = 100_000) -> list[dict[str, object]]:
    return [
        {
            "available_time": 100 + i * 100,
            "bar_payload": {
                "close": price,
                "high": price,
                "low": price,
                "open": price,
                "volume": volume,
            },
        }
        for i in range(1, 6)
    ]


def _future_bars(price: str = "5500.00") -> list[dict[str, object]]:
    return _bars(price=price)


def _ledger(session: str = "g13") -> PaperExecutionLedger:
    return PaperExecutionLedger.open_session(
        replay_session_id=session,
        instrument_id="SESSION",
        symbol="SESSION",
        policy=dict(POLICY),
        execution_mode="INTERNAL_SIMULATION",
        execution_authority="PAPER_ONLY",
    )


def _instrument_ref(registry: InstrumentRegistry, canonical_id: str) -> dict[str, object]:
    record = registry.get(canonical_id)
    economics = economics_from_descriptor(record.descriptor)
    return build_instrument_ref(
        instrument_id=canonical_id,
        symbol=canonical_id,
        asset_class=economics.asset_class,
        currency=economics.settlement_currency,
        contract_multiplier=str(economics.contract_multiplier),
        instrument_kind=economics.instrument_kind,
        tradability=record.descriptor.tradability.value,
    )


def _option_instrument(registry: InstrumentRegistry) -> tuple[str, dict[str, object]]:
    option_id = register_option_contract(
        option_id="NVDA20260815C00130000",
        underlying_symbol="NVDA",
        expiration="2026-08-15",
        strike="130",
        call_put="call",
        registry=registry,
    )
    return option_id, _instrument_ref(registry, option_id)


def _future_instrument(registry: InstrumentRegistry) -> tuple[str, dict[str, object]]:
    future_id = register_future_contract(
        contract_id="ES202512",
        family_root="ES",
        expiration="2025-12-19",
        contract_multiplier="50",
        registry=registry,
    )
    return future_id, _instrument_ref(registry, future_id)


def _es_margin_facts(instrument_id: str) -> MarginRequirementFacts:
    return MarginRequirementFacts(
        instrument_id=instrument_id,
        provider="margin.fixture.futures_margin",
        initial_margin_per_contract=Decimal("15000"),
        maintenance_margin_per_contract=Decimal("13500"),
        currency="USD",
        effective_time_ns=1,
        received_time_ns=1,
        provenance="test",
    )


class G13OptionPaperTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_registry_for_tests()
        self.registry = InstrumentRegistry()

    def test_specific_option_accepted(self) -> None:
        option_id, instrument = _option_instrument(self.registry)
        ledger = _ledger("opt-accept")
        result = submit_interactive_order(
            ledger=ledger,
            bars=_bars(),
            symbol="NVDA20260815C00130000",
            instrument_id=option_id,
            side="BUY",
            quantity=2,
            observation_time=1,
            client_order_id="opt-buy-1",
            idempotency_key="opt-buy-1",
            order_type="LIMIT",
            limit_price_minor=185,
            instrument=instrument,
        )
        self.assertFalse(result["duplicate"])
        self.assertEqual(result["order"]["state"], "FILLED")
        pos = ledger.canonical_portfolio.get_position(option_id)
        self.assertIsNotNone(pos)
        self.assertEqual(int(pos.quantity), 2)

    def test_underlying_only_rejected(self) -> None:
        from market_platform_foundation.risk.financial import canonical_order_multiplier

        with self.assertRaises(ValueError):
            canonical_order_multiplier(
                {
                    "instrument_kind": "OPTION_CONTRACT",
                    "instrument_id": "NVDA",
                }
            )

    def test_multiplier_cash_debit_exact(self) -> None:
        option_id, instrument = _option_instrument(self.registry)
        ledger = _ledger("opt-cash")
        submit_interactive_order(
            ledger=ledger,
            bars=_bars(),
            symbol=option_id,
            instrument_id=option_id,
            side="BUY",
            quantity=3,
            observation_time=1,
            client_order_id="opt-cash",
            idempotency_key="opt-cash",
            order_type="LIMIT",
            limit_price_minor=185,
            instrument=instrument,
        )
        expected = option_premium(Decimal("3"), Decimal("1.85"), Decimal("100"))
        cash = ledger.canonical_portfolio.cash_balances[0].settled
        self.assertEqual(cash, Decimal("500000") - expected)

    def test_short_open_fails_without_margin_model(self) -> None:
        option_id, instrument = _option_instrument(self.registry)
        decision = evaluate_pretrade(
            PreTradeRiskContext(
                operational_identity="op",
                account_id="acc",
                mode="PAPER",
                instrument_id=option_id,
                asset_class="OPTION",
                instrument_kind="OPTION_CONTRACT",
                contract_multiplier=100,
                side="SELL",
                quantity=1,
                position_quantity=0,
                limit_price_minor=185,
                currency_cash_minor={"USD": 500_000_00},
            )
        )
        self.assertFalse(decision.accepted)
        self.assertIn("UNSUPPORTED_RISK_MODEL", decision.reason_codes)

    def test_duplicate_fill_idempotent(self) -> None:
        option_id, instrument = _option_instrument(self.registry)
        ledger = _ledger("opt-idem")
        fill = {
            "fill_id": "dup-fill",
            "order_id": "ord-1",
            "instrument_id": option_id,
            "instrument": instrument,
            "direction": "long",
            "fill_quantity": 1,
            "fill_price_minor": 185,
            "fill_time": 200,
        }
        order = {"order_id": "ord-1", "state": "FILLED"}
        ledger.append_order(order, intent={"instrument": instrument, "instrument_id": option_id})
        ledger.append_fill(fill, order=order)
        cash_after = ledger.canonical_portfolio.cash_balances[0].settled
        ledger.append_fill(fill, order=order)
        self.assertEqual(ledger.canonical_portfolio.cash_balances[0].settled, cash_after)
        self.assertEqual(len(ledger._applied_fill_ids), 1)


class G13FuturesPaperTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_registry_for_tests()
        self.registry = InstrumentRegistry()

    def test_family_rejected(self) -> None:
        register_future_family(family_root="ES", registry=self.registry)
        with self.assertRaises(InstrumentAdmissionError):
            admit_order_instrument("ES", registry=self.registry)

    def test_continuous_rejected(self) -> None:
        register_continuous_futures_series(
            family_root="ES",
            methodology="unadjusted_continuous",
            registry=self.registry,
        )
        with self.assertRaises(InstrumentAdmissionError):
            admit_order_instrument("ES_CONTINUOUS", registry=self.registry)

    def test_margin_missing_fails_closed(self) -> None:
        future_id, instrument = _future_instrument(self.registry)
        decision = evaluate_pretrade(
            PreTradeRiskContext(
                operational_identity="op",
                account_id="acc",
                mode="PAPER",
                instrument_id=future_id,
                asset_class="FUTURE",
                instrument_kind="FUTURE_CONTRACT",
                contract_multiplier=50,
                side="BUY",
                quantity=1,
                currency_cash_minor={"USD": 500_000_00},
                source_time_ns=1,
            )
        )
        self.assertFalse(decision.accepted)
        self.assertEqual(decision.reason_codes[0], MARGIN_MISSING)

    def test_valid_margin_admitted(self) -> None:
        future_id, _ = _future_instrument(self.registry)
        facts = _es_margin_facts(future_id)
        admission = admit_margin_facts(
            facts,
            instrument_id=future_id,
            order_currency="USD",
            observation_time_ns=100,
        )
        self.assertTrue(admission.admitted)

    def test_futures_open_no_full_notional_debit(self) -> None:
        future_id, instrument = _future_instrument(self.registry)
        facts = _es_margin_facts(future_id)
        ledger = _ledger("fut-open")
        submit_interactive_order(
            ledger=ledger,
            bars=_future_bars(),
            symbol=future_id,
            instrument_id=future_id,
            side="BUY",
            quantity=1,
            observation_time=1,
            client_order_id="fut-1",
            idempotency_key="fut-1",
            order_type="LIMIT",
            limit_price_minor=550_000,
            instrument=instrument,
            margin_facts=facts,
        )
        cash = ledger.canonical_portfolio.cash_balances[0].settled
        notional_if_equity = Decimal("5500") * Decimal("50")
        self.assertGreater(notional_if_equity, Decimal("15000"))
        self.assertEqual(cash, Decimal("500000") - Decimal("15000"))


def _partial_policy() -> dict:
    policy = dict(POLICY)
    policy["participation_cap_numerator"] = 1
    policy["participation_cap_denominator"] = 10
    return policy


def _partial_bars(price: str = "1.85", volume: int = 40) -> list[dict[str, object]]:
    return [
        {
            "available_time": 100 + i * 100,
            "bar_payload": {
                "close": price,
                "high": price,
                "low": price,
                "open": price,
                "volume": volume,
            },
        }
        for i in range(1, 8)
    ]


class G13OptionLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_registry_for_tests()
        self.registry = InstrumentRegistry()

    def _ledger(self, session: str) -> PaperExecutionLedger:
        return PaperExecutionLedger.open_session(
            replay_session_id=session,
            instrument_id="SESSION",
            symbol="SESSION",
            policy=_partial_policy(),
            execution_mode="INTERNAL_SIMULATION",
            execution_authority="PAPER_ONLY",
        )

    def test_partial_fill_accumulates_contracts(self) -> None:
        option_id, instrument = _option_instrument(self.registry)
        ledger = self._ledger("opt-partial")
        first = submit_interactive_order(
            ledger=ledger,
            bars=_partial_bars(),
            symbol=option_id,
            instrument_id=option_id,
            side="BUY",
            quantity=10,
            observation_time=1,
            client_order_id="opt-p1",
            idempotency_key="opt-p1",
            order_type="LIMIT",
            limit_price_minor=185,
            instrument=instrument,
        )
        self.assertEqual(first["order"]["state"], "PARTIALLY_FILLED")
        self.assertEqual(int(first["order"]["filled_quantity"]), 4)
        pos = ledger.canonical_portfolio.get_position(option_id)
        self.assertEqual(int(pos.quantity), 4)

    def test_replace_working_remainder(self) -> None:
        option_id, instrument = _option_instrument(self.registry)
        ledger = self._ledger("opt-replace")
        result = submit_interactive_order(
            ledger=ledger,
            bars=_partial_bars(),
            symbol=option_id,
            instrument_id=option_id,
            side="BUY",
            quantity=10,
            observation_time=1,
            client_order_id="opt-rp",
            idempotency_key="opt-rp",
            order_type="LIMIT",
            limit_price_minor=185,
            instrument=instrument,
        )
        order_id = result["order_id"]
        replaced = replace_interactive_order(
            ledger=ledger,
            order_id=order_id,
            replaced_quantity=8,
            order_type="LIMIT",
            limit_price_minor=185,
        )
        self.assertEqual(replaced["state"], "REPLACED")
        self.assertEqual(int(ledger.lookup_order(order_id)["working_remaining"]), 4)

    def test_cancel_partial_remainder(self) -> None:
        option_id, instrument = _option_instrument(self.registry)
        ledger = self._ledger("opt-cancel")
        result = submit_interactive_order(
            ledger=ledger,
            bars=_partial_bars(),
            symbol=option_id,
            instrument_id=option_id,
            side="BUY",
            quantity=10,
            observation_time=1,
            client_order_id="opt-cn",
            idempotency_key="opt-cn",
            order_type="LIMIT",
            limit_price_minor=185,
            instrument=instrument,
        )
        order_id = result["order_id"]
        cancelled = cancel_interactive_order(ledger=ledger, order_id=order_id)
        self.assertEqual(cancelled["state"], "CANCELLED")
        pos = ledger.canonical_portfolio.get_position(option_id)
        self.assertEqual(int(pos.quantity), 4)


class G13RuntimeMarginProbeTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_registry_for_tests()
        self.registry = InstrumentRegistry()

    def test_runtime_probe_admits_explicit_margin(self) -> None:
        from market_platform_foundation.cross_lane.multi_asset_runtime import (
            RuntimeProjectionRequest,
            probe_risk_admission,
        )

        future_id = register_future_contract(
            contract_id="ES202512",
            family_root="ES",
            expiration="2025-12-19",
            contract_multiplier="50",
            registry=self.registry,
        )
        descriptor = self.registry.get(future_id).descriptor
        facts = _es_margin_facts(future_id)
        risk = probe_risk_admission(
            RuntimeProjectionRequest(
                descriptor=descriptor,
                pretrade_quantity=1,
                account_cash_minor=500_000_00,
                margin_facts=facts,
                as_of_time_ns=100,
            )
        )
        self.assertTrue(risk["allowed"])
        self.assertIsNone(risk["reason"])


class G13AccountIsolationTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_registry_for_tests()
        self.registry = InstrumentRegistry()

    def test_separate_ledgers_isolate_option_positions(self) -> None:
        option_id, instrument = _option_instrument(self.registry)
        ledger_a = _ledger("iso-a")
        ledger_b = _ledger("iso-b")
        submit_interactive_order(
            ledger=ledger_a,
            bars=_bars(),
            symbol=option_id,
            instrument_id=option_id,
            side="BUY",
            quantity=2,
            observation_time=1,
            client_order_id="iso-a",
            idempotency_key="iso-a",
            order_type="LIMIT",
            limit_price_minor=185,
            instrument=instrument,
        )
        self.assertIsNotNone(ledger_a.canonical_portfolio.get_position(option_id))
        self.assertIsNone(ledger_b.canonical_portfolio.get_position(option_id))


class G13FuturesLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_registry_for_tests()
        self.registry = InstrumentRegistry()

    def _ledger(self, session: str) -> PaperExecutionLedger:
        return PaperExecutionLedger.open_session(
            replay_session_id=session,
            instrument_id="SESSION",
            symbol="SESSION",
            policy=_partial_policy(),
            execution_mode="INTERNAL_SIMULATION",
            execution_authority="PAPER_ONLY",
        )

    def test_partial_fill_accumulates_contracts(self) -> None:
        future_id, instrument = _future_instrument(self.registry)
        facts = _es_margin_facts(future_id)
        ledger = self._ledger("fut-partial")
        first = submit_interactive_order(
            ledger=ledger,
            bars=_partial_bars(price="5500.00", volume=40),
            symbol=future_id,
            instrument_id=future_id,
            side="BUY",
            quantity=10,
            observation_time=1,
            client_order_id="fut-p1",
            idempotency_key="fut-p1",
            order_type="LIMIT",
            limit_price_minor=550_000,
            instrument=instrument,
            margin_facts=facts,
        )
        self.assertEqual(first["order"]["state"], "PARTIALLY_FILLED")
        self.assertEqual(int(first["order"]["filled_quantity"]), 4)
        pos = ledger.canonical_portfolio.get_position(future_id)
        self.assertEqual(int(pos.quantity), 4)

    def test_replace_working_remainder(self) -> None:
        future_id, instrument = _future_instrument(self.registry)
        facts = _es_margin_facts(future_id)
        ledger = self._ledger("fut-replace")
        result = submit_interactive_order(
            ledger=ledger,
            bars=_partial_bars(price="5500.00", volume=40),
            symbol=future_id,
            instrument_id=future_id,
            side="BUY",
            quantity=10,
            observation_time=1,
            client_order_id="fut-rp",
            idempotency_key="fut-rp",
            order_type="LIMIT",
            limit_price_minor=550_000,
            instrument=instrument,
            margin_facts=facts,
        )
        order_id = result["order_id"]
        replaced = replace_interactive_order(
            ledger=ledger,
            order_id=order_id,
            replaced_quantity=8,
            order_type="LIMIT",
            limit_price_minor=550_000,
        )
        self.assertEqual(replaced["state"], "REPLACED")
        self.assertEqual(int(ledger.lookup_order(order_id)["working_remaining"]), 4)

    def test_cancel_partial_remainder(self) -> None:
        future_id, instrument = _future_instrument(self.registry)
        facts = _es_margin_facts(future_id)
        ledger = self._ledger("fut-cancel")
        result = submit_interactive_order(
            ledger=ledger,
            bars=_partial_bars(price="5500.00", volume=40),
            symbol=future_id,
            instrument_id=future_id,
            side="BUY",
            quantity=10,
            observation_time=1,
            client_order_id="fut-cn",
            idempotency_key="fut-cn",
            order_type="LIMIT",
            limit_price_minor=550_000,
            instrument=instrument,
            margin_facts=facts,
        )
        order_id = result["order_id"]
        cancelled = cancel_interactive_order(ledger=ledger, order_id=order_id)
        self.assertEqual(cancelled["state"], "CANCELLED")
        pos = ledger.canonical_portfolio.get_position(future_id)
        self.assertEqual(int(pos.quantity), 4)


class G13SettlementCurrencyTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_registry_for_tests()
        self.registry = InstrumentRegistry()

    def test_option_eur_settlement_fails_without_bucket(self) -> None:
        option_id, _ = _option_instrument(self.registry)
        decision = evaluate_pretrade(
            PreTradeRiskContext(
                operational_identity="op",
                account_id="acc",
                mode="PAPER",
                instrument_id=option_id,
                asset_class="OPTION",
                instrument_kind="OPTION_CONTRACT",
                contract_multiplier=100,
                side="BUY",
                quantity=1,
                currency="EUR",
                limit_price_minor=185,
                currency_cash_minor={"USD": 500_000_00},
            )
        )
        self.assertFalse(decision.accepted)
        self.assertEqual(decision.reason_codes[0], INSUFFICIENT_SETTLEMENT_CURRENCY)

    def test_future_eur_settlement_fails_without_bucket(self) -> None:
        future_id, _ = _future_instrument(self.registry)
        facts = _es_margin_facts(future_id)
        decision = evaluate_pretrade(
            PreTradeRiskContext(
                operational_identity="op",
                account_id="acc",
                mode="PAPER",
                instrument_id=future_id,
                asset_class="FUTURE",
                instrument_kind="FUTURE_CONTRACT",
                contract_multiplier=50,
                side="BUY",
                quantity=1,
                currency="EUR",
                currency_cash_minor={"USD": 500_000_00},
                margin_facts=facts,
                source_time_ns=100,
            )
        )
        self.assertFalse(decision.accepted)
        self.assertEqual(decision.reason_codes[0], INSUFFICIENT_SETTLEMENT_CURRENCY)


class G13MarginPreviewBindingTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_registry_for_tests()
        self.registry = InstrumentRegistry()

    def test_changed_margin_facts_invalidates_preview(self) -> None:
        future_id, _ = _future_instrument(self.registry)
        facts_a = _es_margin_facts(future_id)
        facts_b = MarginRequirementFacts(
            instrument_id=future_id,
            provider="margin.fixture.futures_margin",
            initial_margin_per_contract=Decimal("16000"),
            maintenance_margin_per_contract=Decimal("14500"),
            currency="USD",
            effective_time_ns=1,
            received_time_ns=1,
            provenance="test-updated",
        )
        ledger = _ledger("margin-preview")
        store = PreviewStore()
        revision = portfolio_state_revision(ledger)
        record = store.issue(
            account_id=ledger.paper_account_id,
            mode="PAPER",
            instrument_id=future_id,
            intent_digest="intent-digest",
            side="BUY",
            quantity=1,
            order_type="LIMIT",
            risk_policy_revision=str(POLICY["risk_policy_identity_hash"]),
            portfolio_revision=revision,
            observation_time=1,
            limit_price_minor=550_000,
            margin_facts_revision=facts_a.revision_digest(),
        )
        with self.assertRaises(PreviewError) as ctx:
            verify_preview_submit(
                store,
                preview_id=record.preview_id,
                account_id=ledger.paper_account_id,
                mode="PAPER",
                intent_digest="intent-digest",
                instrument_id=future_id,
                side="BUY",
                quantity=1,
                order_type="LIMIT",
                limit_price_minor=550_000,
                portfolio_revision=revision,
                risk_policy_revision=str(POLICY["risk_policy_identity_hash"]),
                margin_facts_revision=facts_b.revision_digest(),
            )
        self.assertEqual(ctx.exception.code, PreviewErrorCode.PREVIEW_MARGIN_STALE)

    def test_matching_margin_facts_accepts_preview(self) -> None:
        future_id, _ = _future_instrument(self.registry)
        facts = _es_margin_facts(future_id)
        ledger = _ledger("margin-preview-ok")
        store = PreviewStore()
        revision = portfolio_state_revision(ledger)
        digest = facts.revision_digest()
        record = store.issue(
            account_id=ledger.paper_account_id,
            mode="PAPER",
            instrument_id=future_id,
            intent_digest="intent-digest",
            side="BUY",
            quantity=1,
            order_type="LIMIT",
            risk_policy_revision=str(POLICY["risk_policy_identity_hash"]),
            portfolio_revision=revision,
            observation_time=1,
            limit_price_minor=550_000,
            margin_facts_revision=digest,
        )
        verified = verify_preview_submit(
            store,
            preview_id=record.preview_id,
            account_id=ledger.paper_account_id,
            mode="PAPER",
            intent_digest="intent-digest",
            instrument_id=future_id,
            side="BUY",
            quantity=1,
            order_type="LIMIT",
            limit_price_minor=550_000,
            portfolio_revision=revision,
            risk_policy_revision=str(POLICY["risk_policy_identity_hash"]),
            margin_facts_revision=digest,
        )
        self.assertEqual(verified.preview_id, record.preview_id)


class G13PaperAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_registry_for_tests()
        self.registry = InstrumentRegistry()

    def test_option_snapshot_carries_contract_metadata(self) -> None:
        option_id, instrument = _option_instrument(self.registry)
        ledger = _ledger("adapter-opt")
        submit_interactive_order(
            ledger=ledger,
            bars=_bars(),
            symbol=option_id,
            instrument_id=option_id,
            side="BUY",
            quantity=1,
            observation_time=1,
            client_order_id="adapter-opt",
            idempotency_key="adapter-opt",
            order_type="LIMIT",
            limit_price_minor=185,
            instrument=instrument,
        )
        snapshot = paper_snapshot_to_canonical(ledger)
        self.assertEqual(len(snapshot.positions), 1)
        position = snapshot.positions[0]
        self.assertEqual(position.instrument_kind, "OPTION_CONTRACT")
        self.assertEqual(position.asset_class, "OPTION")
        self.assertEqual(position.quantity_unit, QuantityUnit.CONTRACTS)


class G13RuntimePerformanceTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_registry_for_tests()
        self.registry = InstrumentRegistry()

    def test_g13_runtime_performance_measured(self) -> None:
        option_id, instrument = _option_instrument(self.registry)
        future_id, future_instrument = _future_instrument(self.registry)
        facts = _es_margin_facts(future_id)
        ledger = _ledger("perf")
        policy = dict(POLICY)
        results: dict[str, float] = {}

        start = time.perf_counter()
        for _ in range(200):
            evaluate_pretrade(
                PreTradeRiskContext(
                    operational_identity="perf",
                    account_id="acc",
                    mode="PAPER",
                    instrument_id=option_id,
                    asset_class="OPTION",
                    instrument_kind="OPTION_CONTRACT",
                    contract_multiplier=100,
                    side="BUY",
                    quantity=1,
                    limit_price_minor=185,
                    currency_cash_minor={"USD": 500_000_00},
                )
            )
        results["option_pretrade_ms"] = (time.perf_counter() - start) * 1000

        start = time.perf_counter()
        for _ in range(200):
            evaluate_pretrade(
                PreTradeRiskContext(
                    operational_identity="perf",
                    account_id="acc",
                    mode="PAPER",
                    instrument_id=future_id,
                    asset_class="FUTURE",
                    instrument_kind="FUTURE_CONTRACT",
                    contract_multiplier=50,
                    side="BUY",
                    quantity=1,
                    margin_facts=facts,
                    currency_cash_minor={"USD": 500_000_00},
                    source_time_ns=100,
                )
            )
        results["future_pretrade_ms"] = (time.perf_counter() - start) * 1000

        start = time.perf_counter()
        for i in range(50):
            apply_paper_fill_to_portfolio(
                ledger.canonical_portfolio,
                fill={
                    "fill_id": f"perf-fill-{i}",
                    "instrument": future_instrument,
                    "direction": "long",
                    "fill_quantity": 1,
                    "fill_price_minor": 550_000,
                    "fill_time": 100 + i,
                    "margin_facts": facts.to_dict(),
                },
                policy=policy,
            )
        results["fill_to_portfolio_ms"] = (time.perf_counter() - start) * 1000

        evidence_path = Path(__file__).resolve().parents[2] / "artifacts" / "g13-runtime-performance.json"
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        evidence_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

        self.assertLess(results["option_pretrade_ms"], 2000.0)
        self.assertLess(results["future_pretrade_ms"], 2000.0)
        self.assertLess(results["fill_to_portfolio_ms"], 2000.0)


class G13CrossCuttingTests(unittest.TestCase):
    def test_canonical_portfolio_is_authority(self) -> None:
        portfolio = CanonicalPortfolio(PortfolioKey(account_id="iso-a", mode="PAPER"))
        portfolio.set_cash(
            __import__("market_platform_foundation.portfolio.canonical", fromlist=["CashBalance"]).CashBalance(
                currency="USD",
                settled=Decimal("10000"),
            )
        )
        instrument = {
            "instrument_id": "OPT1",
            "instrument_kind": "OPTION_CONTRACT",
            "asset_class": "OPTION",
            "currency": "USD",
            "contract_multiplier": "100",
        }
        fill = {
            "fill_id": "f1",
            "instrument": instrument,
            "direction": "long",
            "fill_quantity": 1,
            "fill_price_minor": 200,
            "fill_time": 1,
        }
        apply_paper_fill_to_portfolio(
            portfolio,
            fill=fill,
            policy={"price_scale": 100, "commission_minor_per_share": 0, "fee_minor_per_order": 0},
        )
        self.assertEqual(portfolio.get_position("OPT1").quantity, Decimal("1"))


if __name__ == "__main__":
    unittest.main()
