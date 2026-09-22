"""Authorization packet is not a grant; execute must refuse it."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.paper.calibration.item9_calibration_execute import (  # noqa: E402
    inspect_authorization_artifact,
    refuse_calibration_execution_before_corpus_read,
)
from market_platform_foundation.paper.calibration.item9_validation_readiness_contract import (  # noqa: E402
    AUTHORIZATION_ABSENT,
    AUTHORIZATION_INVALID,
    AUTHORIZATION_PACKET_SCHEMA_ID,
    CALIBRATION_EXECUTION_REFUSED,
    FITTING_ALLOWED_DEFAULT,
)


class Item9AuthorizationPacketNotGrantTests(unittest.TestCase):
    def test_tracked_packet_template_is_not_a_grant(self) -> None:
        path = ROOT / "manifests" / "paper" / "item9_calibration_authorization_packet_v1.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(payload["schema_id"], AUTHORIZATION_PACKET_SCHEMA_ID)
        self.assertEqual(payload["packet_role"], "NOT_AN_AUTHORIZATION_GRANT")
        self.assertFalse(payload["fitting_allowed"])
        self.assertFalse(payload["calibrated"])
        self.assertTrue(payload["does_not_authorize_calibration"])
        self.assertEqual(payload["authorization_state"], AUTHORIZATION_ABSENT)

    def test_packet_path_refused_by_execute_inspector(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            packet_path = Path(tmp) / "packet.json"
            packet_path.write_text(
                json.dumps(
                    {
                        "schema_id": AUTHORIZATION_PACKET_SCHEMA_ID,
                        "packet_role": "NOT_AN_AUTHORIZATION_GRANT",
                        "grant": "DENIED_PACKET_IS_NOT_A_GRANT",
                        "fitting_allowed": False,
                        "authorization_state": AUTHORIZATION_ABSENT,
                    }
                ),
                encoding="utf-8",
            )
            inspected = inspect_authorization_artifact(packet_path)
            self.assertEqual(inspected["authorization_state"], AUTHORIZATION_INVALID)
            self.assertFalse(inspected["valid"])
            self.assertEqual(inspected["reason"], "AUTHORIZATION_PACKET_IS_NOT_A_GRANT")
            result = refuse_calibration_execution_before_corpus_read(
                authorization_path=packet_path,
                receipt_dir=None,
                imp_root=ROOT,
            )
            self.assertEqual(result["verdict"], CALIBRATION_EXECUTION_REFUSED)
            self.assertEqual(result["reason"], "AUTHORIZATION_REQUIRED_BEFORE_CORPUS_READ")
            self.assertFalse(result["corpus_read_attempted"])
            self.assertEqual(result["fitting_allowed"], FITTING_ALLOWED_DEFAULT)

    def test_packet_schema_with_forged_grant_still_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            forged = Path(tmp) / "forged.json"
            forged.write_text(
                json.dumps(
                    {
                        "schema_id": AUTHORIZATION_PACKET_SCHEMA_ID,
                        "packet_role": "NOT_AN_AUTHORIZATION_GRANT",
                        "grant": "ITEM9_CALIBRATION_RUN_AUTHORIZED",
                        "fitting_allowed": False,
                    }
                ),
                encoding="utf-8",
            )
            inspected = inspect_authorization_artifact(forged)
            self.assertEqual(inspected["authorization_state"], AUTHORIZATION_INVALID)
            self.assertEqual(inspected["reason"], "AUTHORIZATION_PACKET_IS_NOT_A_GRANT")


if __name__ == "__main__":
    unittest.main()
