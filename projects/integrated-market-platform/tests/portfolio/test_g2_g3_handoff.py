"""Explicit G2/G3 handoff: risk does not rank; ranking cannot bypass risk.

OE Phase 4 portfolio interaction. Ranking remains the Opportunity Engine
operator order. G3 ``evaluate_pretrade`` and G2 book exposure remain the
authoritative gates. This does not mutate the book, submit, or automate Live.
"""

from __future__ import annotations

import dataclasses
import unittest
from decimal import Decimal

from market_platform_foundation.intelligence.opportunity.ingest import (
    assemble_opportunity_review_rows,
)
from market_platform_foundation.intelligence.opportunity.ranking import rank_review_rows
from market_platform_foundation.intelligence.opportunity.read_model import OpportunitySummary
from market_platform_foundation.intelligence.contracts import (
    IntelligenceScope,
    OpportunitySide,
    OpportunityV1,
    QualityState,
    QualitySummary,
)
from market_platform_foundation.intelligence.opportunity.types import AssessmentAction
from market_platform_foundation.portfolio.canonical import (
    CanonicalPortfolio,
    PortfolioKey,
    PositionInput,
    QuantityUnit,
    ValuationMark,
)
from market_platform_foundation.risk.book_exposure import BookLimitPolicy
from market_platform_foundation.risk.decision import REJECT_KILL_SWITCH, evaluate_risk
from market_platform_foundation.risk.g2_g3_handoff import (
    HANDOFF_AUTHORITY,
    LIVE_OBSERVATIONAL_NO_EXECUTION,
    RANKING_PAYLOAD_KEYS,
    RankedOpportunityIntent,
    evaluate_ranked_opportunity_handoff,
    intent_from_ranked_summary,
)
from market_platform_foundation.risk.kill_switch import KillSwitchState
from market_platform_foundation.risk.policy import DEFAULT_RISK_POLICY
from market_platform_foundation.risk.pretrade import PreTradeRiskContext, evaluate_pretrade
from market_platform_foundation.xa01.registry import reset_registry_for_tests


QUALITY = QualitySummary(state=QualityState.GOOD)


def _opportunity(opportunity_id: str, instrument_id: str) -> OpportunityV1:
    return OpportunityV1(
        opportunity_id=opportunity_id,
        schema_version="1",
        scope=IntelligenceScope(instrument_ids=(instrument_id,), context_id="regular"),
        created_at_ns=10_000,
        quality=QUALITY,
        side=OpportunitySide.LONG,
        reason_summary=f"{instrument_id} candidate",
    )


def _context(**overrides: object) -> PreTradeRiskContext:
    body: dict[str, object] = {
        "operational_identity": "op-1",
        "account_id": "acct-1",
        "mode": "PAPER",
        "instrument_id": "AAPL",
        "asset_class": "EQUITY",
        "instrument_kind": "TRADABLE_SECURITY",
        "symbol": "AAPL",
        "contract_multiplier": 1,
        "side": "BUY",
        "quantity": 100,
        "quantity_unit": "SHARES",
        "order_type": "LIMIT",
        "limit_price_minor": 1000,
        "currency": "USD",
        "account_currency": "USD",
        "portfolio_cash_minor": 10_000_00,
        "position_quantity": 0,
        "working_obligations_minor": 0,
        "risk_policy_revision": "pol-1",
        "source_time_ns": 1,
    }
    body.update(overrides)
    return PreTradeRiskContext(**body)  # type: ignore[arg-type]


def _intent(**overrides: object) -> RankedOpportunityIntent:
    body: dict[str, object] = {
        "opportunity_id": "opp-top",
        "instrument_id": "AAPL",
        "account_id": "acct-1",
        "mode": "PAPER",
        "side": "BUY",
        "quantity": 100,
        "rank_order": 1,
        "rank_score": 99.0,
    }
    body.update(overrides)
    return RankedOpportunityIntent(**body)  # type: ignore[arg-type]


def _paper_book(account_id: str = "acct-1") -> CanonicalPortfolio:
    return CanonicalPortfolio(PortfolioKey(account_id=account_id, mode="PAPER"))


def _equity(instrument_id: str, quantity: str) -> PositionInput:
    return PositionInput(
        instrument_id=instrument_id,
        asset_class="EQUITY",
        instrument_kind="TRADABLE_SECURITY",
        quantity=Decimal(quantity),
        quantity_unit=QuantityUnit.SHARES,
        native_currency="USD",
    )


def _mark(instrument_id: str, price: str) -> ValuationMark:
    return ValuationMark(
        instrument_id=instrument_id,
        price=Decimal(price),
        currency="USD",
        source="test",
        source_time_ns=1_000,
        observed_at_ns=1_000,
    )


class RiskDoesNotRankTests(unittest.TestCase):
    def test_handoff_authority_is_risk_not_ranking(self) -> None:
        report = evaluate_ranked_opportunity_handoff(
            _intent(),
            context=_context(),
        )
        self.assertEqual(report.authority, HANDOFF_AUTHORITY)
        self.assertEqual(HANDOFF_AUTHORITY, "G2_G3_RISK_NOT_RANKING")

    def test_handoff_payload_omits_ranking_fields(self) -> None:
        report = evaluate_ranked_opportunity_handoff(
            _intent(rank_order=1, rank_score=0.99, ranking_vector={"basis": "STUB"}),
            context=_context(),
        )
        payload = report.to_dict()
        leaked = RANKING_PAYLOAD_KEYS.intersection(payload)
        self.assertFalse(leaked)
        self.assertNotIn("rank_order", payload)
        self.assertNotIn("rank_score", payload)
        self.assertNotIn("ranking_vector", payload)
        field_names = {item.name for item in dataclasses.fields(type(report))}
        self.assertFalse(RANKING_PAYLOAD_KEYS.intersection(field_names))

    def test_pretrade_and_book_decisions_have_no_rank_fields(self) -> None:
        pretrade_fields = {item.name for item in dataclasses.fields(PreTradeRiskContext)}
        self.assertFalse(RANKING_PAYLOAD_KEYS.intersection(pretrade_fields))
        decision = evaluate_pretrade(_context())
        decision_fields = {item.name for item in dataclasses.fields(type(decision))}
        self.assertFalse(RANKING_PAYLOAD_KEYS.intersection(decision_fields))

    def test_evaluate_risk_ignores_rank_payload_on_intent(self) -> None:
        intent = {
            "intent_id": "i-1",
            "instrument_id": "AAPL",
            "direction": "long",
            "desired_quantity": 10,
            "rank_order": 1,
            "rank_score": 0.99,
        }
        approved = evaluate_risk(
            intent=intent,
            policy=DEFAULT_RISK_POLICY,
            kill_switch=KillSwitchState(active=False),
            current_position_shares=0,
            open_order_count=0,
        )
        self.assertEqual(approved["decision"], "APPROVE")
        self.assertNotIn("rank_order", approved)
        self.assertNotIn("rank_score", approved)


class RankingCannotBypassRiskTests(unittest.TestCase):
    def test_rank_one_still_rejected_when_g3_cash_insufficient(self) -> None:
        context = _context(quantity=1001, limit_price_minor=1000)
        report = evaluate_ranked_opportunity_handoff(
            _intent(rank_order=1, rank_score=1.0),
            context=context,
        )
        self.assertFalse(report.accepted)
        self.assertEqual(report.decision, "REJECT")
        self.assertIn("INSUFFICIENT_CASH", report.reason_codes)
        self.assertFalse(report.pretrade.accepted)

    def test_rank_order_does_not_change_g3_decision(self) -> None:
        context = _context(quantity=50, limit_price_minor=1000)
        first = evaluate_ranked_opportunity_handoff(_intent(rank_order=1), context=context)
        last = evaluate_ranked_opportunity_handoff(_intent(rank_order=99), context=context)
        self.assertEqual(first.accepted, last.accepted)
        self.assertEqual(first.decision, last.decision)
        self.assertEqual(first.reason_codes, last.reason_codes)
        self.assertEqual(first.pretrade.required_cash_minor, last.pretrade.required_cash_minor)

    def test_kill_switch_rejects_rank_one(self) -> None:
        report = evaluate_ranked_opportunity_handoff(
            _intent(rank_order=1),
            context=_context(),
            kill_switch=KillSwitchState(active=True, reason_code="HALT"),
        )
        self.assertFalse(report.accepted)
        self.assertEqual(report.decision, "REJECT")
        self.assertIn(REJECT_KILL_SWITCH, report.reason_codes)

    def test_g2_book_limit_rejects_rank_one(self) -> None:
        reset_registry_for_tests()
        book = _paper_book()
        book.upsert_position(_equity("AAPL", "100"))
        book.apply_mark(_mark("AAPL", "10"))
        report = evaluate_ranked_opportunity_handoff(
            _intent(rank_order=1),
            context=_context(),
            portfolio=book,
            book_policy=BookLimitPolicy(currency="USD", max_gross_exposure=Decimal("500")),
        )
        self.assertFalse(report.accepted)
        self.assertIn("GROSS_EXPOSURE_LIMIT", report.reason_codes)
        self.assertIsNotNone(report.book_exposure)
        self.assertFalse(report.book_exposure.within_limits)
        self.assertEqual(book.get_position("AAPL").quantity, Decimal("100"))

    def test_live_ranked_opportunity_is_observational_never_accepted(self) -> None:
        report = evaluate_ranked_opportunity_handoff(
            _intent(mode="LIVE", rank_order=1),
            context=_context(mode="LIVE"),
        )
        self.assertFalse(report.accepted)
        self.assertEqual(report.decision, "REJECT")
        self.assertIn(LIVE_OBSERVATIONAL_NO_EXECUTION, report.reason_codes)
        self.assertTrue(report.pretrade.accepted)

    def test_ranked_engine_row_cannot_bypass_insufficient_cash(self) -> None:
        rows = assemble_opportunity_review_rows(
            opportunities=(
                _opportunity("opp-loud", "AAPL"),
                _opportunity("opp-quiet", "MSFT"),
            ),
            assessments_by_opportunity={
                "opp-loud": AssessmentAction.EMIT,
                "opp-quiet": AssessmentAction.EMIT,
            },
        )
        ranked = rank_review_rows(rows)
        top = ranked[0]
        self.assertEqual(top.rank_order, 1)
        intent = intent_from_ranked_summary(top, quantity=1001)
        report = evaluate_ranked_opportunity_handoff(
            intent,
            context=_context(
                instrument_id=intent.instrument_id,
                quantity=1001,
                limit_price_minor=1000,
            ),
        )
        self.assertFalse(report.accepted)
        self.assertIn("INSUFFICIENT_CASH", report.reason_codes)

    def test_summary_accepted_flag_is_not_risk_authority(self) -> None:
        summary = OpportunitySummary(
            summary_id="s-1",
            instrument_id="AAPL",
            headline="pipeline accepted",
            accepted=True,
            rank_order=1,
            opportunity_id="opp-1",
            account_id="acct-1",
            mode="PAPER",
            side="LONG",
        )
        intent = intent_from_ranked_summary(summary, quantity=1001)
        report = evaluate_ranked_opportunity_handoff(
            intent,
            context=_context(quantity=1001, limit_price_minor=1000),
        )
        self.assertTrue(summary.accepted)
        self.assertFalse(report.accepted)

    def test_identity_mismatch_fails_closed(self) -> None:
        report = evaluate_ranked_opportunity_handoff(
            _intent(instrument_id="MSFT", rank_order=1),
            context=_context(instrument_id="AAPL"),
        )
        self.assertFalse(report.accepted)
        self.assertIn("HANDOFF_IDENTITY_MISMATCH", report.reason_codes)


if __name__ == "__main__":
    unittest.main()
