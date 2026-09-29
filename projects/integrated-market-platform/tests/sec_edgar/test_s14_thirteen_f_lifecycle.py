"""S14 managed 13F index lifecycle: discovery, manifest, integrity, atomic publish, rollback, PIT.

Every data set here is synthetic, written in the SEC Form 13F data-set layout
(SUBMISSION / COVERPAGE / INFOTABLE TSVs); the listing page is a synthetic page with
the SEC's link pattern. No test touches the network.
"""

from __future__ import annotations

import io
import json
import os
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
import unittest.mock
import zipfile
from datetime import UTC, date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.sec_edgar import thirteen_f_lifecycle as lc  # noqa: E402
from market_platform_foundation.sec_edgar.thirteen_f_index import (  # noqa: E402
    SourceIntegrityError,
    ThirteenFIndex,
    build_index,
    verify_archive,
)

CUSIP = "67066G104"
HR = "13F HOLDINGS REPORT"
BASE = "https://www.sec.gov/files/structureddata/data/form-13f-data-sets/"
W1, W2, W3 = "01mar2026-31may2026_form13f.zip", "01jun2026-31aug2026_form13f.zip", "01sep2026-30nov2026_form13f.zip"


def tsv(header: str, rows: list[tuple]) -> str:
    return header + "\n" + "".join("\t".join(str(value) for value in row) + "\n" for row in rows)


def data_set(submissions: list[tuple], covers: list[tuple], lines: list[tuple], *, drop: str | None = None) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        tables = {
            "SUBMISSION.tsv": tsv("ACCESSION_NUMBER\tFILING_DATE\tSUBMISSIONTYPE\tCIK\tPERIODOFREPORT", submissions),
            "COVERPAGE.tsv": tsv("ACCESSION_NUMBER\tAMENDMENTTYPE\tFILINGMANAGER_NAME\tREPORTTYPE", covers),
            "INFOTABLE.tsv": tsv("ACCESSION_NUMBER\tCUSIP\tVALUE\tSSHPRNAMT\tSSHPRNAMTTYPE\tPUTCALL", lines),
        }
        for name, text in tables.items():
            if name != drop:
                archive.writestr(name, text)
    return buffer.getvalue()


# Q1 2026 reports, filed in May.
Q1 = data_set(
    [("A-1", "14-MAY-2026", "13F-HR", "1", "31-MAR-2026"), ("B-1", "15-MAY-2026", "13F-HR", "2", "31-MAR-2026"),
     ("C-1", "10-MAY-2026", "13F-HR", "3", "31-MAR-2026")],
    [("A-1", "", "Alpha Capital", HR), ("B-1", "", "Beta Advisors", HR), ("C-1", "", "Gamma LP", HR)],
    [("A-1", CUSIP, 1000, 100, "SH", ""), ("B-1", CUSIP, 2000, 200, "SH", ""), ("C-1", CUSIP, 500, 50, "SH", "")])
# Q2 2026 reports, filed in August; Gamma files Q2 without the CUSIP (a genuine exit).
Q2 = data_set(
    [("A-2", "07-AUG-2026", "13F-HR", "1", "30-JUN-2026"), ("B-2", "13-AUG-2026", "13F-HR", "2", "30-JUN-2026"),
     ("C-2", "12-AUG-2026", "13F-HR", "3", "30-JUN-2026"), ("D-2", "11-AUG-2026", "13F-HR", "4", "30-JUN-2026")],
    [("A-2", "", "Alpha Capital", HR), ("B-2", "", "Beta Advisors", HR), ("C-2", "", "Gamma LP", HR),
     ("D-2", "", "Delta Mgmt", HR)],
    [("A-2", CUSIP, 1500, 150, "SH", ""), ("B-2", CUSIP, 9999, 999, "SH", ""), ("C-2", "000000000", 1, 1, "SH", ""),
     ("D-2", CUSIP, 300, 30, "SH", "")])
# September–November: Beta restates Q2 (09/20); Q3 reports: Alpha 11/03, Delta 11/10 (no CUSIP); Beta has not filed Q3.
Q3 = data_set(
    [("B-3", "20-SEP-2026", "13F-HR/A", "2", "30-JUN-2026"), ("A-4", "03-NOV-2026", "13F-HR", "1", "30-SEP-2026"),
     ("D-4", "10-NOV-2026", "13F-HR", "4", "30-SEP-2026")],
    [("B-3", "RESTATEMENT", "Beta Advisors", HR), ("A-4", "", "Alpha Capital", HR), ("D-4", "", "Delta Mgmt", HR)],
    [("B-3", CUSIP, 4000, 400, "SH", ""), ("A-4", CUSIP, 1200, 120, "SH", ""), ("D-4", "000000000", 1, 1, "SH", "")])
PAYLOADS = {BASE + W1: Q1, BASE + W2: Q2, BASE + W3: Q3}


def listing(*names: str) -> str:
    links = "".join(f'<li><a href="/files/structureddata/data/form-13f-data-sets/{name}">{name}</a></li>' for name in names)
    return (f"<html><body><h1>Form 13F Data Sets</h1><ul>{links}"
            '<li><a href="https://example.com/files/2026q1_form13f.zip">mirror</a></li>'
            '<li><a href="/files/structureddata/data/form-13f-data-sets/readme.pdf">readme</a></li></ul></body></html>')


class Clock:
    def __init__(self, moment: datetime) -> None:
        self.value = moment.timestamp()

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


class Harness:
    def __init__(self, root: Path, names: tuple[str, ...], *, payloads: dict[str, bytes] | None = None) -> None:
        self.names = list(names)
        self.payloads = dict(payloads or PAYLOADS)
        self.downloads: list[str] = []
        self.clock = Clock(datetime(2026, 9, 29, 12, tzinfo=UTC))
        self.store = lc.ThirteenFStore(root, clock=self.clock)
        self.listing_error: Exception | None = None

    def fetch_listing(self) -> str:
        if self.listing_error is not None:
            raise self.listing_error
        return listing(*self.names)

    def download(self, url: str, dest: Path) -> None:
        self.downloads.append(url.rsplit("/", 1)[-1])
        dest.write_bytes(self.payloads[url])

    def lifecycle(self, **kwargs) -> lc.ThirteenFLifecycle:
        return lc.ThirteenFLifecycle(self.store, fetch_listing=self.fetch_listing, download=self.download, **kwargs)


class DiscoveryTests(unittest.TestCase):
    def test_listing_admits_official_dataset_links_only(self):
        html = listing(W2, W1) + '<a href="/files/structureddata/data/form-13f-data-sets/2023q4_form13f.zip">old</a>'
        refs = lc.parse_listing(html)
        self.assertEqual([ref.name for ref in refs], ["2023q4_form13f.zip", W1, W2])  # oldest window first
        self.assertEqual((refs[1].coverage_start, refs[1].coverage_end), ("2026-03-01", "2026-05-31"))
        self.assertEqual((refs[0].coverage_start, refs[0].coverage_end), ("2023-10-01", "2023-12-31"))
        self.assertTrue(all(ref.url.startswith("https://www.sec.gov/files/") for ref in refs))

    def test_unrecognised_names_are_never_guessed(self):
        self.assertIsNone(lc.dataset_from_name("31feb2026-31may2026_form13f.zip", "u"))
        self.assertIsNone(lc.dataset_from_name("01jun2026-31may2026_form13f.zip", "u"))  # end before start
        self.assertIsNone(lc.dataset_from_name("form13f_latest.zip", "u"))
        self.assertEqual(lc.parse_listing("<html>no links</html>"), [])


class ArchiveIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def test_missing_table_and_corrupt_archive_fail_closed(self):
        (self.dir / "a.zip").write_bytes(data_set([], [], [], drop="INFOTABLE.tsv"))
        with self.assertRaisesRegex(SourceIntegrityError, "THIRTEEN_F_SOURCE_TABLE_MISSING:INFOTABLE.tsv"):
            verify_archive(self.dir / "a.zip")
        (self.dir / "b.zip").write_bytes(Q1[: len(Q1) // 2])
        with self.assertRaisesRegex(SourceIntegrityError, "THIRTEEN_F_SOURCE_CORRUPT"):
            verify_archive(self.dir / "b.zip")

    def test_missing_required_column(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("SUBMISSION.tsv", "ACCESSION_NUMBER\tFILING_DATE\n")
            archive.writestr("COVERPAGE.tsv", "x\n")
            archive.writestr("INFOTABLE.tsv", "x\n")
        (self.dir / "c.zip").write_bytes(buffer.getvalue())
        with self.assertRaisesRegex(SourceIntegrityError, "COLUMNS_MISSING:SUBMISSION.tsv"):
            verify_archive(self.dir / "c.zip")

    def test_duplicate_accession_is_never_summed_twice(self):
        (self.dir / "q2.zip").write_bytes(Q2)
        (self.dir / "q2copy.zip").write_bytes(Q2)
        stats = build_index([self.dir / "q2.zip", self.dir / "q2copy.zip"], self.dir / "i.sqlite")
        self.assertEqual(stats["duplicate_accessions"], 4)
        index = ThirteenFIndex.load(self.dir / "i.sqlite")
        self.addCleanup(index.close)
        section = index.section([CUSIP], now=datetime(2026, 9, 1, tzinfo=UTC))
        self.assertEqual({item["manager"]: item["shares"] for item in section["holders"]}["Alpha Capital"], 150)

    def test_conflicting_duplicate_accession_fails_closed(self):
        (self.dir / "q2.zip").write_bytes(Q2)
        (self.dir / "conflict.zip").write_bytes(data_set([("A-2", "08-AUG-2026", "13F-HR", "1", "30-JUN-2026")],
                                                         [("A-2", "", "Alpha Capital", HR)], []))
        with self.assertRaisesRegex(SourceIntegrityError, "THIRTEEN_F_DUPLICATE_ACCESSION_CONFLICT"):
            build_index([self.dir / "q2.zip", self.dir / "conflict.zip"], self.dir / "i.sqlite")
        self.assertFalse((self.dir / "i.sqlite").exists())
        self.assertFalse((self.dir / "i.tmp").exists())


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "13f"

    def harness(self, *names: str, **kwargs) -> Harness:
        return Harness(self.root, names or (W1, W2), **kwargs)

    def published(self, harness: Harness, **kwargs) -> dict:
        result = harness.lifecycle(**kwargs).refresh()
        self.assertEqual(result["outcome"], "PUBLISHED", result)
        return result

    def assert_serving(self, harness: Harness, generation: str) -> None:
        self.assertEqual(harness.store.current_generation(), generation)
        index, problem = lc.load_current_index(self.root)
        self.assertIsNone(problem)
        index.close()
        self.assertEqual(list(harness.store.generations.glob("*.building")), [])
        self.assertEqual(list(harness.store.sources.glob("*.part")), [])
        self.assertFalse(harness.store.lock_path.exists())

    # ---------------------------------------------------------- first build, manifest, freshness
    def test_first_refresh_publishes_a_manifested_generation(self):
        h = self.harness()
        result = self.published(h)
        manifest = result["manifest"]
        self.assertEqual(h.downloads, [W1, W2])
        self.assertEqual(manifest["schema_version"], lc.MANIFEST_SCHEMA)
        self.assertEqual([item["name"] for item in manifest["source_datasets"]], [W1, W2])
        self.assertEqual((manifest["coverage_start"], manifest["coverage_end"]), ("2026-03-01", "2026-08-31"))
        self.assertEqual((manifest["filing_date_min"], manifest["filing_date_max"]), ("2026-05-10", "2026-08-13"))
        self.assertEqual((manifest["filing_count"], manifest["position_count"]), (7, 7))
        self.assertIsNone(manifest["parent_generation"])
        self.assertEqual(manifest["tool_version"], lc.TOOL_VERSION)
        for item in manifest["source_datasets"]:
            self.assertEqual(item["sha256"], lc.sha256_file(h.store.source_path(item["name"])))
        index_path = h.store.current_index_path()
        self.assertEqual(manifest["index_sha256"], lc.sha256_file(index_path))
        self.assertEqual(manifest["smoke"]["period"], "2026-06-30")
        self.assert_serving(h, result["generation"])
        state = lc.status(self.root, clock=h.clock)
        self.assertEqual((state["refresh_state"], state["is_current_for_available_datasets"]), ("CURRENT_AS_FILED", True))
        self.assertEqual((state["indexed_through"], state["latest_source_filing_date"]), ("2026-08-31", "2026-08-13"))
        self.assertEqual(state["source_dataset_count"], 2)
        self.assertNotIn("LIVE", json.dumps(state))

    def test_index_carries_generation_provenance(self):
        h = self.harness()
        result = self.published(h)
        index, _ = lc.load_current_index(self.root)
        self.addCleanup(index.close)
        self.assertEqual(index.meta["generation"], result["generation"])
        self.assertEqual(index.indexed_through, date(2026, 8, 31))

    def test_status_without_root_or_index(self):
        self.assertEqual(lc.status(None)["refresh_state"], "NOT_CONFIGURED")
        state = lc.status(self.root)
        self.assertEqual((state["refresh_state"], state["refresh_reason"]), ("NOT_CONFIGURED", "THIRTEEN_F_INDEX_NOT_BUILT"))

    # ---------------------------------------------------------- incremental availability
    def test_no_new_dataset_is_a_no_op(self):
        h = self.harness()
        first = self.published(h)
        h.downloads.clear()
        again = h.lifecycle().refresh()
        self.assertEqual((again["outcome"], again["generation"]), ("NO_CHANGE", first["generation"]))
        self.assertEqual(h.downloads, [])

    def test_one_new_dataset_is_reported_then_published(self):
        h = self.harness()
        first = self.published(h)
        h.names.append(W3)
        check = h.lifecycle().check()
        self.assertEqual((check["missing"], check["is_current_for_available_datasets"]), ([W3], False))
        state = lc.status(self.root, clock=h.clock)
        self.assertEqual((state["refresh_state"], state["missing_datasets"]), ("REFRESH_AVAILABLE", [W3]))
        h.clock.advance(3600)
        h.downloads.clear()
        second = self.published(h)
        self.assertEqual(h.downloads, [W3])  # W2 is reused from the verified source store
        self.assertEqual([item["name"] for item in second["manifest"]["source_datasets"]], [W2, W3])
        self.assertEqual(second["manifest"]["parent_generation"], first["generation"])
        self.assert_serving(h, second["generation"])
        self.assertEqual(lc.status(self.root, clock=h.clock)["refresh_state"], "CURRENT_AS_FILED")

    def test_two_missing_datasets_are_both_fetched(self):
        h = self.harness(W1)
        self.published(h, datasets=3)
        h.names += [W2, W3]
        h.downloads.clear()
        h.clock.advance(60)
        result = self.published(h, datasets=3)
        self.assertEqual(sorted(h.downloads), sorted([W2, W3]))
        self.assertEqual(len(result["manifest"]["source_datasets"]), 3)

    def test_dry_run_changes_nothing(self):
        h = self.harness()
        result = h.lifecycle().refresh(dry_run=True)
        self.assertEqual((result["outcome"], result["missing"]), ("WOULD_REFRESH", [W1, W2]))
        self.assertEqual(h.downloads, [])
        self.assertIsNone(h.store.current_generation())

    # ---------------------------------------------------------- failures keep the active index
    def assert_failed_and_unchanged(self, h: Harness, result: dict, generation: str | None, error: str) -> None:
        self.assertEqual((result["outcome"], result["error"]), ("FAILED", error), result)
        self.assertEqual(result["generation"], generation)
        if generation is None:
            self.assertIsNone(h.store.current_generation())
        else:
            self.assert_serving(h, generation)
        summary = json.loads((self.root / "last_refresh.json").read_text())
        self.assertEqual((summary["outcome"], summary["error"]), ("FAILED", error))
        self.assertEqual(lc.status(self.root, clock=h.clock).get("last_refresh_error", {}).get("error"), error)

    def test_corrupt_zip_fails_closed(self):
        h = self.harness()
        first = self.published(h)
        h.names.append(W3)
        h.payloads[BASE + W3] = Q3[:200]
        self.assert_failed_and_unchanged(h, h.lifecycle().refresh(), first["generation"], "THIRTEEN_F_SOURCE_CORRUPT")
        self.assertFalse(h.store.source_path(W3).exists())

    def test_missing_table_fails_closed(self):
        h = self.harness()
        first = self.published(h)
        h.names.append(W3)
        h.payloads[BASE + W3] = data_set([], [], [], drop="COVERPAGE.tsv")
        self.assert_failed_and_unchanged(h, h.lifecycle().refresh(), first["generation"], "THIRTEEN_F_SOURCE_TABLE_MISSING")

    def test_duplicate_accession_conflict_fails_closed(self):
        h = self.harness()
        first = self.published(h)
        h.names.append(W3)
        h.payloads[BASE + W3] = data_set([("B-2", "14-SEP-2026", "13F-HR", "2", "30-JUN-2026")],
                                         [("B-2", "", "Beta Advisors", HR)], [])
        self.assert_failed_and_unchanged(h, h.lifecycle().refresh(), first["generation"],
                                         "THIRTEEN_F_DUPLICATE_ACCESSION_CONFLICT")

    def test_build_failure(self):
        h = self.harness()
        first = self.published(h)

        def broken(*_args, **_kwargs):
            raise sqlite3.OperationalError("disk I/O error")

        result = h.lifecycle(builder=broken).refresh(force=True)
        self.assert_failed_and_unchanged(h, result, first["generation"], "UNEXPECTED_OPERATIONALERROR")
        self.assertEqual(result["stage"], "build")

    def test_smoke_failure(self):
        h = self.harness()
        first = self.published(h)

        def failing_smoke(_path, _manifest):
            raise lc.RefreshError("INDEX_SMOKE_QUERY_FAILED", "validate")

        result = h.lifecycle(smoke=failing_smoke).refresh(force=True)
        self.assert_failed_and_unchanged(h, result, first["generation"], "INDEX_SMOKE_QUERY_FAILED")

    def test_real_smoke_closes_every_connection_before_publish(self):
        # Windows cannot rename a directory holding an open SQLite file, so the smoke
        # validator must not leave its connection to garbage collection (found live, S14).
        opened: list[sqlite3.Connection] = []
        real_connect = sqlite3.connect

        def tracking_connect(*args, **kwargs):
            connection = real_connect(*args, **kwargs)
            opened.append(connection)
            return connection

        h = self.harness()
        with unittest.mock.patch.object(lc.sqlite3, "connect", tracking_connect):
            self.published(h)
        self.assertTrue(opened)
        for connection in opened:
            with self.assertRaises(sqlite3.ProgrammingError):
                connection.execute("SELECT 1")

    def test_real_smoke_rejects_an_index_without_positions(self):
        h = self.harness()
        h.payloads[BASE + W1] = data_set([("X-1", "14-MAY-2026", "13F-HR", "9", "31-MAR-2026")],
                                         [("X-1", "", "Empty", HR)], [])
        h.names = [W1]
        result = h.lifecycle(datasets=1).refresh()
        self.assert_failed_and_unchanged(h, result, None, "INDEX_EMPTY")

    def test_source_hash_mismatch_quarantines_and_recovers(self):
        h = self.harness()
        first = self.published(h)
        path = h.store.source_path(W2)
        path.write_bytes(path.read_bytes() + b"tampered")
        result = h.lifecycle().refresh(force=True)
        self.assert_failed_and_unchanged(h, result, first["generation"], "THIRTEEN_F_SOURCE_HASH_MISMATCH")
        self.assertTrue(path.with_name(path.name + ".quarantine").exists())
        h.downloads.clear()
        h.clock.advance(60)
        again = h.lifecycle().refresh(force=True)
        self.assertEqual(again["outcome"], "PUBLISHED")
        self.assertEqual(h.downloads, [W2])  # the quarantined data set is fetched again and re-verified

    def test_discovery_failure_is_a_source_state_not_an_index_failure(self):
        h = self.harness()
        first = self.published(h)
        h.listing_error = OSError("SEC_UNREACHABLE")
        check = h.lifecycle().check()
        self.assertEqual((check["ok"], check["error"]), (False, "SEC_UNREACHABLE"))
        state = lc.status(self.root, clock=h.clock)
        self.assertEqual((state["refresh_state"], state["generation"]), ("SOURCE_ERROR", first["generation"]))
        result = h.lifecycle().refresh()
        self.assert_failed_and_unchanged(h, result, first["generation"], "SEC_UNREACHABLE")

    # ---------------------------------------------------------- atomic publish, crash safety, rollback
    def test_crash_at_every_stage_leaves_the_active_index(self):
        h = self.harness()
        first = self.published(h)
        h.names.append(W3)
        for stage in ("download", "build", "validate", "before_swap", "after_candidate"):
            with self.subTest(stage=stage):
                def hook(current: str, stage: str = stage) -> None:
                    if current == stage:
                        raise RuntimeError(f"crash at {stage}")

                h.clock.advance(60)
                result = h.lifecycle(hook=hook).refresh()
                self.assertEqual(result["outcome"], "FAILED")
                self.assert_serving(h, first["generation"])
        h.clock.advance(60)
        recovered = self.published(h)
        self.assert_serving(h, recovered["generation"])

    def test_dead_process_leftovers_are_reclaimed(self):
        h = self.harness()
        first = self.published(h)
        # A refresh process died mid-download and mid-build, holding the lock.
        (h.store.sources / f"{W3}.part").write_bytes(b"partial")
        (h.store.generations / "gen-dead.building").mkdir()
        (h.store.generations / "gen-dead.building" / "index.sqlite").write_bytes(b"half")
        h.store.lock_path.write_text(json.dumps({"pid": 999999, "started_at_epoch": time.time() - lc.LOCK_STALE_S - 1}))
        self.assertEqual(lc.status(self.root, clock=h.clock)["refresh_state"], "CURRENT_AS_FILED")  # stale lock ≠ refreshing
        self.assert_serving_ignoring_lock(h, first["generation"])
        h.names.append(W3)
        result = self.published(h)
        self.assertIn(f"sources/{W3}.part", result["cleaned"])
        self.assertIn("generations/gen-dead.building", result["cleaned"])
        self.assert_serving(h, result["generation"])

    def assert_serving_ignoring_lock(self, h: Harness, generation: str) -> None:
        index, problem = lc.load_current_index(self.root)
        self.assertIsNone(problem)
        index.close()
        self.assertEqual(h.store.current_generation(), generation)

    def test_pointer_switch_is_all_or_nothing(self):
        h = self.harness()
        first = self.published(h)
        before = (self.root / "CURRENT").read_bytes()
        reader = ThirteenFIndex.load(h.store.current_index_path())  # a request thread holding the old generation
        h.names.append(W3)
        h.clock.advance(60)
        second = self.published(h)
        pointer = json.loads((self.root / "CURRENT").read_text())
        self.assertNotEqual((self.root / "CURRENT").read_bytes(), before)
        self.assertEqual((pointer["generation"], pointer["previous"]), (second["generation"], first["generation"]))
        self.assertEqual(pointer["manifest_sha256"], lc.sha256_file(h.store.generation_dir(second["generation"]) / "manifest.json"))
        # The old reader keeps answering from its immutable generation until it re-opens.
        self.assertEqual(reader.section([CUSIP], now=datetime(2026, 9, 29, tzinfo=UTC))["period"], "2026-06-30")
        reader.close()
        self.assertFalse((self.root / "CURRENT.tmp").exists())

    def test_rollback_to_parent(self):
        h = self.harness()
        first = self.published(h)
        h.names.append(W3)
        h.clock.advance(60)
        second = self.published(h)
        rolled = h.lifecycle().rollback()
        self.assertEqual((rolled["outcome"], rolled["generation"]), ("ROLLED_BACK", first["generation"]))
        self.assert_serving(h, first["generation"])
        # A parent whose index no longer matches its manifest is refused.
        store = h.store
        lc._write_json_atomic(store.pointer, {"generation": second["generation"]})
        index = store.generation_dir(first["generation"]) / "index.sqlite"
        index.write_bytes(index.read_bytes()[:-10] + b"0123456789")
        refused = h.lifecycle().rollback()
        self.assertEqual((refused["outcome"], refused["error"]), ("FAILED", "PARENT_INDEX_HASH_MISMATCH"))
        self.assertEqual(store.current_generation(), second["generation"])

    def test_rollback_without_parent(self):
        h = self.harness()
        self.published(h)
        self.assertEqual(h.lifecycle().rollback()["error"], "NO_PARENT_GENERATION")

    def test_stale_or_damaged_manifest_is_index_invalid_and_rebuilt(self):
        h = self.harness()
        first = self.published(h)
        manifest_path = h.store.generation_dir(first["generation"]) / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["index_bytes"] += 1
        manifest_path.write_text(json.dumps(manifest))
        state = lc.status(self.root, clock=h.clock)
        self.assertEqual((state["refresh_state"], state["refresh_reason"]), ("INDEX_INVALID", "INDEX_SIZE_MISMATCH"))
        self.assertEqual(lc.load_current_index(self.root), (None, "INDEX_SIZE_MISMATCH"))
        h.clock.advance(60)
        rebuilt = h.lifecycle().refresh()  # no new data set, but the active generation is invalid
        self.assertEqual(rebuilt["outcome"], "PUBLISHED")
        manifest_path.unlink()
        self.assertEqual(h.store.verify_generation(first["generation"]), "MANIFEST_MISSING")

    def test_old_generations_are_pruned_but_parent_kept(self):
        h = self.harness()
        generations = []
        for _ in range(5):
            h.clock.advance(60)
            generations.append(h.lifecycle().refresh(force=True)["generation"])
        remaining = list(lc.iter_generations(self.root))
        self.assertEqual(len(remaining), lc.KEEP_GENERATIONS)
        self.assertIn(generations[-1], remaining)
        self.assertIn(generations[-2], remaining)

    # ---------------------------------------------------------- concurrency
    def test_a_lock_being_written_is_live_not_stale(self):
        # Regression: a second refresh read the owner's lock between O_EXCL create and payload write
        # (empty file), judged it stale against the injected clock, and deleted it.
        h = self.harness()
        h.store.root.mkdir(parents=True, exist_ok=True)
        h.store.lock_path.write_bytes(b"")
        self.assertTrue(h.store.lock_active())
        result = h.lifecycle().refresh()
        self.assertEqual((result["outcome"], result["error"]), ("FAILED", "REFRESH_ALREADY_RUNNING"))
        self.assertTrue(h.store.lock_path.exists())
        h.store.lock_path.write_bytes(b'{"started_at_epoch": "garbage"')     # partial JSON: dated by mtime
        self.assertTrue(h.store.lock_active())
        os.utime(h.store.lock_path, (time.time() - lc.LOCK_STALE_S - 5,) * 2)  # but a truly old one is stale
        self.assertFalse(h.store.lock_active())
        self.assertEqual(h.lifecycle().refresh()["outcome"], "PUBLISHED")

    def test_lock_contention(self):
        h = self.harness()
        h.store.acquire()
        self.assertEqual(lc.status(self.root, clock=h.clock)["refresh_state"], "REFRESHING")
        result = h.lifecycle().refresh()
        self.assertEqual((result["outcome"], result["error"]), ("FAILED", "REFRESH_ALREADY_RUNNING"))
        self.assertTrue(h.store.lock_path.exists())  # the other refresh's lock is left alone
        with self.assertRaises(lc.RefreshError):
            h.lifecycle().rollback()
        h.store.release()

    def test_concurrent_refreshes_publish_once(self):
        h = self.harness()
        gate = threading.Event()

        def slow_builder(paths, out, *, meta):
            gate.wait(5)
            return build_index(paths, out, meta=meta)

        results: list[dict] = []
        workers = [threading.Thread(target=lambda: results.append(h.lifecycle(builder=slow_builder).refresh())) for _ in range(2)]
        for worker in workers:
            worker.start()
        deadline = time.monotonic() + 5
        while len(results) < 1 and time.monotonic() < deadline:
            time.sleep(0.01)
        gate.set()
        for worker in workers:
            worker.join(10)
        outcomes = sorted(item["outcome"] + ":" + str(item.get("error")) for item in results)
        self.assertEqual(outcomes, ["FAILED:REFRESH_ALREADY_RUNNING", "PUBLISHED:None"])
        self.assertEqual(len(list(lc.iter_generations(self.root))), 1)

    # ---------------------------------------------------------- point in time across refreshes
    def test_refresh_never_reveals_later_filings_to_a_historical_query(self):
        h = self.harness()
        self.published(h)
        h.names.append(W3)
        h.clock.advance(60)
        self.published(h, datasets=3)
        index, _ = lc.load_current_index(self.root)
        self.addCleanup(index.close)

        def holders(moment: datetime) -> dict:
            return {item["manager"]: item for item in index.section([CUSIP], now=moment)["holders"]}

        # Aug 15: Beta's original Q2 report (999) — the Sep 20 restatement is not yet public.
        self.assertEqual(holders(datetime(2026, 8, 15, tzinfo=UTC))["Beta Advisors"]["shares"], 999)
        # Sep 22: the restatement (400) is public and replaces the original.
        self.assertEqual(holders(datetime(2026, 9, 22, tzinfo=UTC))["Beta Advisors"]["shares"], 400)
        # Jul 20: Q2 is not public at all; the newest public quarter is Q1.
        early = index.section([CUSIP], now=datetime(2026, 7, 20, tzinfo=UTC))
        self.assertEqual(early["period"], "2026-03-31")

    def test_exit_needs_the_managers_own_filing_even_after_refresh(self):
        h = self.harness(W1, W2, W3)
        self.published(h, datasets=3)
        index, _ = lc.load_current_index(self.root)
        self.addCleanup(index.close)
        # Nov 5: Q3 window open; Alpha filed Q3 on 11/03, Delta not until 11/10, Beta not at all.
        nov5 = index.section([CUSIP], now=datetime(2026, 11, 5, tzinfo=UTC))
        self.assertEqual((nov5["period"], nov5["state"], nov5["reason"]), ("2026-09-30", "PARTIAL", "FILING_WINDOW_OPEN"))
        self.assertEqual(nov5["change_counts"]["EXITED"], 0)
        self.assertEqual([item["manager"] for item in nov5["holders"]], ["Alpha Capital"])
        # Nov 11: Delta's Q3 report is public and omits the CUSIP -> EXITED; Beta (not filed) is not an exit.
        nov11 = index.section([CUSIP], now=datetime(2026, 11, 11, tzinfo=UTC))
        self.assertEqual(nov11["change_counts"]["EXITED"], 1)
        self.assertNotIn("Beta Advisors", [item["manager"] for item in nov11["holders"]])

    def test_index_ending_before_the_deadline_is_partial(self):
        tmp = Path(self.tmp.name)
        (tmp / "q2.zip").write_bytes(Q2)
        build_index([tmp / "q2.zip"], tmp / "short.sqlite", meta={"coverage_end": "2026-08-10"})
        index = ThirteenFIndex.load(tmp / "short.sqlite")
        self.addCleanup(index.close)
        section = index.section([CUSIP], now=datetime(2026, 9, 28, tzinfo=UTC))
        self.assertEqual((section["state"], section["reason"]), ("PARTIAL", "INDEX_ENDS_BEFORE_FILING_DEADLINE"))
        self.assertEqual(section["indexed_through"], "2026-08-10")


class CliTests(unittest.TestCase):
    def test_cli_refuses_a_root_inside_the_repository(self):
        sys.path.insert(0, str(ROOT / "tools" / "sec_edgar"))
        import thirteen_f_refresh  # noqa: PLC0415

        with self.assertRaises(SystemExit):
            thirteen_f_refresh.main(["--root", str(ROOT / "tmp-13f"), "--status"])
        self.assertFalse((ROOT / "tmp-13f").exists())

    def test_cli_offline_listing_and_import(self):
        sys.path.insert(0, str(ROOT / "tools" / "sec_edgar"))
        import thirteen_f_refresh  # noqa: PLC0415

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / W1).write_bytes(Q1)
            (base / W2).write_bytes(Q2)
            (base / "listing.html").write_text(listing(W1, W2))
            with io.StringIO() as out, _redirect(out):
                code = thirteen_f_refresh.main(["--root", str(base / "root"), "--refresh", "--listing-file",
                                                str(base / "listing.html"), "--import-zip", str(base / W1),
                                                "--import-zip", str(base / W2)])
                text = out.getvalue()
            self.assertEqual(code, 0, text)
            self.assertIn('"outcome": "PUBLISHED"', text)
            state = lc.status(base / "root")
            self.assertEqual(state["source_datasets"], [W1, W2])


class _redirect:
    def __init__(self, stream: io.StringIO) -> None:
        self.stream = stream

    def __enter__(self):
        self.saved = sys.stdout
        sys.stdout = self.stream

    def __exit__(self, *exc):
        sys.stdout = self.saved


if __name__ == "__main__":
    unittest.main()
