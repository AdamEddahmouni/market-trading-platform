"""Complete enumeration of the active Screener query: every row once, from one result set, or nothing."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.ui_api.screener_ai_universe import UniverseEnumerationError, enumerate_universe  # noqa: E402
from market_platform_foundation.ui_api.screener_query import MAX_PAGE_LIMIT  # noqa: E402
from tests.support.coverage_universe import SCOPE, PagingReader, instrument_id, universe  # noqa: E402

QUERY = {**SCOPE, "view": "Overview", "screen": ""}


class EnumerationTests(unittest.TestCase):
    def test_every_size_is_read_completely_in_bounded_pages(self):
        for size in (0, 1, 49, 50, 51, 100, 500, 501, 4600, 20000):
            reader = PagingReader(universe(size))
            found = enumerate_universe(reader, QUERY)
            self.assertEqual(found.result_count, size)
            self.assertEqual([row["instrument"]["instrument_id"] for row in found.rows], [instrument_id(index) for index in range(size)])
            self.assertEqual(found.pages, max(1, -(-size // MAX_PAGE_LIMIT)))
            self.assertTrue(all(call["limit"] == MAX_PAGE_LIMIT for call in reader.calls))
            self.assertEqual([call["offset"] for call in reader.calls], [index * MAX_PAGE_LIMIT for index in range(found.pages)])

    def test_later_pages_are_pinned_to_the_first_pages_result_set(self):
        reader = PagingReader(universe(1200), result_set="set-9")
        found = enumerate_universe(reader, QUERY)
        self.assertEqual(found.result_set, "set-9")
        self.assertIsNone(reader.calls[0]["result_set"])
        self.assertEqual({call["result_set"] for call in reader.calls[1:]}, {"set-9"})
        self.assertEqual(found.query_id, "query-1")
        self.assertNotIn("rows", found.envelope)

    def test_the_query_is_passed_through_unchanged(self):
        reader = PagingReader(universe(10))
        filters = [{"id": "r1", "field": "rsi_14", "operator": "gt", "value": 50}]
        enumerate_universe(reader, {**QUERY, "search": "abc", "sort": "price", "descending": False, "filters": filters})
        call = reader.calls[0]
        self.assertEqual((call["universe"], call["search"], call["sort"], call["descending"], call["filters"]),
                         ("US_EQUITIES", "abc", "price", False, filters))

    def failure(self, reader) -> str:
        with self.assertRaises(UniverseEnumerationError) as raised:
            enumerate_universe(reader, QUERY)
        return raised.exception.code

    def test_a_result_set_that_moves_mid_scan_ends_the_scan(self):
        class Moving(PagingReader):
            def read(self, **kwargs):
                if kwargs["offset"] >= MAX_PAGE_LIMIT:
                    raise ValueError("RESULT_SET_CHANGED")
                return super().read(**kwargs)

        self.assertEqual(self.failure(Moving(universe(1200))), "RESULT_SET_CHANGED")

        class Relabelled(PagingReader):
            def read(self, **kwargs):
                page = super().read(**kwargs)
                return {**page, "result_set_id": "set-2"} if kwargs["offset"] else page

        self.assertEqual(self.failure(Relabelled(universe(1200))), "RESULT_SET_CHANGED")

    def test_a_repeated_row_a_changed_total_and_a_short_page_are_each_refused(self):
        rows = universe(1200)
        rows[700] = rows[3]
        self.assertEqual(self.failure(PagingReader(rows)), "DUPLICATE_INSTRUMENT")

        class Shrinking(PagingReader):
            def read(self, **kwargs):
                page = super().read(**kwargs)
                return {**page, "result_count": 1100} if kwargs["offset"] else page

        self.assertEqual(self.failure(Shrinking(universe(1200))), "RESULT_COUNT_CHANGED")

        class Short(PagingReader):
            def read(self, **kwargs):
                page = super().read(**kwargs)
                return {**page, "rows": []} if kwargs["offset"] else page

        self.assertEqual(self.failure(Short(universe(1200))), "SHORT_PAGE")

        class Overfull(PagingReader):
            def read(self, **kwargs):
                return {**super().read(**kwargs), "result_count": 5}

        self.assertEqual(self.failure(Overfull(universe(9))), "RESULT_COUNT_MISMATCH")

    def test_a_row_without_identity_and_an_unrelated_reader_error_are_not_swallowed(self):
        rows = universe(5)
        rows[2] = {"instrument": {}, "fields": {}}
        self.assertEqual(self.failure(PagingReader(rows)), "ROW_IDENTITY_MISSING")

        class Broken(PagingReader):
            def read(self, **kwargs):
                raise ValueError("MARKET_SNAPSHOT_UNAVAILABLE")

        with self.assertRaisesRegex(ValueError, "MARKET_SNAPSHOT_UNAVAILABLE"):
            enumerate_universe(Broken(universe(5)), QUERY)


if __name__ == "__main__":
    unittest.main()
