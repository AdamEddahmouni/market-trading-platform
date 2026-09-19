"""Artifact path portability and Item 9 expected-cycle gap analysis."""

from __future__ import annotations

import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.platform.artifact_path_resolver import (  # noqa: E402
    COLLECTOR_LOG_STALE_AFTER_SECONDS,
    ITEM9_COLLECTOR_LOG_ENV,
    StoredPathAvailability,
    analyze_item9_collect_log_gaps,
    analyze_item9_receipt_directory,
    classify_stored_path,
    portable_stored_path,
    read_item9_collector_log_text,
    resolve_item9_collector_log_path,
    resolve_stored_file_path,
    resolve_v3_baseline_run_dir,
)

_FOREIGN_MANIFEST = (
    "C:\\Users\\adame\\Desktop\\market-trading-platform\\.worktrees\\opend-fill-economics-v3"
    "\\projects\\integrated-market-platform\\artifacts\\historical-research-harness"
    "\\baseline-pack-v3\\runs\\DEADBEEF\\run_manifest.json"
)

_EPOCH_121031_LOG = """
09/18/2026 12:10:03 receipt item9-prospective-20260918-epoch-fed2d9f7-aapl-120905
09/18/2026 12:10:31 START item9-prospective-20260918-epoch-fed2d9f7-aapl-121031
09/18/2026 13:54:11 END item9-prospective-20260918-epoch-fed2d9f7-aapl-121031 exit=1
09/18/2026 13:56:00 receipt item9-prospective-20260918-epoch-fed2d9f7-aapl-135512
"""


class ArtifactPathResolverTests(unittest.TestCase):
    def test_foreign_windows_path_classified_on_linux(self) -> None:
        if sys.platform == "win32":
            self.skipTest("foreign-platform classification is for non-Windows hosts")
        resolution = classify_stored_path(_FOREIGN_MANIFEST, platform="linux")
        self.assertEqual(resolution.availability, StoredPathAvailability.FOREIGN_PLATFORM)

    def test_resolve_foreign_manifest_does_not_raise(self) -> None:
        missing_run_id = "0" * 64
        try:
            resolved = resolve_v3_baseline_run_dir(
                ROOT,
                run_id=missing_run_id,
                manifest_path=_FOREIGN_MANIFEST,
            )
        except OSError as exc:
            self.fail(f"resolve_v3_baseline_run_dir must not raise OSError: {exc}")
        if sys.platform != "win32":
            self.assertIsNone(resolved)

    def test_portable_stored_path_prefers_repo_relative(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "evidence" / "sample.json"
            target.parent.mkdir(parents=True)
            target.write_text("{}", encoding="utf-8")
            stored = portable_stored_path(target, repository_root=root)
            self.assertEqual(stored, "evidence/sample.json")
            resolution = resolve_stored_file_path(stored, repository_root=root)
            self.assertEqual(resolution.availability, StoredPathAvailability.AVAILABLE)

    def test_epoch_121031_log_gap_not_coerced_to_receipt(self) -> None:
        gaps = analyze_item9_collect_log_gaps(_EPOCH_121031_LOG)
        self.assertEqual(gaps["started_epoch_count"], 1)
        self.assertEqual(gaps["ended_epoch_count"], 1)
        self.assertEqual(gaps["hung_epochs_without_end"], [])
        missing = gaps["missing_receipt_epochs"]
        self.assertEqual(len(missing), 1)
        self.assertEqual(missing[0]["epoch"], "121031")
        self.assertEqual(missing[0]["receipt_status"], "NOT_OBSERVED")
        self.assertEqual(missing[0]["failure_class"], "PROVIDER_UNAVAILABLE_OR_PARTIAL_RECEIPT")

    def test_receipt_directory_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            receipt_dir = Path(tmp)
            (receipt_dir / "item9-prospective-20260918-epoch-fed2d9f7-aapl-120905.json").write_text(
                "{}",
                encoding="utf-8",
            )
            inventory = analyze_item9_receipt_directory(receipt_dir)
            self.assertEqual(inventory["receipt_file_count"], 1)

    def test_hung_start_without_end_classified(self) -> None:
        log = "09/18/2026 12:10:31 START item9-prospective-20260918-epoch-fed2d9f7-aapl-121031\n"
        gaps = analyze_item9_collect_log_gaps(log)
        self.assertEqual(gaps["hung_epochs_without_end"], ["121031"])
        self.assertEqual(gaps["missing_receipt_epochs"][0]["failure_class"], "COLLECTOR_HUNG_OR_PROVIDER_UNAVAILABLE")
        self.assertEqual(gaps["analysis_completeness"], "FULL")
        self.assertFalse(gaps["truncated"])

    def test_complete_cycle_with_receipt_not_missing(self) -> None:
        log = """
START item9-prospective-20260918-epoch-fed2d9f7-aapl-120905
END item9-prospective-20260918-epoch-fed2d9f7-aapl-120905 exit=0
receipt item9-prospective-20260918-epoch-fed2d9f7-aapl-120905
"""
        gaps = analyze_item9_collect_log_gaps(log)
        self.assertEqual(gaps["missing_receipt_epochs"], [])
        self.assertEqual(gaps["hung_epochs_without_end"], [])

    def test_end_without_start_not_coerced_to_receipt(self) -> None:
        log = "END item9-prospective-20260918-epoch-fed2d9f7-aapl-135512 exit=1\n"
        gaps = analyze_item9_collect_log_gaps(log)
        self.assertEqual(gaps["ends_without_start"], ["135512"])
        self.assertEqual(gaps["started_epoch_count"], 0)
        self.assertEqual(gaps["missing_receipt_epochs"], [])

    def test_duplicate_start_and_end_observations(self) -> None:
        log = """
START item9-prospective-20260918-epoch-fed2d9f7-aapl-121031
START item9-prospective-20260918-epoch-aaaaaaa1-aapl-121031
END item9-prospective-20260918-epoch-fed2d9f7-aapl-121031 exit=1
END item9-prospective-20260918-epoch-fed2d9f7-aapl-121031 exit=1
"""
        gaps = analyze_item9_collect_log_gaps(log)
        self.assertEqual(gaps["started_epoch_count"], 1)
        self.assertEqual(gaps["start_observation_count"], 2)
        self.assertEqual(gaps["end_observation_count"], 2)
        self.assertEqual(gaps["duplicate_start_epochs"], ["121031"])
        self.assertEqual(gaps["duplicate_end_epochs"], ["121031"])
        self.assertEqual(gaps["missing_receipt_epochs"][0]["experiment_id"].startswith("item9-prospective-"), True)
        self.assertIn("fed2d9f7", gaps["missing_receipt_epochs"][0]["experiment_id"])

    def test_crlf_null_and_noise_lines_do_not_crash(self) -> None:
        log = (
            "garbage\r\n"
            "START item9-prospective-20260918-epoch-fed2d9f7-aapl-121031\x00\r\n"
            "not a cycle line START almost\r\n"
            "END item9-prospective-20260918-epoch-fed2d9f7-aapl-121031 exit=1\n"
        )
        gaps = analyze_item9_collect_log_gaps(log)
        self.assertEqual(gaps["started_epoch_count"], 1)
        self.assertEqual(gaps["ended_epoch_count"], 1)
        self.assertEqual(len(gaps["missing_receipt_epochs"]), 1)

    def test_inventory_receipt_epochs_close_log_only_gap(self) -> None:
        log = "START item9-prospective-20260918-epoch-fed2d9f7-aapl-120905\nEND item9-prospective-20260918-epoch-fed2d9f7-aapl-120905\n"
        gaps = analyze_item9_collect_log_gaps(log, known_receipt_epochs={"120905"})
        self.assertEqual(gaps["missing_receipt_epochs"], [])
        self.assertEqual(gaps["inventory_receipt_epoch_count"], 1)

    def test_truncated_flag_marks_partial_tail(self) -> None:
        gaps = analyze_item9_collect_log_gaps(
            "END item9-prospective-20260918-epoch-fed2d9f7-aapl-121031\n",
            truncated=True,
        )
        self.assertTrue(gaps["truncated"])
        self.assertEqual(gaps["analysis_completeness"], "PARTIAL_TAIL")

    def test_missing_default_collector_log(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            imp_root = Path(tmp)
            text, meta = read_item9_collector_log_text(imp_root, {})
            self.assertIsNone(text)
            self.assertEqual(meta.get("availability"), StoredPathAvailability.NOT_OBSERVED.value)
            self.assertEqual(meta.get("reason_code"), "COLLECTOR_LOG_NOT_CONFIGURED")
            self.assertEqual(meta.get("truncated"), False)
            self.assertEqual(meta.get("freshness"), "NOT_OBSERVED")

    def test_env_override_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            imp_root = Path(tmp)
            missing = imp_root / "no-such-collector.log"
            text, meta = read_item9_collector_log_text(
                imp_root,
                {ITEM9_COLLECTOR_LOG_ENV: str(missing)},
            )
            self.assertIsNone(text)
            self.assertEqual(meta.get("availability"), StoredPathAvailability.UNAVAILABLE.value)
            self.assertEqual(meta.get("reason_code"), "FILE_NOT_FOUND")

    def test_stale_collector_log_freshness(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            imp_root = Path(tmp)
            log_path = imp_root / "collector.log"
            log_path.write_text("START item9-prospective-20260918-epoch-fed2d9f7-aapl-121031\n", encoding="utf-8")
            now_ns = time.time_ns() + int((COLLECTOR_LOG_STALE_AFTER_SECONDS + 60) * 1_000_000_000)
            text, meta = read_item9_collector_log_text(
                imp_root,
                {ITEM9_COLLECTOR_LOG_ENV: str(log_path)},
                now_ns=now_ns,
            )
            self.assertIsNotNone(text)
            self.assertEqual(meta.get("freshness"), "STALE")
            self.assertEqual(meta.get("availability"), StoredPathAvailability.AVAILABLE.value)

    def test_truncated_tail_drops_partial_first_line(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            imp_root = Path(tmp)
            log_path = imp_root / "collector.log"
            start_line = "START item9-prospective-20260918-epoch-fed2d9f7-aapl-111111\n"
            end_line = "END item9-prospective-20260918-epoch-fed2d9f7-aapl-222222 exit=1\n"
            prefix = "x" * 80
            body = prefix + start_line + ("y" * 40) + "\n" + end_line
            log_path.write_text(body, encoding="utf-8")
            max_bytes = len(end_line) + 10
            text, meta = read_item9_collector_log_text(
                imp_root,
                {ITEM9_COLLECTOR_LOG_ENV: str(log_path)},
                max_bytes=max_bytes,
            )
            self.assertTrue(meta.get("truncated"))
            self.assertGreater(meta.get("bytes_omitted"), 0)
            self.assertIsNotNone(text)
            self.assertNotIn("111111", text or "")
            self.assertIn("222222", text or "")
            gaps = analyze_item9_collect_log_gaps(text or "", truncated=True)
            self.assertEqual(gaps["analysis_completeness"], "PARTIAL_TAIL")
            self.assertEqual(gaps["started_epoch_count"], 0)

    def test_foreign_collector_log_path_classified(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            imp_root = Path(tmp)
            if sys.platform == "win32":
                foreign = "/var/log/item9-prospective-collector.log"
                expected_reason = "POSIX_ABSOLUTE_ON_WINDOWS"
            else:
                foreign = r"C:\Users\adame\logs\item9-prospective-collector.log"
                expected_reason = "WINDOWS_ABSOLUTE_ON_NON_WINDOWS"
            resolution = resolve_item9_collector_log_path(imp_root, {ITEM9_COLLECTOR_LOG_ENV: foreign})
            self.assertEqual(resolution.availability, StoredPathAvailability.FOREIGN_PLATFORM)
            self.assertEqual(resolution.reason_code, expected_reason)
            text, meta = read_item9_collector_log_text(imp_root, {ITEM9_COLLECTOR_LOG_ENV: foreign})
            self.assertIsNone(text)
            self.assertEqual(meta.get("availability"), StoredPathAvailability.FOREIGN_PLATFORM.value)

    def test_foreign_receipt_dir_not_inventoried(self) -> None:
        if sys.platform == "win32":
            receipt_dir = "/opt/imp/receipts"
        else:
            receipt_dir = r"C:\Users\adame\receipts"
        inventory = analyze_item9_receipt_directory(receipt_dir)
        self.assertEqual(inventory["availability"], StoredPathAvailability.FOREIGN_PLATFORM.value)
        self.assertEqual(inventory["receipt_file_count"], 0)
        self.assertEqual(inventory["receipt_files"], [])

    def test_read_collector_log_via_env_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            imp_root = Path(tmp)
            log_path = imp_root / "session.utf8.log"
            log_path.write_text(_EPOCH_121031_LOG.strip() + "\n", encoding="utf-8")
            env = {ITEM9_COLLECTOR_LOG_ENV: str(log_path)}
            text, meta = read_item9_collector_log_text(imp_root, env)
            self.assertIsNotNone(text)
            self.assertEqual(meta.get("availability"), StoredPathAvailability.AVAILABLE.value)
            gaps = analyze_item9_collect_log_gaps(text or "")
            self.assertEqual(len(gaps["missing_receipt_epochs"]), 1)


if __name__ == "__main__":
    unittest.main()
