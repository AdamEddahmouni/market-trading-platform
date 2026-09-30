"""Cached public congress-legislators registry: bounded refresh, provenance, local-only load, and the
participants service's background refresh behind the public-records gate. Fetches are fakes (no network)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import UTC, date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.congressional_ptr import legislators_registry as legislators  # noqa: E402
from market_platform_foundation.congressional_ptr.identity import MemberResolver, SourceIdentity, split_full_name  # noqa: E402

NOW = datetime(2026, 9, 29, 12, 0, tzinfo=UTC)


def member(bioguide, first, last, terms):
    return {"id": {"bioguide": bioguide}, "name": {"first": first, "last": last, "official_full": f"{first} {last}"},
            "terms": terms}


CURRENT = [member("S000001", "Jane", "Smith", [{"type": "sen", "state": "OH", "start": "2025-01-03", "end": "2031-01-03"}]),
           member("D000002", "Alex", "Doe", [{"type": "rep", "state": "VA", "district": 5, "start": "2025-01-03", "end": "2027-01-03"}])]
HISTORICAL = [member("R000003", "Pat", "Roe", [{"type": "rep", "state": "TX", "district": 2, "start": "2019-01-03", "end": "2023-01-03"}]),
              member("O000004", "Old", "Timer", [{"type": "sen", "state": "MA", "start": "1901-03-04", "end": "1907-03-03"}]),
              {"id": {}, "name": {"last": "NoId"}, "terms": []}]


def fetcher(*, fail=None, calls=None):
    def fetch(url):
        if calls is not None:
            calls.append(url)
        if fail and fail in url:
            return 503, b"", {}
        if url.endswith("legislators-current.json"):
            return 200, json.dumps(CURRENT).encode(), {"last-modified": "Thu, 24 Sep 2026 10:21:30 GMT", "etag": '"c"'}
        if url.endswith("legislators-historical.json"):
            return 200, json.dumps(HISTORICAL).encode(), {"etag": '"h"'}
        if "api.github.com" in url:
            return 200, json.dumps([{"sha": "577ca04", "commit": {"committer": {"date": "2026-09-24T10:20:54Z"}}}]).encode(), {}
        return 404, b"", {}
    return fetch


class RegistryRefreshTests(unittest.TestCase):
    def test_refresh_records_provenance_and_filters_history(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            manifest = legislators.refresh(cache, fetch=fetcher(), now=lambda: NOW)
            self.assertEqual((manifest["source"], manifest["license"], manifest["parse_state"]),
                             ("unitedstates/congress-legislators", "CC0-1.0", "PARSED"))
            self.assertEqual(manifest["revision"]["commit"], "577ca04")
            files = manifest["files"]
            self.assertEqual(files["legislators-current.json"]["kept_members"], 2)
            # Pre-STOCK-Act members and rows without a Bioguide id are not identity evidence.
            self.assertEqual((files["legislators-historical.json"]["source_members"],
                              files["legislators-historical.json"]["kept_members"]), (2, 1))
            self.assertEqual(len(files["legislators-current.json"]["source_sha256"]), 64)
            cached = legislators.load(cache, now=lambda: NOW)
            self.assertEqual((cached.state, len(cached.registry.members)), ("CURRENT", 3))
            self.assertTrue(cached.registry.source.startswith("unitedstates/congress-legislators@2026-09-29"))
            # Official-id resolution works from the local copy alone.
            identity = SourceIdentity("SENATE", "senate_efd", "Jane Smith", split_full_name("Jane Smith"), date(2026, 9, 1), "OH")
            resolution = MemberResolver(cached.registry).resolve([identity])[identity.key]
            self.assertEqual((resolution.canonical_member_id, resolution.resolution), ("BIOGUIDE:S000001", "OFFICIAL_ID"))

    def test_failed_refresh_keeps_the_previous_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            legislators.refresh(cache, fetch=fetcher(), now=lambda: NOW)
            with self.assertRaises(legislators.RegistryRefreshError) as caught:
                legislators.refresh(cache, fetch=fetcher(fail="historical"), now=lambda: NOW)
            self.assertEqual(str(caught.exception), "REGISTRY_HTTP_503")
            self.assertEqual(legislators.load(cache, now=lambda: NOW).state, "CURRENT")

    def test_invalid_payloads_are_rejected(self):
        for body, code in ((b"{not json", "REGISTRY_INVALID_JSON"), (b"{}", "REGISTRY_NOT_A_LIST"), (b"[]", "REGISTRY_EMPTY")):
            with tempfile.TemporaryDirectory() as directory, self.assertRaises(legislators.RegistryRefreshError) as caught:
                legislators.refresh(Path(directory), fetch=lambda url, body=body: (200, body, {}))
            self.assertEqual(str(caught.exception), code)

    def test_states_missing_stale(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            self.assertEqual(legislators.load(cache).state, "MISSING")
            legislators.refresh(cache, fetch=fetcher(), now=lambda: datetime(2026, 9, 1, tzinfo=UTC))
            stale = legislators.load(cache, now=lambda: NOW)
            self.assertEqual((stale.state, stale.reason), ("STALE", "REFRESH_DUE"))
            self.assertIsNotNone(stale.registry)                   # a stale copy is still used, and says so


class ParticipantsRegistryTests(unittest.TestCase):
    def service(self, cache, env, refresh):
        from market_platform_foundation.ui_api.screener_participants import ScreenerParticipantService
        from market_platform_foundation.ui_api.screener_squeeze_sources import BackgroundCache

        return ScreenerParticipantService(catalog=lambda universe: ([], None), row_for=lambda i, u: None,
                                          cache=BackgroundCache(clock=lambda: NOW.timestamp(), spawn=lambda job: job()),
                                          clock=lambda: NOW.timestamp(), wait_s=0.0, env=env.get,
                                          registry_cache_dir=cache, registry_refresh=refresh)

    def test_missing_copy_refreshes_in_background_only_when_public_records_live(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            calls = []

            def refresh(path):
                calls.append(path)
                return legislators.refresh(path, fetch=fetcher(), now=lambda: NOW)
            offline = self.service(cache, {}, refresh)
            self.assertIsNone(offline._member_resolver().registry)
            self.assertEqual((calls, offline._registry_status["state"]), ([], "MISSING"))
            live = self.service(cache, {"IMP_PUBLIC_RECORDS_LIVE": "1"}, refresh)
            resolver = live._member_resolver()
            self.assertEqual((len(calls), len(resolver.registry.members)), (1, 3))
            self.assertEqual(live._registry_status["state"], "CURRENT")
            self.assertIs(live._member_resolver(), resolver)        # no re-parse while the copy is unchanged

    def test_explicit_registry_path_still_wins(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "explicit.json"
            path.write_text(json.dumps(CURRENT), encoding="utf-8")
            svc = self.service(Path(directory) / "cache", {"IMP_CONGRESS_LEGISLATORS_PATH": str(path),
                                                            "IMP_PUBLIC_RECORDS_LIVE": "1"},
                               lambda p: self.fail("an explicit registry is never refreshed"))
            self.assertEqual(len(svc._member_resolver().registry.members), 2)


if __name__ == "__main__":
    unittest.main()
