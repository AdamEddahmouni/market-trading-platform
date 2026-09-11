"""FTEP-V1 protocol reference loading and SHA-256 verification tests."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.paper_forward_bridge.protocol_ref import (  # noqa: E402
    ProtocolRefError,
    compute_protocol_doc_sha256,
    load_protocol_ref,
    resolve_protocol_doc_path,
    verify_protocol_ref,
    write_test_protocol_ref,
)
from market_platform_foundation.intelligence.paper_forward_bridge.activation import (  # noqa: E402
    ActivationManifestError,
    MANIFEST_SCHEMA_VERSION,
    ActivationManifestStatus,
    compute_manifest_fingerprint,
    derive_campaign_id,
    seed_test_frozen_manifest,
    write_activation_manifest,
)


class ForwardTestProtocolRefTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.campaigns_root = Path(self._tmp.name) / "forward-test-campaigns"
        self.campaigns_root.mkdir(parents=True, exist_ok=True)
        os.environ["IMP_FORWARD_TEST_CAMPAIGNS_DIR"] = str(self.campaigns_root)

    def tearDown(self) -> None:
        os.environ.pop("IMP_FORWARD_TEST_CAMPAIGNS_DIR", None)
        self._tmp.cleanup()

    def test_write_and_verify_protocol_ref(self) -> None:
        ref = write_test_protocol_ref(self.campaigns_root, campaign_slug="test-campaign")
        verified = verify_protocol_ref("test-campaign", campaigns_root_override=self.campaigns_root)
        self.assertEqual(verified.protocol_id, ref.protocol_id)
        doc_path = resolve_protocol_doc_path(ref)
        self.assertEqual(compute_protocol_doc_sha256(doc_path), ref.protocol_doc_sha256)

    def test_protocol_doc_sha256_mismatch_fails(self) -> None:
        ref = write_test_protocol_ref(self.campaigns_root, campaign_slug="bad-ref")
        path = self.campaigns_root / "bad-ref" / "PROTOCOL_REF.json"
        payload = load_protocol_ref("bad-ref", campaigns_root_override=self.campaigns_root)
        tampered = dict(payload.raw)
        tampered["protocol_doc_sha256"] = "0" * 64
        path.write_text(__import__("json").dumps(tampered, indent=2, sort_keys=True) + "\n")
        with self.assertRaises(ProtocolRefError) as ctx:
            verify_protocol_ref("bad-ref", campaigns_root_override=self.campaigns_root)
        self.assertEqual(str(ctx.exception), "PROTOCOL_REF_DOC_SHA256_MISMATCH")

    def test_frozen_manifest_requires_valid_protocol_ref(self) -> None:
        slug = "missing-protocol-ref"
        manifest = {
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "campaign_slug": slug,
            "protocol_id": "FTEP-V1/0.1.0-PREREG",
            "activation_status": ActivationManifestStatus.FROZEN.value,
            "status": ActivationManifestStatus.FROZEN.value,
            "owner_decisions_pending": [],
            "binding": {
                "run_kind": "FORWARD_TEST",
                "mode": "PAPER",
                "test_mode": "SIGNAL_ONLY",
                "universe": {"symbols": ["ACME"], "asset_class": "FUTURES_EQUITY_INDEX"},
                "cohort_arms": {
                    "baseline": {
                        "policy_id": "news_deterministic_baseline",
                        "policy_version": "1.0.0",
                    }
                },
                "evaluation_horizon_ns": 3_600_000_000_000,
            },
        }
        fingerprint = compute_manifest_fingerprint(manifest)
        manifest["manifest_fingerprint"] = fingerprint
        manifest["campaign_id"] = derive_campaign_id(manifest)
        path = self.campaigns_root / slug / "ACTIVATION_MANIFEST.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.assertRaises(ActivationManifestError) as ctx:
            write_activation_manifest(path, manifest, campaigns_root_override=self.campaigns_root)
        self.assertIn("PROTOCOL_REF_NOT_FOUND", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
