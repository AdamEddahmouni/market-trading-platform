"""State path operator diagnostic tests."""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(ROOT))

from tools.state_path_diagnostic import (  # noqa: E402
    collect_state_path_report,
    effective_state_dir,
)


class StatePathDiagnosticTests(unittest.TestCase):
    def test_effective_state_dir_honors_imp_state_dir(self) -> None:
        imp_root = Path(tempfile.mkdtemp())
        override = Path(tempfile.mkdtemp())
        prior = os.environ.pop("IMP_STATE_DIR", None)
        try:
            os.environ["IMP_STATE_DIR"] = str(override)
            self.assertEqual(effective_state_dir(imp_root), override.resolve())
        finally:
            if prior is not None:
                os.environ["IMP_STATE_DIR"] = prior
            else:
                os.environ.pop("IMP_STATE_DIR", None)

    def test_worktree_mismatch_warning_when_canonical_has_sessions(self) -> None:
        imp_root = Path(tempfile.mkdtemp())
        canonical = Path(tempfile.mkdtemp())
        effective = Path(tempfile.mkdtemp())
        canonical_db = canonical / "imp-state.sqlite3"
        connection = sqlite3.connect(canonical_db)
        connection.execute(
            """
            CREATE TABLE forward_test_sessions (
                session_id TEXT PRIMARY KEY
            )
            """
        )
        connection.execute("INSERT INTO forward_test_sessions(session_id) VALUES ('fts-TEST')")
        connection.commit()
        connection.close()

        prior_canonical = os.environ.pop("IMP_CANONICAL_STATE_DIR", None)
        prior_effective = os.environ.pop("IMP_STATE_DIR", None)
        try:
            os.environ["IMP_CANONICAL_STATE_DIR"] = str(canonical)
            os.environ["IMP_STATE_DIR"] = str(effective)
            report = collect_state_path_report(imp_root)
        finally:
            if prior_canonical is not None:
                os.environ["IMP_CANONICAL_STATE_DIR"] = prior_canonical
            else:
                os.environ.pop("IMP_CANONICAL_STATE_DIR", None)
            if prior_effective is not None:
                os.environ["IMP_STATE_DIR"] = prior_effective
            else:
                os.environ.pop("IMP_STATE_DIR", None)

        self.assertIn("WORKTREE_STATE_MISMATCH", report["warnings"])
        self.assertEqual(report["canonical_forward_test_session_count"], 1)
        self.assertIsNone(report["effective_forward_test_session_count"])

    def test_state_path_cli_json(self) -> None:
        import subprocess
        import sys

        env = os.environ.copy()
        env.pop("IMP_STATE_DIR", None)
        env.pop("IMP_CANONICAL_STATE_DIR", None)
        env.pop("IMP_PERSIST_STATE", None)
        result = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "state_path_diagnostic.py")],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
        self.assertTrue(result.stdout.strip(), msg=result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["artifact_kind"], "imp_state_path_diagnostic")


if __name__ == "__main__":
    unittest.main()
