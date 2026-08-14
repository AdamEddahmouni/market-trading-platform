import tempfile
import unittest
from pathlib import Path

from market_platform_foundation.authority import resolve_canonical_authority
from market_platform_foundation.canonical import (
    load_json_strict,
    sha256_bytes,
    write_canonical_json,
)


class AuthorityTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        specification_directory = self.root / "docs" / "superpowers" / "specs"
        governance_directory = self.root / "docs" / "superpowers" / "governance"
        manifest_directory = self.root / "manifests" / "phase0"
        specification_directory.mkdir(parents=True)
        governance_directory.mkdir(parents=True)
        manifest_directory.mkdir(parents=True)

        self.active_spec = specification_directory / "revision-3.md"
        self.revision_1 = specification_directory / "revision-1.md"
        self.revision_2 = specification_directory / "revision-2.md"
        self.approval = governance_directory / "revision-3-approval.json"
        self.manifest = manifest_directory / "canonical-authority.json"

        self.active_spec.write_bytes(b"revision 3\n")
        self.revision_1.write_bytes(b"revision 1\n")
        self.revision_2.write_bytes(b"revision 2\n")
        active_sha256 = sha256_bytes(self.active_spec.read_bytes())
        write_canonical_json(
            self.approval,
            {
                "logical_id": "foundation.canonical_specification.revision_3.approval",
                "specification_logical_id": "foundation.canonical_specification.revision_3",
                "specification_sha256": active_sha256,
                "status": "APPROVED",
            },
        )
        write_canonical_json(
            self.manifest,
            {
                "active_specification": {
                    "approval_logical_id": "foundation.canonical_specification.revision_3.approval",
                    "approval_path": self.approval.relative_to(self.root).as_posix(),
                    "approval_sha256": sha256_bytes(self.approval.read_bytes()),
                    "logical_id": "foundation.canonical_specification.revision_3",
                    "path": self.active_spec.relative_to(self.root).as_posix(),
                    "sha256": active_sha256,
                },
                "incorporated_specifications": [
                    {
                        "logical_id": "foundation.canonical_specification.revision_1",
                        "path": self.revision_1.relative_to(self.root).as_posix(),
                        "sha256": sha256_bytes(self.revision_1.read_bytes()),
                    },
                    {
                        "logical_id": "foundation.canonical_specification.revision_2",
                        "path": self.revision_2.relative_to(self.root).as_posix(),
                        "sha256": sha256_bytes(self.revision_2.read_bytes()),
                    },
                ],
                "manifest_version": "1.0.0",
                "phase0_authority": {
                    "logical_id": "foundation.canonical_specification.revision_2",
                    "path": self.revision_2.relative_to(self.root).as_posix(),
                    "sha256": sha256_bytes(self.revision_2.read_bytes()),
                },
                "phase0_status": "BLOCKED_PENDING_POSTROOT_ACCEPTANCE",
                "status": "EFFECTIVE",
            },
        )

    def test_approved_revision_3_is_the_only_active_authority(self):
        result = resolve_canonical_authority(self.root)
        self.assertEqual(result["status"], "PASS")
        self.assertTrue(result["one_canonical_specification"])
        self.assertEqual(
            result["active_logical_id"],
            "foundation.canonical_specification.revision_3",
        )

    def test_changed_active_specification_fails(self):
        self.active_spec.write_text("changed\n", encoding="utf-8")
        result = resolve_canonical_authority(self.root)
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("ACTIVE_SPECIFICATION_HASH_MISMATCH", result["reason_codes"])

    def test_missing_approval_blocks(self):
        self.approval.unlink()
        result = resolve_canonical_authority(self.root)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("APPROVAL_RECORD_MISSING", result["reason_codes"])

    def test_wrong_approval_binding_fails(self):
        approval = load_json_strict(self.approval)
        approval["specification_sha256"] = "0" * 64
        write_canonical_json(self.approval, approval)
        manifest = load_json_strict(self.manifest)
        manifest["active_specification"]["approval_sha256"] = sha256_bytes(
            self.approval.read_bytes()
        )
        write_canonical_json(self.manifest, manifest)
        result = resolve_canonical_authority(self.root)
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("APPROVAL_BINDING_MISMATCH", result["reason_codes"])

    def test_active_path_escape_fails(self):
        escaped = self.root.parent / "outside-authority.md"
        escaped.write_bytes(b"outside\n")
        self.addCleanup(escaped.unlink, missing_ok=True)
        manifest = load_json_strict(self.manifest)
        manifest["active_specification"]["path"] = "../outside-authority.md"
        manifest["active_specification"]["sha256"] = sha256_bytes(
            escaped.read_bytes()
        )
        write_canonical_json(self.manifest, manifest)

        result = resolve_canonical_authority(self.root)

        self.assertEqual(result["status"], "FAIL")
        self.assertIn("AUTHORITY_PATH_INVALID", result["reason_codes"])


if __name__ == "__main__":
    unittest.main()
