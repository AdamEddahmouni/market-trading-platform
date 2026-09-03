import tempfile
import unittest
from pathlib import Path

from market_platform_foundation.distribution import build_distribution, validate_lock


class DistributionTests(unittest.TestCase):
    def test_lock_has_zero_third_party_dependencies(self):
        report = validate_lock(Path("phase0-dependency-lock.json"))
        self.assertEqual(report["third_party_count"], 0)
        self.assertEqual(report["prohibited_matches"], [])

    def test_two_builds_are_byte_identical(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            one = build_distribution(Path("."), Path(first))
            two = build_distribution(Path("."), Path(second))
            self.assertEqual(one["archive_sha256"], two["archive_sha256"])
            self.assertEqual(one["manifest_sha256"], two["manifest_sha256"])

    def test_named_audit_modules_are_distributable(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = build_distribution(Path("."), Path(tmp))
            manifest = (Path(tmp) / result["manifest_path"]).read_text(encoding="utf-8")
            self.assertIn("src/market_platform_foundation/credential_audit.py", manifest)
            self.assertIn("tests/phase0/test_credential_audit.py", manifest)

    def test_revision_3_guidance_is_bound_into_distribution(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = build_distribution(Path("."), Path(tmp))
            manifest = (Path(tmp) / result["manifest_path"]).read_text(
                encoding="utf-8"
            )
            self.assertIn("docs/research/donors/DONOR_REUSE_MATRIX.md", manifest)
            self.assertIn("docs/architecture/SWIM_WITH_THE_WHALES.md", manifest)
            self.assertIn("docs/roadmap/REVISION_3_ROADMAP.md", manifest)

    def test_lf_checkout_policy_is_bound_into_distribution(self):
        attributes = Path(".gitattributes")
        self.assertTrue(attributes.is_file())
        self.assertEqual(attributes.read_bytes(), b"* text=auto eol=lf\n")
        with tempfile.TemporaryDirectory() as tmp:
            result = build_distribution(Path("."), Path(tmp))
            manifest = (Path(tmp) / result["manifest_path"]).read_text(
                encoding="utf-8"
            )
            self.assertIn('"path":".gitattributes"', manifest)

    def test_symlink_or_reparse_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            outside = Path(tmp) / "outside.txt"
            outside.write_text("outside", encoding="utf-8")
            link = Path("src") / "market_platform_foundation" / "escape-test-link"
            try:
                try:
                    link.symlink_to(outside)
                except OSError:
                    self.skipTest("symlink creation is unavailable")
                with self.assertRaises(ValueError):
                    build_distribution(Path("."), Path(tmp) / "output")
            finally:
                if link.is_symlink():
                    link.unlink()
