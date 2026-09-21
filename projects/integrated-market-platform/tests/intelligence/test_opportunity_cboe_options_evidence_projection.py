"""Wire observational Cboe options context onto opportunity evidence projections."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

from market_platform_foundation.cboe_options.contracts import CboeExchangeCode
from market_platform_foundation.cboe_options.intraday import parse_intraday_statistics_html
from market_platform_foundation.cboe_options.market_volume import parse_market_volume_csv
from market_platform_foundation.cboe_options.opportunity_evidence import (
    ATTACHMENT_KIND,
    AUTHORITY_CLASS_EVIDENCE_NOT_PREDICTION,
)
from market_platform_foundation.cboe_options.store import CboeOptionsStore
from market_platform_foundation.cboe_options.symbol_data import parse_symbol_data_csv
from market_platform_foundation.intelligence.contracts import (
    ContractReference,
    IntelligenceScope,
    OpportunitySide,
    OpportunityV1,
    QualityState,
    QualitySummary,
)
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository
from market_platform_foundation.ui_api.opportunity_projections import (
    build_opportunity_evidence_payload,
    build_opportunities_summary_payload,
)
from market_platform_foundation.ui_api.store import ReplayStore

from tests.ui1.test_ui_api import COLLECTION_ROOT

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "cboe_options"))
from _helpers import INGESTED_TIME, RETRIEVED_TIME, intraday_html, load_json, load_text, parse_daily_fixture  # noqa: E402

DECISION_TIME = "2026-08-19T18:00:00-05:00"
EVIDENCE_KEY = "cboe_options_observational_evidence"


def _populated_cboe_store() -> CboeOptionsStore:
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


def _mint_opportunity(
    *,
    opportunity_id: str,
    instrument_id: str,
    family_admission_status: str,
    asset_class: str,
) -> OpportunityV1:
    return OpportunityV1(
        opportunity_id=opportunity_id,
        schema_version="1",
        scope=IntelligenceScope(instrument_ids=(instrument_id,), context_id="regular"),
        created_at_ns=1_700_000_000_000_000_000,
        quality=QualitySummary(state=QualityState.GOOD),
        side=OpportunitySide.LONG,
        expected_return=0.1,
        expected_net_edge=0.05,
        reason_summary="projection fixture",
        lineage_refs=(ContractReference(kind="forecast", id="fc-cboe-1"),),
        metadata={
            "family_admission_status": family_admission_status,
            "asset_class": asset_class,
        },
    )


class OpportunityCboeOptionsEvidenceProjectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = ReplayStore(collection_root=COLLECTION_ROOT)
        self.store.load()
        self.repo = InMemoryIntelligenceRepository()
        self.store.strategy_repository = self.repo

    def _bind(self, opportunity: OpportunityV1, *, cboe_store: CboeOptionsStore | None) -> None:
        self.repo.put_opportunity(opportunity)
        if cboe_store is not None:
            self.store.cboe_options_store = cboe_store
            self.store.cboe_options_decision_time = DECISION_TIME
        elif hasattr(self.store, "cboe_options_store"):
            delattr(self.store, "cboe_options_store")

    def test_admitted_equity_gets_overlay_when_fixtures_exist(self) -> None:
        opportunity = _mint_opportunity(
            opportunity_id="opp-cboe-aapl-1",
            instrument_id="US:AAPL",
            family_admission_status="ADMITTED",
            asset_class="US_EQUITY",
        )
        self._bind(opportunity, cboe_store=_populated_cboe_store())

        evidence = build_opportunity_evidence_payload(self.store, opportunity.opportunity_id)
        block = evidence.get(EVIDENCE_KEY)
        self.assertIsInstance(block, dict)
        self.assertEqual(block.get("disposition"), "ATTACHED")
        self.assertEqual(block.get("underlying_symbol"), "AAPL")
        self.assertEqual(block.get("authority_class"), AUTHORITY_CLASS_EVIDENCE_NOT_PREDICTION)
        self.assertEqual(block.get("attachment_kind"), ATTACHMENT_KIND)
        self.assertFalse(block.get("live_trading_authorized"))
        self.assertIsNone(block.get("options_strategy"))
        context = block.get("context") or {}
        self.assertGreater(len(context.get("open_interest") or []), 0)
        self.assertGreater(len(context.get("volume") or []), 0)
        self.assertGreater(len(context.get("derived_activity") or []), 0)

    def test_nvda_admitted_equity_also_overlays_without_aapl_hardcoding(self) -> None:
        opportunity = _mint_opportunity(
            opportunity_id="opp-cboe-nvda-1",
            instrument_id="NVDA",
            family_admission_status="ADMITTED",
            asset_class="US_EQUITY",
        )
        self._bind(opportunity, cboe_store=_populated_cboe_store())

        evidence = build_opportunity_evidence_payload(self.store, opportunity.opportunity_id)
        block = evidence.get(EVIDENCE_KEY) or {}
        self.assertEqual(block.get("disposition"), "ATTACHED")
        self.assertEqual(block.get("underlying_symbol"), "NVDA")
        context = block.get("context") or {}
        self.assertEqual(len(context.get("underlying_contract_activity") or []), 0)

    def test_not_admitted_does_not_get_overlay(self) -> None:
        opportunity = _mint_opportunity(
            opportunity_id="opp-cboe-denied-1",
            instrument_id="AAPL",
            family_admission_status="DENIED",
            asset_class="US_EQUITY",
        )
        self._bind(opportunity, cboe_store=_populated_cboe_store())

        evidence = build_opportunity_evidence_payload(self.store, opportunity.opportunity_id)
        self.assertNotIn(EVIDENCE_KEY, evidence)

    def test_non_equity_does_not_get_overlay(self) -> None:
        opportunity = _mint_opportunity(
            opportunity_id="opp-cboe-futures-1",
            instrument_id="ES",
            family_admission_status="ADMITTED",
            asset_class="US_FUTURES",
        )
        self._bind(opportunity, cboe_store=_populated_cboe_store())

        evidence = build_opportunity_evidence_payload(self.store, opportunity.opportunity_id)
        self.assertNotIn(EVIDENCE_KEY, evidence)

    def test_missing_options_inputs_do_not_invent_numbers(self) -> None:
        opportunity = _mint_opportunity(
            opportunity_id="opp-cboe-empty-1",
            instrument_id="AAPL",
            family_admission_status="ADMITTED",
            asset_class="US_EQUITY",
        )
        self._bind(opportunity, cboe_store=CboeOptionsStore())

        evidence = build_opportunity_evidence_payload(self.store, opportunity.opportunity_id)
        block = evidence.get(EVIDENCE_KEY) or {}
        self.assertEqual(block.get("disposition"), "ATTACHED")
        context = block.get("context") or {}
        self.assertEqual(context.get("open_interest"), [])
        self.assertEqual(context.get("volume"), [])
        self.assertEqual(context.get("derived_activity"), [])
        self.assertEqual(context.get("underlying_contract_activity"), [])
        serialized = str(context)
        self.assertNotRegex(serialized, r"\b(999999|fabricated|placeholder)\b")

    def test_absent_cboe_store_leaves_evidence_unchanged(self) -> None:
        opportunity = _mint_opportunity(
            opportunity_id="opp-cboe-absent-1",
            instrument_id="AAPL",
            family_admission_status="ADMITTED",
            asset_class="US_EQUITY",
        )
        self._bind(opportunity, cboe_store=None)

        evidence = build_opportunity_evidence_payload(self.store, opportunity.opportunity_id)
        self.assertNotIn(EVIDENCE_KEY, evidence)

    def test_derived_put_call_mix_is_not_marked_observed(self) -> None:
        opportunity = _mint_opportunity(
            opportunity_id="opp-cboe-derived-1",
            instrument_id="US:AAPL",
            family_admission_status="ADMITTED",
            asset_class="US_EQUITY",
        )
        self._bind(opportunity, cboe_store=_populated_cboe_store())

        evidence = build_opportunity_evidence_payload(self.store, opportunity.opportunity_id)
        context = (evidence.get(EVIDENCE_KEY) or {}).get("context") or {}
        derived = context.get("derived_activity") or []
        self.assertGreater(len(derived), 0)
        for row in derived:
            self.assertEqual(row.get("feature_layer"), "DETERMINISTIC_DERIVED")
            self.assertNotEqual(row.get("feature_layer"), "OBSERVED")
            self.assertNotEqual(row.get("lifecycle"), "OBSERVED")
            self.assertFalse(row.get("predictive"))
            self.assertEqual(row.get("semantics"), "ACTIVITY_MIX_NOT_DIRECTION")

    def test_summary_does_not_surface_cboe_overlay(self) -> None:
        opportunity = _mint_opportunity(
            opportunity_id="opp-cboe-summary-1",
            instrument_id="AAPL",
            family_admission_status="ADMITTED",
            asset_class="US_EQUITY",
        )
        self._bind(opportunity, cboe_store=_populated_cboe_store())

        summary = build_opportunities_summary_payload(self.store)
        for item in summary.get("items") or []:
            if item.get("opportunity_id") == opportunity.opportunity_id:
                self.assertNotIn(EVIDENCE_KEY, item)
                return
        self.fail("minted opportunity missing from summary")


if __name__ == "__main__":
    unittest.main()
