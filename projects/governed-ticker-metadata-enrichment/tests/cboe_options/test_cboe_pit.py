"""Cboe options statistics point-in-time behavior."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.cboe_options.contracts import CboeExchangeCode  # noqa: E402
from market_platform_foundation.cboe_options.daily import parse_daily_statistics_html  # noqa: E402
from market_platform_foundation.cboe_options.pit import reference_as_of, statistic_as_of  # noqa: E402
from market_platform_foundation.cboe_options.reference import parse_reference_csv  # noqa: E402
from market_platform_foundation.cboe_options.store import CboeOptionsStore  # noqa: E402

sys.path.insert(0, str(ROOT / "tests" / "cboe_options"))
from _helpers import INGESTED_TIME, RETRIEVED_TIME, daily_html, load_json, load_text


class CboePitDailyTests(unittest.TestCase):
    def test_daily_statistic_hidden_before_availability(self) -> None:
        payload = load_json("daily_stats_embedded.json")
        payload["lastUpdated"] = "2026-08-19T17:30:00-05:00"
        capture = parse_daily_statistics_html(
            daily_html(payload),
            retrieved_time=RETRIEVED_TIME,
            ingested_time=INGESTED_TIME,
        )
        before = statistic_as_of(
            capture.observations,
            decision_time="2026-08-19T17:00:00-05:00",
            canonical_statistic_id="TOTAL_PUT_CALL_RATIO",
            trade_date="2026-08-19",
        )
        after = statistic_as_of(
            capture.observations,
            decision_time="2026-08-19T18:00:00-05:00",
            canonical_statistic_id="TOTAL_PUT_CALL_RATIO",
            trade_date="2026-08-19",
        )
        self.assertIsNone(before)
        self.assertIsNotNone(after)

    def test_correction_visibility_preserves_prior_version(self) -> None:
        store = CboeOptionsStore()

        def _load_correction(name: str):
            payload = load_json(name)
            return parse_daily_statistics_html(
                daily_html(payload),
                retrieved_time=RETRIEVED_TIME,
                ingested_time=payload["availableTime"],
            )

        store.add_statistics(_load_correction("daily_correction_v1.json").observations)
        store.add_statistics(_load_correction("daily_correction_v2.json").observations)

        mid = store.statistic_as_of(
            canonical_statistic_id="EQUITY_EQUITY_VOLUME",
            trade_date="2026-08-19",
            decision_time="2026-08-20T08:00:00-05:00",
        )
        late = store.statistic_as_of(
            canonical_statistic_id="EQUITY_EQUITY_VOLUME",
            trade_date="2026-08-19",
            decision_time="2026-08-20T10:00:00-05:00",
        )
        self.assertIsNotNone(mid)
        self.assertIsNotNone(late)
        assert mid is not None and late is not None
        self.assertEqual(mid.normalized_value, 3822000)
        self.assertEqual(late.normalized_value, 3872000)


class CboePitReferenceTests(unittest.TestCase):
    def test_reference_version_selection_uses_hash_at_decision_time(self) -> None:
        url = "https://cdn.cboe.com/resources/options/reference_data/c1/all_series.csv"
        v1 = parse_reference_csv(
            load_text("reference_v1.csv"),
            exchange=CboeExchangeCode.C1,
            reference_category="all_series",
            source_url=url,
            retrieved_time=RETRIEVED_TIME,
            ingested_time="2026-08-19T08:00:00-05:00",
        ).observation
        v2 = parse_reference_csv(
            load_text("reference_v2.csv"),
            exchange=CboeExchangeCode.C1,
            reference_category="all_series",
            source_url=url,
            retrieved_time=RETRIEVED_TIME,
            ingested_time="2026-08-20T08:00:00-05:00",
        ).observation
        early = reference_as_of(
            [v1, v2],
            decision_time="2026-08-19T12:00:00-05:00",
            exchange=CboeExchangeCode.C1.value,
            reference_category="all_series",
        )
        later = reference_as_of(
            [v1, v2],
            decision_time="2026-08-20T12:00:00-05:00",
            exchange=CboeExchangeCode.C1.value,
            reference_category="all_series",
        )
        assert early is not None and later is not None
        self.assertEqual(early.content_hash, v1.content_hash)
        self.assertEqual(later.content_hash, v2.content_hash)

    def test_observation_visible_respects_available_time(self) -> None:
        payload = load_json("daily_stats_embedded.json")
        payload["lastUpdated"] = "2026-08-19T17:30:00-05:00"
        capture = parse_daily_statistics_html(
            daily_html(payload),
            retrieved_time=RETRIEVED_TIME,
            ingested_time=INGESTED_TIME,
        )
        sample = capture.observations[0]
        hidden = statistic_as_of(
            capture.observations,
            decision_time="2026-08-19T17:00:00-05:00",
            canonical_statistic_id=sample.canonical_statistic_id,
            trade_date=sample.trade_date,
        )
        visible = statistic_as_of(
            capture.observations,
            decision_time="2026-08-19T18:00:00-05:00",
            canonical_statistic_id=sample.canonical_statistic_id,
            trade_date=sample.trade_date,
        )
        self.assertIsNone(hidden)
        self.assertIsNotNone(visible)


if __name__ == "__main__":
    unittest.main()
