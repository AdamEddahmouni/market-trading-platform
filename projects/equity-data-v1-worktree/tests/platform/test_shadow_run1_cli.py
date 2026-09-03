import argparse
import contextlib
import io
import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools" / "research"))

import run_shadow_run as cli


class CliOpenTests(unittest.TestCase):
    def test_open_refuses_dirty_tree_and_writes_immutable_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            calls = {"rev-parse": b"abc123\n", "status": b" M file.py\n"}

            def fake_git(args):
                return calls[args]

            rc, payload = cli.cmd_open(
                {
                    "instrument": "BIYA",
                    "first_session": "2026-08-24",
                    "holidays": "",
                    "early_closes": "",
                    "capture_id": "CAP1",
                    "store_root": root,
                    "allow_dirty": False,
                    "_git_head": fake_git,
                }
            )
            self.assertNotEqual(rc, 0)
            self.assertIn("DIRTY_TREE", json.dumps(payload))

            calls["status"] = b""
            rc, payload = cli.cmd_open(
                {
                    "instrument": "BIYA",
                    "first_session": "2026-08-24",
                    "holidays": "",
                    "early_closes": "",
                    "capture_id": "CAP1",
                    "store_root": root,
                    "allow_dirty": False,
                    "_git_head": fake_git,
                }
            )
            self.assertEqual(rc, 0)
            run_id = payload["run_id"]
            exp = cli.open_experiment_store(root)
            contract = exp.manifest(run_id)
            self.assertIsNotNone(contract)
            # Second open of same run verifies, never rewrites:
            before = contract["created_at_ns"]
            rc2, payload2 = cli.cmd_open(
                {
                    "instrument": "BIYA",
                    "first_session": "2026-08-24",
                    "holidays": "",
                    "early_closes": "",
                    "capture_id": "CAP1",
                    "store_root": root,
                    "allow_dirty": False,
                    "_git_head": fake_git,
                    "run_id": run_id,
                }
            )
            self.assertEqual(rc2, 0)
            self.assertTrue(payload2.get("verified"))
            self.assertEqual(exp.manifest(run_id)["created_at_ns"], before)
            exp.close()

    def test_status_close_report_smoke(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            head = lambda _: b"abc123\n"
            open_args = {
                "instrument": "BIYA", "first_session": "2026-08-24",
                "holidays": "", "early_closes": "", "capture_id": "CAP1",
                "store_root": root, "allow_dirty": False, "_git_head": head,
            }
            rc, payload = cli.cmd_open(open_args)
            self.assertEqual(rc, 0)
            run_id = payload["run_id"]

            ns = argparse.Namespace
            rc_s, status = cli.cmd_status(ns(run_id=run_id, store_root=root))
            self.assertEqual((rc_s, status["state"]), (0, "OPEN"))

            # Stopping rule not met -> close refuses without --force.
            rc_c, _ = cli.cmd_close(ns(run_id=run_id, store_root=root, force=False, reason=""))
            self.assertEqual(rc_c, 4)

            rc_f, forced = cli.cmd_close(ns(run_id=run_id, store_root=root, force=True, reason="smoke"))
            self.assertEqual((rc_f, forced["state"]), (0, "CLOSED"))

            rc_r, report = cli.cmd_report(ns(run_id=run_id, store_root=root))
            self.assertEqual(rc_r, 0)
            self.assertIn("terminology", report)


if __name__ == "__main__":
    unittest.main()
