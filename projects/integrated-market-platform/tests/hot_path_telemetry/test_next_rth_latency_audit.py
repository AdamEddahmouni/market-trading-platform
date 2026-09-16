"""Lock next-RTH hop classification and honest delta behavior."""

from __future__ import annotations

import unittest

from market_platform_foundation.hot_path_telemetry.next_rth_latency_audit import (
    DeltaId,
    HopClassification,
    HopClockSnapshot,
    HopId,
    ack_created_at_is_usable,
    classification_table,
    compute_next_rth_deltas,
    event_v1_clocks_are_eligibility_not_processing,
    hop_classification,
    merge_snapshots,
    patch_plan,
    snapshot_from_event_v1,
    snapshot_from_news_article,
)
from market_platform_foundation.intelligence.contracts.common import (
    QualityState,
    QualitySummary,
    SourceReference,
)
from market_platform_foundation.intelligence.contracts.event import EventV1
from market_platform_foundation.news.contracts import NewsArticleEvent, PublicationTimeQuality


def _event_v1(*, event_time: int, available: int, received: int | None, provider: int | None = None) -> EventV1:
    return EventV1(
        event_id="evt-next-rth-1",
        schema_version="1",
        event_type="QUOTE",
        event_time_ns=event_time,
        available_time_ns=available,
        payload={},
        quality=QualitySummary(state=QualityState.GOOD),
        source=SourceReference(
            provider_id="moomoo.opend",
            source_type="QUOTE",
            source_record_id="seq-1",
        ),
        provider_time_ns=provider,
        received_time_ns=received,
    )


class NextRthLatencyAuditTests(unittest.TestCase):
    def test_catalog_classifications_are_frozen(self) -> None:
        expected = {
            HopId.SOURCE_PUBLICATION: HopClassification.AVAILABLE,
            HopId.PROVIDER_RETRIEVAL: HopClassification.AMBIGUOUS,
            HopId.IMP_RECEIVE: HopClassification.AVAILABLE,
            HopId.NORMALIZATION: HopClassification.AMBIGUOUS,
            HopId.DETECTOR: HopClassification.AMBIGUOUS,
            HopId.OPPORTUNITY_CREATION: HopClassification.AMBIGUOUS,
            HopId.RANKED_BOOK: HopClassification.MISSING,
            HopId.API_RESPONSE: HopClassification.MISSING,
            HopId.UI_FIRST_VISIBLE: HopClassification.MISSING,
            HopId.OPERATOR_ACTION: HopClassification.AMBIGUOUS,
        }
        for hop, klass in expected.items():
            self.assertEqual(hop_classification(hop).classification, klass)
        table = classification_table()
        self.assertEqual(len(table), 10)

    def test_target_delta_classes(self) -> None:
        deltas = compute_next_rth_deltas(HopClockSnapshot())
        self.assertEqual(deltas[DeltaId.SOURCE_TO_RECEIVE.value]["classification"], "DERIVABLE")
        self.assertEqual(deltas[DeltaId.RECEIVE_TO_NORMALIZATION.value]["classification"], "AMBIGUOUS")
        self.assertEqual(deltas[DeltaId.OPPORTUNITY_TO_UI.value]["classification"], "MISSING")
        self.assertEqual(deltas[DeltaId.UI_TO_OPERATOR.value]["classification"], "MISSING")
        self.assertEqual(deltas[DeltaId.SOURCE_TO_OPERATOR.value]["classification"], "AMBIGUOUS")
        self.assertFalse(deltas[DeltaId.SOURCE_TO_RECEIVE.value]["pair_present"])
        self.assertIsNone(deltas[DeltaId.SOURCE_TO_RECEIVE.value]["delta_ns"])

    def test_news_known_publication_derives_source_to_receive(self) -> None:
        article = NewsArticleEvent(
            event_id="news-1",
            provider_id="finviz",
            provider_native_id="fv-1",
            source_id="finviz_elite",
            published_time="2024-01-15T14:30:00Z",
            published_time_quality=PublicationTimeQuality.KNOWN,
            retrieved_time="2024-01-15T14:30:05Z",
            headline="Example",
        )
        snapshot = snapshot_from_news_article(article)
        deltas = compute_next_rth_deltas(snapshot)
        self.assertTrue(deltas[DeltaId.SOURCE_TO_RECEIVE.value]["pair_present"])
        self.assertEqual(deltas[DeltaId.SOURCE_TO_RECEIVE.value]["delta_ns"], 5_000_000_000)
        self.assertIsNone(snapshot.provider_retrieval_ns)
        self.assertIsNone(snapshot.ui_first_visible_ns)

    def test_unknown_publication_does_not_invent_source_clock(self) -> None:
        article = NewsArticleEvent(
            event_id="news-2",
            provider_id="finviz",
            provider_native_id="fv-2",
            source_id="finviz_elite",
            published_time="",
            published_time_quality=PublicationTimeQuality.UNKNOWN,
            retrieved_time="2024-01-15T14:30:05Z",
            headline="Example",
        )
        snapshot = snapshot_from_news_article(article)
        self.assertIsNone(snapshot.source_publication_ns)
        self.assertFalse(compute_next_rth_deltas(snapshot)[DeltaId.SOURCE_TO_RECEIVE.value]["pair_present"])

    def test_event_v1_available_alias_is_not_a_normalize_hop(self) -> None:
        event = _event_v1(event_time=10, available=20, received=20, provider=10)
        self.assertTrue(event_v1_clocks_are_eligibility_not_processing(event))
        snapshot = snapshot_from_event_v1(event)
        deltas = compute_next_rth_deltas(snapshot)
        self.assertEqual(deltas[DeltaId.RECEIVE_TO_NORMALIZATION.value]["delta_ns"], 0)
        self.assertEqual(deltas[DeltaId.RECEIVE_TO_NORMALIZATION.value]["classification"], "AMBIGUOUS")

    def test_missing_ui_and_ranked_hops_never_zero_fill(self) -> None:
        snapshot = HopClockSnapshot(
            source_publication_ns=1,
            imp_receive_ns=2,
            opportunity_created_ns=3,
            operator_action_ns=0,
        )
        deltas = compute_next_rth_deltas(snapshot)
        self.assertFalse(deltas[DeltaId.OPPORTUNITY_TO_UI.value]["pair_present"])
        self.assertIsNone(deltas[DeltaId.OPPORTUNITY_TO_UI.value]["delta_ns"])
        self.assertFalse(deltas[DeltaId.UI_TO_OPERATOR.value]["pair_present"])
        self.assertFalse(ack_created_at_is_usable(snapshot.operator_action_ns))

    def test_merge_does_not_overwrite_with_none(self) -> None:
        left = HopClockSnapshot(source_publication_ns=10, imp_receive_ns=20)
        right = HopClockSnapshot(detector_ns=30, imp_receive_ns=None)
        merged = merge_snapshots(left, right)
        self.assertEqual(merged.imp_receive_ns, 20)
        self.assertEqual(merged.detector_ns, 30)

    def test_patch_plan_keeps_schema_on_p1(self) -> None:
        plan = patch_plan()
        self.assertTrue(any("EventV1" in item for item in plan["p1_schema_do_not_edit"]))
        self.assertTrue(any("zero-fill" in item for item in plan["forbidden"]))


if __name__ == "__main__":
    unittest.main()
