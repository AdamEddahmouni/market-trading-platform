"""Tests for Market Context contracts (MC1 foundation)."""

from __future__ import annotations

import sys
import unittest
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.contracts.market_context import (  # noqa: E402
    BaselineFinancialSentiment,
    BaselineSentimentModel,
    CatalystEvidence,
    ContextQualityFlag,
    ExpectationSnapshot,
    InformationDecayClass,
    InformationSource,
    InformationSourceType,
    MarketReactionEvidence,
    ModelVersionRef,
    PublicationState,
    ReactionConfirmationState,
    SemanticSentimentLabel,
    baseline_sentiment_to_dict,
    catalyst_evidence_to_dict,
    market_reaction_evidence_to_dict,
    surprise_unavailable_when_expectation_missing,
)


class MarketContextContractTests(unittest.TestCase):
    def test_baseline_sentiment_separate_from_surprise(self) -> None:
        model_ref = ModelVersionRef(
            model_id="ProsusAI/finbert",
            model_version="baseline-v1",
            schema_version="market_context.v1",
        )
        sentiment = BaselineFinancialSentiment(
            target_entity_id="NVDA",
            label=SemanticSentimentLabel.POSITIVE,
            confidence=0.91,
            uncertainty_score=0.12,
            model=BaselineSentimentModel.FINBERT_BASELINE,
            model_version=model_ref,
            event_time="2025-08-20T12:00:00Z",
            available_time="2025-08-20T12:00:05Z",
            publication_state=PublicationState.PUBLISHED,
        )
        payload = baseline_sentiment_to_dict(sentiment)
        self.assertEqual(payload["label"], "positive")
        self.assertEqual(payload["model"], "BaselineFinancialSentiment/FinBERT")
        self.assertNotIn("surprise", payload)

    def test_catalyst_evidence_exposes_components(self) -> None:
        catalyst = CatalystEvidence(
            event_id="evt-1",
            entity_ids=("NVDA",),
            catalyst_strength=0.82,
            novelty_score=0.9,
            surprise_score=-0.15,
            materiality_score=0.7,
            credibility_score=0.95,
            semantic_sentiment=SemanticSentimentLabel.POSITIVE,
            event_time="2025-08-20T12:00:00Z",
            available_time="2025-08-20T12:00:05Z",
            publication_state=PublicationState.PUBLISHED,
        )
        payload = catalyst_evidence_to_dict(catalyst)
        self.assertEqual(payload["surprise_score"], -0.15)
        self.assertEqual(payload["semantic_sentiment"], "positive")

    def test_missing_expectation_fails_closed_for_surprise(self) -> None:
        surprise, flags = surprise_unavailable_when_expectation_missing(
            None,
            actual_present=True,
        )
        self.assertIsNone(surprise)
        self.assertIn(ContextQualityFlag.EXPECTATION_MISSING.value, flags)
        self.assertIn(ContextQualityFlag.SURPRISE_UNAVAILABLE.value, flags)

    def test_information_source_point_in_time_fields(self) -> None:
        source = InformationSource(
            source_id="src-1",
            source_type=InformationSourceType.NEWSWIRE,
            publisher="Reuters",
            author=None,
            domain="reuters.com",
            primary_or_secondary="secondary",
            official=False,
            first_party=False,
            source_tier="tier_1",
            source_origin_id="origin-1",
            syndication_parent_id=None,
            provider="fixture.news",
            event_time="2025-08-20T11:59:00Z",
            available_time="2025-08-20T12:00:00Z",
            ingested_time="2025-08-20T12:00:01Z",
        )
        self.assertLessEqual(source.event_time, source.available_time)

    def test_expectation_snapshot_requires_available_time(self) -> None:
        snap = ExpectationSnapshot(
            metric_name="revenue",
            entity_id="NVDA",
            expected_value=Decimal("30.5"),
            median=Decimal("30.5"),
            high=Decimal("31.0"),
            low=Decimal("29.8"),
            dispersion=Decimal("0.4"),
            sample_size=28,
            source="analyst_consensus.fixture",
            event_time="2025-08-20T08:00:00Z",
            available_time="2025-08-20T08:00:00Z",
            publication_state=PublicationState.PUBLISHED,
        )
        self.assertEqual(snap.metric_name, "revenue")
        self.assertEqual(snap.sample_size, 28)

    def test_market_reaction_evidence_serializes_information_decay(self) -> None:
        evidence = MarketReactionEvidence(
            entity_id="BOXL",
            event_id="evt-1",
            semantic_direction="BULLISH",
            predicted_economic_direction="BULLISH",
            observed_market_direction="BULLISH",
            reaction_mismatch=False,
            confirmation_state=ReactionConfirmationState.CONFIRMED,
            abnormal_return=0.02,
            volume_multiple=1.5,
            priced_in_probability=0.4,
            remaining_information_edge=0.08,
            information_decay_class=InformationDecayClass.HOURS,
            horizon="1D",
            event_time="2026-07-15T14:30:00.000000000Z",
            available_time="2026-07-15T14:45:00.000000000Z",
            publication_state=PublicationState.PUBLISHED,
        )
        payload = market_reaction_evidence_to_dict(evidence)
        self.assertEqual(payload["information_decay_class"], "HOURS")
        self.assertEqual(payload["priced_in_probability"], 0.4)
        self.assertEqual(payload["remaining_information_edge"], 0.08)


if __name__ == "__main__":
    unittest.main()
