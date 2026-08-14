import tempfile
import unittest
from pathlib import Path

from market_platform_foundation.canonical import load_json_strict, sha256_bytes
from market_platform_foundation.evidence import finalize_artifact, publish_artifacts


class EvidenceTests(unittest.TestCase):
    def test_finalized_artifact_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "artifact.json"
            finalize_artifact(path, "phase0.registry_snapshot", {"rows": []})
            with self.assertRaises(FileExistsError):
                finalize_artifact(path, "phase0.registry_snapshot", {"rows": []})

    def test_content_hash_resolves(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "artifact.json"
            digest = finalize_artifact(path, "phase0.registry_snapshot", {"rows": []})
            self.assertEqual(digest, sha256_bytes(path.read_bytes()))
            record = load_json_strict(path)
            self.assertEqual(record["content_sha256"], sha256_bytes(b'{"rows":[]}\n'))

    def test_bundle_rejects_duplicate_logical_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                publish_artifacts(
                    Path(tmp),
                    [
                        ("phase0.registry_snapshot", {"rows": []}),
                        ("phase0.registry_snapshot", {"rows": []}),
                    ],
                )
