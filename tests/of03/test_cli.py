from __future__ import annotations

import io
import json
import unittest
from contextlib import redirect_stdout

from market_platform_foundation.of03.cli import main
from market_platform_foundation.of03.operations import execute


class CliTests(unittest.TestCase):
    def test_status_json(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = main(["--json", "status"])
        self.assertEqual(code, 0)
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload["capability_id"], "OF03.OP.STATUS")
        self.assertEqual(payload["outcome_code"], "OK")
        self.assertTrue(payload["verification"]["valid"])
        self.assertIn("snapshot_hash", payload["verification"])

    def test_show_requires_version_or_active(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = main(["--json", "show-definition", "--kind", "capability", "--id", "OF03.OP.STATUS"])
        self.assertEqual(code, 1)
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload["outcome_code"], "IMPLICIT_LATEST_PROHIBITED")

    def test_show_active(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = main(["--json", "show-definition", "--kind", "capability", "--id", "OF03.OP.STATUS", "--active"])
        self.assertEqual(code, 0)
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload["verification"]["definition"]["capability_id"], "OF03.OP.STATUS")

    def test_verify_bindings_not_invoked(self) -> None:
        result = execute("OF03.OP.VERIFY_BINDINGS")
        self.assertEqual(result.outcome_code, "OK")
        self.assertFalse(result.verification["invoked"])
        self.assertTrue(all(item["binding_invoked"] is False for item in result.verification["bindings"]))

    def test_list_and_snapshot(self) -> None:
        caps = execute("OF03.OP.LIST_CAPABILITIES")
        sops = execute("OF03.OP.LIST_SOPS")
        wfs = execute("OF03.OP.LIST_WORKFLOWS")
        snap = execute("OF03.OP.SNAPSHOT")
        self.assertEqual(len(caps.verification["capabilities"]), 88)
        self.assertEqual(len(sops.verification["sops"]), 41)
        self.assertEqual(len(wfs.verification["workflows"]), 30)
        self.assertEqual(len(snap.verification["registry_snapshot_hash"]), 64)


if __name__ == "__main__":
    unittest.main()
