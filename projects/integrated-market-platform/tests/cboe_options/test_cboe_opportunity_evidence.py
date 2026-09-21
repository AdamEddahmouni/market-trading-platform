"""Governed Cboe observational context attach onto admitted US equity opportunities."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.cboe_options.contracts import CboeExchangeCode  # noqa: E402
from market_platform_foundation.cboe_options.intraday import parse_intraday_statistics_html  # noqa: E402
from market_platform_foundation.cboe_options.market_volume import parse_market_volume_csv  # noqa: E402
from market_platform_foundation.cboe_options.opportunity_attachment import (  # noqa: E402
    attach_cboe_options_observational_context,
)
from market_platform_foundation.cboe_options.opportunity_evidence import (  # noqa: E402
    AUTHORITY_CLASS_EVIDENCE_NOT_PREDICTION,
    ATTACHMENT_KIND,
    FORBIDDEN_AUTHORITY_KEYS,
    build_cboe_options_observational_context,
    observational_context_to_dict,
    underlying_symbol_from_instrument_id,
)
from market_platform_foundation.cboe_options.store import CboeOptionsStore  # noqa: E402
from market_platform_foundation.cboe_options.symbol_data import parse_symbol_data_csv  # noqa: E402
from market_platform_foundation.intelligence.contracts import (  # noqa: E402
    IntelligenceScope,
    OpportunityV1,
    QualityState,
    QualitySummary,
)

sys.path.insert(0, str(ROOT / "tests" / "cboe_options"))
from _helpers import INGESTED_TIME, RETRIEVED_TIME, intraday_html, load_json, load_text, parse_daily_fixture


DECISION_TIME = "2026-08-19T18:00:00-05:00"


def _populated_store() -> CboeOptionsStore:
    store = CboeOptionsStore()
    store.add_statistics(parse_daily_fixture().observations)
    delay_meta = load_json("market_volume_delayed.json")
    store.add_statistics(
        parse_market_volume_csv(
            load_text("market_volume.csv"),
            retrieved_time=RETRIEVED_TIME,
            ingested_time=INGESTED_TIME,
            trade_date="2026-08-19",
            source_data_as_of_time=delay_meta["sourceDataAsOfTime"],
        ).observations
    )
    intraday_payload = load_json("intraday_exchange_stats.json")
    store.add_statistics(
        parse_intraday_statistics_html(
            intraday_html(intraday_payload),
            retrieved_time=RETRIEVED_TIME,
            ingested_time=INGESTED_TIME,
            trade_date=intraday_payload["tradeDate"],
        ).cumulative
    )
    store.add_snapshots(
        parse_symbol_data_csv(
            load_text("symbol_data_cone.csv"),
            exchange=CboeExchangeCode.C1,
            retrieved_time=RETRIEVED_TIME,
            ingested_time=INGESTED_TIME,
        ).snapshots
    )
    return store


def _admitted_opportunity(*, instrument_id: str, opportunity_id: str = "opp-us-equity-1") -> OpportunityV1:
    return OpportunityV1(
        opportunity_id=opportunity_id,
        schema_version="1",
        scope=IntelligenceScope(instrument_ids=(instrument_id,)),
        created_at_ns=1_700_000_000_000_000_000,
        quality=QualitySummary(state=QualityState.GOOD),
        reason_summary="admitted US equity fixture",
        metadata={
            "family_admission_status": "ADMITTED",
            "asset_class": "US_EQUITY",
        },
    )


class UnderlyingResolutionTests(unittest.TestCase):
    def test_instrument_id_forms_are_generic(self) -> None:
        self.assertEqual(underlying_symbol_from_instrument_id("AAPL"), "AAPL")
        self.assertEqual(underlying_symbol_from_instrument_id("US:AAPL"), "AAPL")
        self.assertEqual(underlying_symbol_from_instrument_id("equity:US:NVDA"), "NVDA")
        self.assertEqual(underlying_symbol_from_instrument_id("nvda"), "NVDA")

    def test_blank_instrument_is_empty(self) -> None:
        self.assertEqual(underlying_symbol_from_instrument_id("  "), "")


class ObservationalContextBuildTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = _populated_store()

    def test_context_includes_oi_volume_and_derived(self) -> None:
        context = build_cboe_options_observational_context(
            self.store,
            underlying_symbol="AAPL",
            decision_time=DECISION_TIME,
        )
        self.assertEqual(context.authority_class, AUTHORITY_CLASS_EVIDENCE_NOT_PREDICTION)
        self.assertEqual(context.attachment_kind, ATTACHMENT_KIND)
        self.assertFalse(context.predictive)
        self.assertFalse(context.live_trading_authorized)
        self.assertIsNone(context.options_strategy)
        self.assertGreater(len(context.open_interest), 0)
        self.assertGreater(len(context.volume), 0)
        self.assertGreater(len(context.derived_activity), 0)
        self.assertGreater(len(context.underlying_contract_activity), 0)
        for snap in context.underlying_contract_activity:
            self.assertEqual(snap.underlying.upper(), "AAPL")

    def test_nvda_has_market_aggregates_without_fabricating_contracts(self) -> None:
        context = build_cboe_options_observational_context(
            self.store,
            underlying_symbol="NVDA",
            decision_time=DECISION_TIME,
        )
        self.assertGreater(len(context.open_interest), 0)
        self.assertGreater(len(context.volume), 0)
        self.assertEqual(len(context.underlying_contract_activity), 0)
        self.assertIn("UNDERLYING_CONTRACT_ACTIVITY_NOT_OBSERVED", context.quality_flags)

    def test_payload_has_no_forbidden_authority_or_signal_keys(self) -> None:
        context = build_cboe_options_observational_context(
            self.store,
            underlying_symbol="AAPL",
            decision_time=DECISION_TIME,
        )
        payload = observational_context_to_dict(context)
        self.assertFalse(payload["live_trading_authorized"])
        self.assertIsNone(payload["options_strategy"])
        self.assertFalse(payload["predictive"])
        serialized = json.dumps(payload).lower()
        # Affirmative signal / authority tokens must not appear as claim keys.
        for key in (
            "execution_authority",
            "submit_order",
            "broker_order",
            "trade_direction",
            "bullish",
            "bearish",
            "smart_money",
            "whale",
            "alpha",
            "expected_return",
        ):
            self.assertIn(key, FORBIDDEN_AUTHORITY_KEYS)
            self.assertNotIn(f'"{key}"', serialized)
        self.assertIn("not_options_live_trading", serialized)
        self.assertIn("not_options_strategy", serialized)

    def test_pit_hides_context_before_availability(self) -> None:
        context = build_cboe_options_observational_context(
            self.store,
            underlying_symbol="AAPL",
            decision_time="2026-08-18T12:00:00-05:00",
        )
        self.assertEqual(len(context.open_interest), 0)
        self.assertEqual(len(context.volume), 0)
        self.assertEqual(len(context.underlying_contract_activity), 0)


class OpportunityAttachmentAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = _populated_store()

    def test_attaches_to_admitted_us_equity_opportunity(self) -> None:
        opportunity = _admitted_opportunity(instrument_id="US:AAPL")
        result = attach_cboe_options_observational_context(
            opportunity,
            store=self.store,
            decision_time=DECISION_TIME,
        )
        self.assertEqual(result.disposition, "ATTACHED")
        self.assertEqual(result.opportunity_id, opportunity.opportunity_id)
        self.assertEqual(result.underlying_symbol, "AAPL")
        self.assertIsNotNone(result.context)
        assert result.context is not None
        self.assertGreater(len(result.context.open_interest), 0)
        self.assertGreater(len(result.context.volume), 0)
        self.assertFalse(result.context.live_trading_authorized)
        self.assertIsNone(result.context.options_strategy)

    def test_nvda_fixture_opportunity_attaches_without_aapl_hardcoding(self) -> None:
        opportunity = _admitted_opportunity(instrument_id="NVDA", opportunity_id="opp-nvda-1")
        result = attach_cboe_options_observational_context(
            opportunity,
            store=self.store,
            decision_time=DECISION_TIME,
        )
        self.assertEqual(result.disposition, "ATTACHED")
        self.assertEqual(result.underlying_symbol, "NVDA")
        assert result.context is not None
        self.assertEqual(len(result.context.underlying_contract_activity), 0)

    def test_denies_when_family_not_admitted(self) -> None:
        opportunity = OpportunityV1(
            opportunity_id="opp-denied-1",
            schema_version="1",
            scope=IntelligenceScope(instrument_ids=("AAPL",)),
            created_at_ns=1_700_000_000_000_000_000,
            quality=QualitySummary(state=QualityState.GOOD),
            metadata={"family_admission_status": "DENIED", "asset_class": "US_EQUITY"},
        )
        result = attach_cboe_options_observational_context(
            opportunity,
            store=self.store,
            decision_time=DECISION_TIME,
        )
        self.assertEqual(result.disposition, "DENIED")
        self.assertEqual(result.denial_reason, "FAMILY_NOT_ADMITTED")
        self.assertIsNone(result.context)

    def test_denies_non_us_equity_asset_class(self) -> None:
        opportunity = OpportunityV1(
            opportunity_id="opp-futures-1",
            schema_version="1",
            scope=IntelligenceScope(instrument_ids=("ES",)),
            created_at_ns=1_700_000_000_000_000_000,
            quality=QualitySummary(state=QualityState.GOOD),
            metadata={"family_admission_status": "ADMITTED", "asset_class": "US_FUTURES"},
        )
        result = attach_cboe_options_observational_context(
            opportunity,
            store=self.store,
            decision_time=DECISION_TIME,
        )
        self.assertEqual(result.disposition, "DENIED")
        self.assertEqual(result.denial_reason, "ASSET_CLASS_NOT_US_EQUITY")

    def test_does_not_mutate_opportunity(self) -> None:
        opportunity = _admitted_opportunity(instrument_id="AAPL")
        before = dict(opportunity.metadata)
        attach_cboe_options_observational_context(
            opportunity,
            store=self.store,
            decision_time=DECISION_TIME,
        )
        self.assertEqual(opportunity.metadata, before)
        self.assertNotIn("cboe_options", opportunity.metadata)


if __name__ == "__main__":
    unittest.main()
