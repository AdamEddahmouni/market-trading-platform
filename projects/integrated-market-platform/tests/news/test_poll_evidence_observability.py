"""Bounded poll rejection observability and campaign-evidence envelope tests."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from market_platform_foundation.news.contracts import (
    FilterDecision,
    FilterStage,
    InstrumentLinkage,
    NewsArticleEvent,
    PipelineEventResult,
    PublicationTimeQuality,
)
from market_platform_foundation.news.poll_evidence import (
    UNAVAILABLE,
    UNKNOWN,
    CampaignEvidenceRetentionPolicy,
    build_poll_evidence_envelope,
    build_poll_rejection_summary,
    digest_fetched_item,
    redact_headline,
    retain_poll_evidence_manifest,
    scrub_secrets,
)
from market_platform_foundation.news.timestamps import epoch_ns_from_iso
from market_platform_foundation.ui_api.news_ingest_mode import select_news_ingest_ingestion_mode
from market_platform_foundation.intelligence.normalization.models import IngestionMode


def _event(
    *,
    event_id: str,
    headline: str,
    symbol: str = "ACME",
    published: str = "2026-09-22T14:00:00Z",
    retrieved: str = "2026-09-22T14:05:00Z",
    quality: PublicationTimeQuality = PublicationTimeQuality.KNOWN,
    source_id: str = "finviz_elite",
    url: str = "",
) -> NewsArticleEvent:
    linkages = ()
    if symbol:
        linkages = (
            InstrumentLinkage(
                instrument_id=symbol,
                provider_symbol=symbol,
                asset_class="EQUITY",
                linkage_method="PROVIDER_SYMBOL",
            ),
        )
    return NewsArticleEvent(
        event_id=event_id,
        provider_id="finviz",
        provider_native_id=event_id,
        source_id=source_id,
        published_time=published,
        published_time_quality=quality,
        retrieved_time=retrieved,
        headline=headline,
        url=url or f"https://news.example/{event_id}",
        instrument_linkages=linkages,
        publisher_source="Wire",
    )


def _reject(
    event: NewsArticleEvent,
    *,
    stage: FilterStage,
    reason: str | None,
) -> PipelineEventResult:
    return PipelineEventResult(
        event=event,
        accepted=False,
        decisions=(
            FilterDecision(
                stage=stage,
                accepted=False,
                reason_code=reason or "",
            ),
        ),
    )


def _accept(event: NewsArticleEvent) -> PipelineEventResult:
    return PipelineEventResult(
        event=event,
        accepted=True,
        decisions=(
            FilterDecision(
                stage=FilterStage.CATALYST_KEYWORD,
                accepted=True,
                reason_code="CATALYST_MATCHED",
                matched_catalyst_ids=("earnings",),
            ),
        ),
    )


class PollRejectionSummaryTests(unittest.TestCase):
    def test_mixed_batch_bucket_counts(self) -> None:
        universe = frozenset({"ACME", "BETA"})
        events = [
            _event(event_id="e1", headline="ACME earnings beat", symbol="ACME"),
            _event(event_id="e2", headline="GAMMA merger rumor", symbol="GAMMA"),
            _event(event_id="e3", headline="Old ACME note", symbol="ACME"),
            _event(event_id="e4", headline="Untrusted wire", symbol="ACME", source_id="unknown_src"),
            _event(event_id="e5", headline="No catalyst text", symbol="ACME"),
            _event(event_id="e6", headline="Missing symbol row", symbol=""),
            _event(
                event_id="e7",
                headline="Inferred pub",
                symbol="ACME",
                quality=PublicationTimeQuality.INFERRED_LOW_CONFIDENCE,
            ),
            _event(
                event_id="e8",
                headline="Unknown pub",
                symbol="ACME",
                quality=PublicationTimeQuality.UNKNOWN,
                published="",
            ),
        ]
        results = [
            _accept(events[0]),
            _accept(events[1]),  # universe filtered
            _reject(events[2], stage=FilterStage.RECENCY, reason="RECENCY_EXCEEDS_TTL"),
            _reject(events[3], stage=FilterStage.SOURCE_POLICY, reason="SOURCE_UNKNOWN"),
            _reject(events[4], stage=FilterStage.CATALYST_KEYWORD, reason="CATALYST_NO_MATCH"),
            _accept(events[5]),  # missing identity after accept
            _reject(events[6], stage=FilterStage.OBSERVABILITY, reason="OBSERVABILITY_LOOKAHEAD"),
            _reject(events[7], stage=FilterStage.RECENCY, reason=None),  # UNKNOWN reason
        ]
        # duplicate
        dup = PipelineEventResult(
            event=_event(event_id="e9", headline="Dup", symbol="ACME"),
            accepted=False,
            decisions=(
                FilterDecision(
                    stage=FilterStage.DEDUPLICATION,
                    accepted=False,
                    reason_code="DUPLICATE",
                ),
            ),
            duplicate_of="e1",
        )
        results.append(dup)
        events.append(dup.event)

        summary = build_poll_rejection_summary(
            fetched_count=10,
            events=events,
            results=results,
            universe=universe,
            normalization_fail_count=1,
        )
        counts = summary.counts
        self.assertEqual(counts["fetched"], 10)
        self.assertEqual(counts["normalization_success"], 9)
        self.assertEqual(counts["normalization_fail"], 1)
        self.assertEqual(counts["publication_known"], 7)
        self.assertEqual(counts["publication_inferred"], 1)
        self.assertEqual(counts["publication_unknown"], 1)
        self.assertEqual(counts["recency_reject"], 2)
        self.assertEqual(counts["source_filter_reject"], 1)
        self.assertEqual(counts["catalyst_reject"], 1)
        self.assertEqual(counts["observability_reject"], 1)
        self.assertEqual(counts["pipeline_accepted"], 3)
        self.assertEqual(counts["universe_filtered"], 1)
        self.assertEqual(counts["missing_identity"], 1)
        self.assertEqual(counts["duplicate_already_present"], 1)
        self.assertEqual(counts["pre_window"], UNAVAILABLE)
        self.assertEqual(counts["post_window_or_current_candidate"], UNAVAILABLE)
        self.assertEqual(counts["pit_reject"], UNAVAILABLE)
        self.assertEqual(counts["event_v1_persisted"], UNAVAILABLE)
        self.assertEqual(counts["opportunity_v1_minted"], UNAVAILABLE)
        self.assertEqual(counts["ranked"], UNAVAILABLE)
        self.assertEqual(summary.reason_buckets.get(UNKNOWN), 1)
        self.assertEqual(summary.reason_buckets.get("UNIVERSE_FILTERED"), 1)

    def test_unknown_when_reason_missing(self) -> None:
        event = _event(event_id="e1", headline="x")
        result = _reject(event, stage=FilterStage.RECENCY, reason="")
        summary = build_poll_rejection_summary(
            fetched_count=1,
            events=[event],
            results=[result],
            universe=frozenset({"ACME"}),
        )
        self.assertEqual(summary.reason_buckets.get(UNKNOWN), 1)
        self.assertEqual(summary.counts["recency_reject"], 1)

    def test_secrets_not_present_in_summary(self) -> None:
        event = _event(
            event_id="e1",
            headline="Leak auth=super-secret-token and api_key=abc",
            url="https://elite.example/news?auth=super-secret-token",
        )
        result = _reject(event, stage=FilterStage.SOURCE_POLICY, reason="SOURCE_UNKNOWN")
        summary = build_poll_rejection_summary(
            fetched_count=1,
            events=[event],
            results=[result],
            universe=frozenset({"ACME"}),
        )
        payload = summary.to_dict()
        blob = json.dumps(payload)
        self.assertNotIn("super-secret-token", blob)
        self.assertNotIn("api_key=abc", blob)
        scrubbed = scrub_secrets(
            {"api_key": "should-not-leak", "token": "nope", "counts": {"fetched": 1}},
            secret="should-not-leak",
        )
        self.assertEqual(scrubbed["api_key"], "<REDACTED>")
        self.assertEqual(scrubbed["token"], "<REDACTED>")

    def test_window_buckets_when_observation_window_supplied(self) -> None:
        window = epoch_ns_from_iso("2026-09-22T13:30:00Z")
        assert window is not None
        pre = _event(
            event_id="pre",
            headline="before",
            published="2026-09-22T13:00:00Z",
        )
        post = _event(
            event_id="post",
            headline="after",
            published="2026-09-22T14:00:00Z",
        )
        summary = build_poll_rejection_summary(
            fetched_count=2,
            events=[pre, post],
            results=[_accept(pre), _accept(post)],
            universe=frozenset({"ACME"}),
            observation_window_start_ns=window,
        )
        self.assertEqual(summary.counts["pre_window"], 1)
        self.assertEqual(summary.counts["post_window_or_current_candidate"], 1)


class PollEvidenceRetentionTests(unittest.TestCase):
    def test_digests_stable(self) -> None:
        item = {
            "provider_native_id": "finviz:abc",
            "url": "https://News.Example/Path/?auth=secret-token&utm=1",
            "headline": "  ACME Reports Beat  ",
            "tickers": ["acme", "BETA"],
            "published_time": "2026-09-22T14:00:00Z",
            "raw_fields": {"should": "not", "affect": "digest"},
        }
        first = digest_fetched_item(item)
        second = digest_fetched_item(dict(item))
        self.assertEqual(first, second)
        self.assertEqual(len(first), 64)
        # Query secrets must not change identity (url_identifier strips query).
        twin = dict(item)
        twin["url"] = "https://news.example/path"
        self.assertEqual(digest_fetched_item(twin), first)

    def test_retention_bounded(self) -> None:
        events = [
            _event(event_id=f"e{i}", headline=f"Headline {i} " + ("x" * 200), symbol="ACME")
            for i in range(5)
        ]
        results = [_accept(event) for event in events]
        items = [
            {
                "provider_native_id": event.provider_native_id,
                "url": event.url,
                "headline": event.headline,
                "tickers": ["ACME"],
                "published_time": event.published_time,
            }
            for event in events
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "poll-evidence-root"
            policy = CampaignEvidenceRetentionPolicy(
                enabled=True,
                max_items_per_poll=2,
                max_polls_retained=2,
                max_headline_chars=40,
                evidence_root=root,
            )
            for idx in range(3):
                envelope = build_poll_evidence_envelope(
                    poll_id=f"poll-{idx}",
                    as_of_ns=1_000 + idx,
                    fetched_items=items,
                    events=events,
                    results=results,
                    universe=frozenset({"ACME"}),
                    policy=policy,
                )
                self.assertLessEqual(len(envelope.items), 2)
                for row in envelope.items:
                    self.assertLessEqual(len(row.headline_redacted), 40)
                    self.assertNotIn("auth=", row.url_identifier)
                path = retain_poll_evidence_manifest(envelope, policy=policy)
                self.assertIsNotNone(path)
            manifests = list((root / "poll-evidence-manifests").glob("*.json"))
            self.assertEqual(len(manifests), 2)
            for path in manifests:
                body = json.loads(path.read_text(encoding="utf-8"))
                self.assertFalse(body.get("raw_payloads_retained"))
                self.assertLessEqual(body.get("item_count"), 2)
                blob = path.read_text(encoding="utf-8")
                self.assertNotIn("auth=", blob)

    def test_retention_refuses_rth_campaign_dirs(self) -> None:
        event = _event(event_id="e1", headline="x")
        envelope = build_poll_evidence_envelope(
            poll_id="poll-x",
            as_of_ns=1,
            fetched_items=[{"headline": "x", "tickers": ["ACME"]}],
            events=[event],
            results=[_accept(event)],
            universe=frozenset({"ACME"}),
        )
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "rth-campaign-20260922-B"
            bad.mkdir()
            policy = CampaignEvidenceRetentionPolicy(
                enabled=True,
                evidence_root=bad,
                max_items_per_poll=10,
                max_polls_retained=10,
            )
            self.assertIsNone(retain_poll_evidence_manifest(envelope, policy=policy))

            # Nested state/ under any rth-campaign-* date must also be refused.
            nested = Path(tmp) / "rth-campaign-20260921-A" / "state"
            nested.mkdir(parents=True)
            nested_policy = CampaignEvidenceRetentionPolicy(
                enabled=True,
                evidence_root=nested,
                max_items_per_poll=10,
                max_polls_retained=10,
            )
            self.assertIsNone(retain_poll_evidence_manifest(envelope, policy=nested_policy))
            self.assertEqual(list(nested.iterdir()), [])

            # Explicit non-campaign evidence root still retains.
            good = Path(tmp) / "poll-evidence-explicit"
            good_policy = CampaignEvidenceRetentionPolicy(
                enabled=True,
                evidence_root=good,
                max_items_per_poll=10,
                max_polls_retained=10,
            )
            retained = retain_poll_evidence_manifest(envelope, policy=good_policy)
            self.assertIsNotNone(retained)
            assert retained is not None
            self.assertTrue(retained.is_file())

    def test_headline_redacts_secret_query_params(self) -> None:
        # Bare secret= in headlines must not survive retention redaction.
        redacted = redact_headline(
            "ACME update secret=leaked-secret-value and access_token=tok123",
            max_chars=200,
        )
        self.assertNotIn("leaked-secret-value", redacted)
        self.assertNotIn("tok123", redacted)
        self.assertIn("secret=<REDACTED>", redacted)
        self.assertIn("access_token=<REDACTED>", redacted)

        event = _event(
            event_id="e-secret",
            headline="Probe row secret=leaked-secret-value auth=still-secret",
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "poll-evidence-root"
            policy = CampaignEvidenceRetentionPolicy(
                enabled=True,
                evidence_root=root,
                max_items_per_poll=10,
                max_polls_retained=10,
                max_headline_chars=200,
            )
            envelope = build_poll_evidence_envelope(
                poll_id="poll-secret",
                as_of_ns=1,
                fetched_items=[
                    {
                        "provider_native_id": event.provider_native_id,
                        "url": event.url,
                        "headline": event.headline,
                        "tickers": ["ACME"],
                        "published_time": event.published_time,
                    }
                ],
                events=[event],
                results=[_accept(event)],
                universe=frozenset({"ACME"}),
                policy=policy,
            )
            self.assertEqual(len(envelope.items), 1)
            self.assertNotIn("leaked-secret-value", envelope.items[0].headline_redacted)
            self.assertNotIn("still-secret", envelope.items[0].headline_redacted)
            path = retain_poll_evidence_manifest(envelope, policy=policy)
            self.assertIsNotNone(path)
            assert path is not None
            blob = path.read_text(encoding="utf-8")
            self.assertNotIn("leaked-secret-value", blob)
            self.assertNotIn("still-secret", blob)


class ModeSelectionUnchangedTests(unittest.TestCase):
    def test_fail_closed_mode_selection_unchanged(self) -> None:
        window = epoch_ns_from_iso("2026-09-22T13:30:00Z")
        assert window is not None
        published = epoch_ns_from_iso("2026-09-22T14:00:00Z")
        self.assertEqual(
            select_news_ingest_ingestion_mode(
                published_time_ns=published,
                published_time_quality=PublicationTimeQuality.KNOWN,
                observation_window_start_ns=window,
                live_gates_active=True,
            ),
            IngestionMode.LIVE_OBSERVED,
        )
        self.assertEqual(
            select_news_ingest_ingestion_mode(
                published_time_ns=published,
                published_time_quality=PublicationTimeQuality.KNOWN,
                observation_window_start_ns=None,
                live_gates_active=True,
            ),
            IngestionMode.HISTORICAL_RECONSTRUCTED,
        )
        self.assertEqual(
            select_news_ingest_ingestion_mode(
                published_time_ns=epoch_ns_from_iso("2026-09-22T12:00:00Z"),
                published_time_quality=PublicationTimeQuality.KNOWN,
                observation_window_start_ns=window,
                live_gates_active=True,
            ),
            IngestionMode.HISTORICAL_RECONSTRUCTED,
        )


if __name__ == "__main__":
    unittest.main()
