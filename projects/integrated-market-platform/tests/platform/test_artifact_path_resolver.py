"""Artifact path portability and Item 9 expected-cycle gap analysis."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.platform.artifact_path_resolver import (  # noqa: E402
    StoredPathAvailability,
    analyze_item9_collect_log_gaps,
    analyze_item9_receipt_directory,
    classify_stored_path,
    portable_stored_path,
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


if __name__ == "__main__":
    unittest.main()
