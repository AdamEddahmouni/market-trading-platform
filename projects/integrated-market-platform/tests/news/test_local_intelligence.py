"""Scheduled local intelligence: windows, attribution, checkpoints, no lookahead, read-only store."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.news.local_intelligence import (
    DIRECTORY_ENV, DerivedEvidenceLog, LocalIntelligenceWorker, ReadOnlyStore, rank, read_view,
)

REGULAR = datetime(2026, 10, 14, 14, 0, tzinfo=UTC).timestamp()   # Wednesday 10:00 New York
PAUSE = datetime(2026, 10, 14, 5, 30, tzinfo=UTC).timestamp()     # Wednesday 01:30 New York
CATCH_UP = datetime(2026, 10, 14, 7, 40, tzinfo=UTC).timestamp()  # Wednesday 03:40 New York


def _iso(seconds: float) -> str:
    return datetime.fromtimestamp(seconds, UTC).isoformat().replace("+00:00", "Z")


def _record(record_id: str, provider: str, headline: str, ingested: float, *, symbol: str | None = None,
            source_type: str = "NEWS") -> tuple:
    article = dict(event_id="e-" + record_id, provider_id=provider, provider_native_id=record_id, source_id=provider + "-src",
                   published_time=_iso(ingested - 60), retrieved_time=_iso(ingested), headline=headline, summary="",
                   url=f"https://example.invalid/{record_id}",
                   instrument_linkages=[dict(instrument_id=symbol, provider_symbol=symbol)] if symbol else [])
    payload = dict(article=article, provenance=dict(source_type=source_type))
    return (record_id, provider, provider + "-src", article["published_time"], article["retrieved_time"], ingested,
            json.dumps(payload))


class FakeScorer:
    def __init__(self, state: str = "SCORED") -> None:
        self.state, self.calls = state, []

    def score(self, texts):
        self.calls.append(list(texts))
        if self.state != "SCORED":
            return [dict(state="NOT_SCORED", reason="MODEL_LOADING", label=None, probabilities=None) for _ in texts]
        return [dict(state="SCORED", label="NEGATIVE" if "falls" in t else "POSITIVE",
                     probabilities=dict(positive=.8, neutral=.1, negative=.1), model_id="ProsusAI/finbert") for t in texts]

    def status(self):
        return dict(state="CURRENT", model_id="ProsusAI/finbert", model_revision="abc123")


class LocalIntelligenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.db = self.tmp / "imp-state.sqlite3"
        with sqlite3.connect(self.db) as con:
            con.execute("CREATE TABLE news_collection_records (record_id TEXT PRIMARY KEY, provider_id TEXT, source_id TEXT, "
                        "published_time TEXT, retrieved_time TEXT, ingested_time REAL, payload_json TEXT)")
            con.executemany("INSERT INTO news_collection_records VALUES (?,?,?,?,?,?,?)", [
                _record("a", "rss", "Stocks rally on rate cut hopes", PAUSE - 600),
                _record("b", "finnhub", "Apple shares falls after downgrade", PAUSE - 300, symbol="AAPL"),
                _record("c", "sec_filings", "Apple Inc. filed 8-K", PAUSE - 100, symbol="AAPL", source_type="OFFICIAL_FILING"),
                _record("late", "rss", "Market opens higher", REGULAR + 3600),  # not yet known at REGULAR
            ])
        self.digest = hashlib.sha256(self.db.read_bytes()).hexdigest()
        self.out = self.tmp / "derived"
        self.scorer = FakeScorer()
        self.clock = [PAUSE]

    def worker(self, **kwargs) -> LocalIntelligenceWorker:
        return LocalIntelligenceWorker(ReadOnlyStore(self.db), DerivedEvidenceLog(self.out),
                                       scorer_factory=lambda: self.scorer, clock=lambda: self.clock[0], **kwargs)

    def test_pause_window_runs_no_inference_but_reports_the_backlog(self) -> None:
        result = self.worker().tick()
        self.assertEqual((result["state"], result["session"]["window"], result["processed"]), ("PAUSED", "INFERENCE_PAUSE", 0))
        self.assertEqual(result["backlog"], 3)
        self.assertEqual(self.scorer.calls, [])
        self.assertEqual(read_view(self.out)["outputs"], [])

    def test_catch_up_processes_with_attribution_and_without_lookahead(self) -> None:
        self.clock[0] = CATCH_UP
        result = self.worker().tick()
        self.assertEqual((result["state"], result["session"]["window"], result["processed"], result["scored"]),
                         ("PROCESSED", "CATCH_UP", 3, 2))
        self.assertEqual(result["paid_inference_calls"], 0)
        outputs = {row["revision_id"]: row for row in read_view(self.out)["outputs"]}
        self.assertEqual(set(outputs), {"a", "b", "c"})  # "late" was not yet known
        self.assertEqual(outputs["b"]["sentiment"]["label"], "NEGATIVE")
        self.assertEqual(outputs["b"]["sentiment_model"]["model_id"], "ProsusAI/finbert")
        self.assertEqual(outputs["b"]["instrument_ids"], ["AAPL"])
        self.assertEqual(outputs["c"]["sentiment"]["state"], "NOT_APPLICABLE")  # official filings are not sentiment-scored
        self.assertIsNone(outputs["c"]["sentiment_model"])
        for row in outputs.values():
            self.assertLessEqual(row["input_available_time"], row["processed_at"])
            self.assertEqual(row["execution_authority"], "NONE")
        self.assertEqual(hashlib.sha256(self.db.read_bytes()).hexdigest(), self.digest)  # canonical store untouched

    def test_restart_does_not_reprocess_and_new_evidence_is_picked_up(self) -> None:
        self.clock[0] = CATCH_UP
        self.worker().tick()
        self.clock[0] = REGULAR
        again = self.worker().tick()  # a new process: the checkpoint is the only memory
        self.assertEqual((again["state"], again["processed"]), ("IDLE", 0))
        self.clock[0] = REGULAR + 7200
        later = self.worker().tick()
        self.assertEqual((later["processed"], later["backlog"]), (1, 0))
        rows = read_view(self.out, limit=50)["outputs"]
        self.assertEqual(sorted(row["revision_id"] for row in rows), ["a", "b", "c", "late"])

    def test_as_of_view_hides_later_processing(self) -> None:
        self.clock[0] = CATCH_UP
        self.worker().tick()
        self.assertEqual(read_view(self.out, as_of=CATCH_UP - 1)["outputs"], [])
        self.assertEqual(len(read_view(self.out, as_of=CATCH_UP + 1)["outputs"]), 3)
        self.assertEqual([row["revision_id"] for row in read_view(self.out, symbol="AAPL")["outputs"]].count("b"), 1)

    def test_unscored_items_are_retried_not_acknowledged(self) -> None:
        self.clock[0] = REGULAR
        self.scorer = FakeScorer(state="LOADING")
        first = self.worker().tick()
        self.assertEqual((first["processed"], first["deferred"]), (1, 2))  # only the filing is complete
        self.scorer = FakeScorer()
        second = self.worker().tick()
        self.assertEqual(second["processed"], 2)

    def test_storage_bound_blocks_without_deleting(self) -> None:
        self.clock[0] = REGULAR
        self.out.mkdir()
        (self.out / "outputs-2026-10-13.jsonl").write_text("x" * 200, encoding="utf-8")
        result = self.worker(max_directory_bytes=100).tick()
        self.assertEqual((result["state"], result["reason"]), ("BLOCKED", "DERIVED_EVIDENCE_BOUND_REACHED"))
        self.assertTrue((self.out / "outputs-2026-10-13.jsonl").exists())

    def test_rank_puts_linked_and_official_first(self) -> None:
        rows = [dict(revision_id=n, available_at_ns=t, article=dict(instrument_linkages=[1] if linked else []),
                     provenance=dict(source_type=kind)) for n, t, linked, kind in
                [("plain-new", 3, False, "NEWS"), ("linked", 1, True, "NEWS"), ("official", 2, True, "OFFICIAL_FILING")]]
        self.assertEqual([row["revision_id"] for row in rank(rows)], ["official", "linked", "plain-new"])

    def test_evidence_review_view_reads_the_configured_directory(self) -> None:
        from market_platform_foundation.ui_api.evidence_review import EvidenceReviewService

        self.clock[0] = CATCH_UP
        self.worker().tick()
        service = EvidenceReviewService(store=None, clock=lambda: CATCH_UP + 60)
        with mock.patch.dict(os.environ, {DIRECTORY_ENV: str(self.out)}):
            view = service.intelligence(symbol="aapl")
        self.assertEqual(view["schema_version"], "evidence-review-intelligence/1")
        self.assertEqual(sorted(row["revision_id"] for row in view["outputs"]), ["b", "c"])
        self.assertEqual(view["authority"]["inference_calls"], 0)
        with mock.patch.dict(os.environ, {DIRECTORY_ENV: ""}):
            self.assertEqual(service.intelligence()["state"], "NOT_CONFIGURED")


if __name__ == "__main__":
    unittest.main()
