"""Stored news PIT retrieval; synthetic articles and a disposable schema13 store."""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from market_platform_foundation.local_state.connection import LocalStateConnection
from market_platform_foundation.news.collection import CollectionJob, NewsCollector
from market_platform_foundation.news.normalize import normalize_raw_item


class StoredKnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.connection = LocalStateConnection(Path(self.temp.name) / 'imp-state.sqlite3')
        self.addCleanup(self.connection.close)
        self.now = datetime.fromisoformat('2026-10-13T10:00:00+00:00').timestamp()
        self.raw = {'provider_native_id': 'wire-1', 'headline': 'AAPL reports earnings',
                    'summary': 'Revenue was 10', 'tickers': ['AAPL'],
                    'url': 'https://example.test/wire-1', 'published_time': '2026-10-13T09:00:00Z'}
        self.provenance = {'source_type': 'NEWS', 'license': {'redistribution': 'UNKNOWN'},
                           'source_reference': 'wire/archive/1'}
        self.job = CollectionJob('finviz', '', 'US_EQUITIES', 120)
        self.collector = NewsCollector(self.connection, [self.job], self.fetch, clock=lambda: self.now)

    def fetch(self, job):
        article = normalize_raw_item(self.raw, provider_id=job.provider, source_id='wire',
                                     retrieved_time=datetime.fromtimestamp(self.now, timezone.utc).isoformat())
        return [(article, dict(self.provenance))], {'state': 'CURRENT'}

    def advance(self, seconds=180):
        self.now += seconds
        self.collector.step()

    def retrieve(self, **kwargs):
        from market_platform_foundation.news.knowledge import StoredNewsRepository
        return StoredNewsRepository(self.connection).retrieve(**kwargs)

    def test_correction_is_appended_and_unchanged_repoll_is_deduplicated(self):
        self.collector.step()
        original = self.connection.fetchall('SELECT * FROM news_collection_records')[0]
        self.advance()
        self.assertEqual(len(self.connection.fetchall('SELECT * FROM news_collection_records')), 1)
        self.raw['summary'] = 'Correction: revenue was 8'
        self.advance()
        rows = self.connection.fetchall('SELECT * FROM news_collection_records')
        self.assertEqual(len(rows), 2, 'same-ID corrections must survive collection')
        self.assertEqual(rows[0]['payload_json'], original['payload_json'])
        self.raw['summary'] = 'Revenue was 10'
        self.advance()
        self.assertEqual(len(self.connection.fetchall('SELECT * FROM news_collection_records')), 3,
                         'a reversion is a newly observed revision')

    def test_cutoff_selects_only_revision_known_then_with_saved_license(self):
        self.collector.step()
        first = self.retrieve(as_of='2026-10-13T10:00:00Z')[0]
        self.raw['summary'] = 'Correction: revenue was 8'
        self.provenance['license'] = {'redistribution': 'PROHIBITED'}
        self.advance()
        before = self.retrieve(as_of='2026-10-13T10:02:59Z', symbol='aapl', source_id='wire')
        self.assertEqual(before, [first], 'later correction metadata must not leak before observation')
        after = self.retrieve(as_of='2026-10-13T10:03:00Z')[0]
        self.assertEqual(after['article']['summary'], 'Correction: revenue was 8')
        self.assertEqual(after['provenance']['license']['redistribution'], 'PROHIBITED')
        self.assertEqual(after['supersedes_record_id'], first['record_id'])
        self.assertEqual(after['first_observed_time'], '2026-10-13T10:00:00Z')
        self.assertEqual(len(self.retrieve(as_of='2026-10-13T10:03:00Z', include_revisions=True)), 2)

    def test_backdated_publication_and_retrieval_do_not_bypass_ingestion(self):
        article, provenance = self.fetch(self.job)[0][0]
        payload = {'article': {**article.to_dict(), 'retrieved_time': '2026-10-13T08:00:00Z'},
                   'provenance': provenance}
        self.connection.execute('INSERT INTO news_collection_records VALUES (?,?,?,?,?,?,?)',
            ('legacy', 'finviz', 'wire', self.raw['published_time'], '2026-10-13T08:00:00Z',
             self.now, json.dumps(payload)))
        self.assertEqual(self.retrieve(as_of='2026-10-13T09:59:59Z'), [])
        stored = self.retrieve(as_of='2026-10-13T10:00:00Z')[0]
        self.assertEqual(stored['record_id'], 'legacy')
        self.assertEqual(stored['provenance'], provenance)
        self.assertEqual(stored['first_observed_time'], '2026-10-13T08:00:00Z')
        self.assertEqual(stored['available_at_ns'], 1791885600000000000)

    def test_filters_unknown_publication_and_invalid_cutoffs_fail_closed(self):
        self.collector.step()
        cutoff = '2026-10-13T11:00:00Z'
        self.assertEqual(self.retrieve(as_of=cutoff, provider_id='rss'), [])
        self.assertEqual(self.retrieve(as_of=cutoff, symbol='MSFT'), [])
        self.assertEqual(self.retrieve(as_of=cutoff, published_after='2026-10-13T09:00:01Z'), [])
        self.assertEqual(len(self.retrieve(as_of=cutoff, published_before='2026-10-13T09:00:00Z')), 1)
        for invalid in ('', 'bad', '2026-10-13', '2026-10-13T10:00:00'):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                self.retrieve(as_of=invalid)
        with self.assertRaises(ValueError):
            self.retrieve(as_of=cutoff, limit=1001)

    def test_saved_availability_and_unknown_observation_are_not_invented(self):
        self.provenance['available_time'] = '2026-10-13T10:10:00Z'
        self.collector.step()
        self.assertEqual(self.retrieve(as_of='2026-10-13T10:09:59Z'), [])
        self.assertEqual(len(self.retrieve(as_of='2026-10-13T10:10:00Z')), 1)
        self.connection.execute("UPDATE news_collection_records SET retrieved_time=''")
        self.assertEqual(self.retrieve(as_of='2026-10-13T11:00:00Z'), [])

    def test_latest_results_are_ordered_by_revision_availability(self):
        self.collector.step()
        self.raw['provider_native_id'] = 'wire-2'
        self.raw['url'] = 'https://example.test/wire-2'
        self.advance()
        self.raw['provider_native_id'] = 'wire-1'
        self.raw['url'] = 'https://example.test/wire-1'
        self.raw['summary'] = 'Correction: revenue was 8'
        self.advance()
        result = self.retrieve(as_of='2026-10-13T11:00:00Z', limit=1)
        self.assertEqual(result[0]['article']['provider_native_id'], 'wire-1')

    def test_revised_symbol_does_not_resurrect_old_linkage(self):
        self.collector.step()
        self.raw['tickers'] = ['MSFT']
        self.advance()
        self.assertEqual(self.retrieve(as_of='2026-10-13T11:00:00Z', symbol='AAPL'), [])
        self.assertEqual(len(self.retrieve(as_of='2026-10-13T10:02:59Z', symbol='AAPL')), 1)

    def test_unknown_publication_can_be_retrieved_but_not_in_publication_range(self):
        self.raw['published_time'] = ''
        self.collector.step()
        self.assertEqual(self.retrieve(as_of='2026-10-13T11:00:00Z')[0]['article']['published_time'], '')
        self.assertEqual(self.retrieve(as_of='2026-10-13T11:00:00Z',
                                       published_before='2026-10-13T11:00:00Z'), [])

    def test_context_planning_metadata_matches_immutable_revision(self):
        self.collector.step()
        first = self.retrieve(as_of='2026-10-13T10:00:00Z')[0]
        self.assertEqual(first['revision_id'], first['record_id'])
        self.assertEqual(first['available_at_ns'], 1791885600000000000)
        self.assertGreater(first['estimated_tokens'], 0)
        self.assertEqual(first['execution_authority'], 'NONE')
        self.connection.close()
        self.connection = LocalStateConnection(Path(self.temp.name) / 'imp-state.sqlite3', require_existing=True)
        self.addCleanup(self.connection.close)
        self.assertEqual(self.retrieve(as_of='2026-10-13T10:00:00Z'), [first])

    def test_scan_bound_refuses_partial_latest_evidence_before_materialization(self):
        self.collector.step()
        self.raw['summary'] = 'Correction: revenue was 8'
        self.advance()
        with patch.object(self.connection, 'fetchall', side_effect=AssertionError('history was materialized')):
            with self.assertRaisesRegex(ValueError, '^NEWS_KNOWLEDGE_SCAN_BOUND$'):
                self.retrieve(as_of='2026-10-13T11:00:00Z', max_scan_records=1)
        self.assertEqual(len(self.retrieve(as_of='2026-10-13T11:00:00Z', max_scan_records=2)), 1)
        for invalid in (0, -1, True, '2'):
            with self.subTest(invalid=invalid), self.assertRaisesRegex(ValueError, 'SCAN_LIMIT_INVALID'):
                self.retrieve(as_of='2026-10-13T11:00:00Z', max_scan_records=invalid)

    def test_late_availability_of_old_revision_does_not_override_newer_correction(self):
        self.provenance['available_time'] = '2026-10-13T10:10:00Z'
        self.collector.step()
        self.provenance['available_time'] = '2026-10-13T10:03:00Z'
        self.raw['summary'] = 'Correction: revenue was 8'
        self.advance()
        result = self.retrieve(as_of='2026-10-13T10:11:00Z')
        self.assertEqual(result[0]['article']['summary'], 'Correction: revenue was 8')


if __name__ == '__main__':
    unittest.main()
