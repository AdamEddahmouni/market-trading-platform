"""FTEP catalyst watch dry-run / fixture mode."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]

from market_platform_foundation.intelligence.paper_forward_bridge.ftep_catalyst_watch import (  # noqa: E402
    collect_ftep_catalyst_watch,
    load_governed_session_ids_from_evidence,
)
from market_platform_foundation.local_state.paths import REPO_ROOT


class FtepCatalystWatchTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["IMP_PERSIST_STATE"] = "1"

    def test_fixture_smoke_when_no_governed_sessions(self) -> None:
        status_no_sessions = {
            "governed_session_count": 0,
            "empirical_lock_count": 0,
            "us_equity_rth_open": False,
            "manifest_fingerprint": "F7083180990BC59578CA045E1E1318A356421BBC9B81EE514C14130CB0B356B1",
        }
        with patch(
            "market_platform_foundation.intelligence.paper_forward_bridge.ftep_catalyst_watch.operator_primary_imp_root_for_evidence",
            return_value=None,
        ), patch(
            "market_platform_foundation.intelligence.paper_forward_bridge.ftep_catalyst_watch.collect_ftep_campaign_status",
            return_value=status_no_sessions,
        ), patch(
            "market_platform_foundation.intelligence.paper_forward_bridge.ftep_catalyst_watch.load_governed_session_ids_from_evidence",
            return_value=([], None),
        ):
            payload = collect_ftep_catalyst_watch(REPO_ROOT, "FTEP-V1-002", fixture_only=True)
        self.assertEqual(payload["disposition"], "PASS")
        self.assertEqual(payload["watch_mode"], "FIXTURE_SMOKE")
        self.assertEqual(payload["summary_count"], 2)
        self.assertEqual(payload["governed_session_ids"], [])
        self.assertTrue(payload["dry_run"])

    def test_watch_catalysts_cli_json(self) -> None:
        env = os.environ.copy()
        env["IMP_PERSIST_STATE"] = "1"
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools" / "ftep_watch_catalysts.py"),
                "FTEP-V1-002",
                "--fixture",
                "--json",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
        self.assertEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["artifact_kind"], "ftep_catalyst_watch_report")

    def test_session_ids_resolve_from_operator_primary_when_worktree_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            worktree = tmp_path / "wt" / "projects" / "integrated-market-platform"
            primary = tmp_path / "main" / "projects" / "integrated-market-platform"
            worktree.mkdir(parents=True)
            primary.mkdir(parents=True)
            (primary / "phase0-dependency-lock.json").write_text("{}", encoding="utf-8")
            evid_dir = primary / "artifacts" / "ftep-v1-002"
            evid_dir.mkdir(parents=True)
            record = {
                "artifact_kind": "ftep_governed_session_start_evidence",
                "sessions_created": [
                    {"session_id": "fts-6DB7771FD9B3A991", "cohort_arm": "BASELINE"},
                    {"session_id": "fts-D93189A042A1BEF2", "cohort_arm": "AI_ENHANCED"},
                ],
            }
            (evid_dir / "governed-session-start-evidence.jsonl").write_text(
                json.dumps(record) + "\n",
                encoding="utf-8",
            )
            with patch(
                "market_platform_foundation.intelligence.paper_forward_bridge.ftep_catalyst_watch.main_working_tree",
                return_value=tmp_path / "main",
            ):
                ids, path = load_governed_session_ids_from_evidence(worktree, "FTEP-V1-002")
        self.assertEqual(ids, ["fts-6DB7771FD9B3A991", "fts-D93189A042A1BEF2"])
        self.assertIsNotNone(path)
        self.assertTrue(str(path).endswith("governed-session-start-evidence.jsonl"))

    def test_worktree_session_ids_take_precedence_over_primary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            worktree = tmp_path / "wt" / "projects" / "integrated-market-platform"
            primary = tmp_path / "main" / "projects" / "integrated-market-platform"
            worktree.mkdir(parents=True)
            primary.mkdir(parents=True)
            (primary / "phase0-dependency-lock.json").write_text("{}", encoding="utf-8")
            for root, session_id in (
                (worktree, "fts-WORKTREE"),
                (primary, "fts-PRIMARY"),
            ):
                evid_dir = root / "artifacts" / "ftep-v1-002"
                evid_dir.mkdir(parents=True)
                record = {
                    "artifact_kind": "ftep_governed_session_start_evidence",
                    "sessions_created": [{"session_id": session_id}],
                }
                (evid_dir / "governed-session-start-evidence.jsonl").write_text(
                    json.dumps(record) + "\n",
                    encoding="utf-8",
                )
            with patch(
                "market_platform_foundation.intelligence.paper_forward_bridge.ftep_catalyst_watch.main_working_tree",
                return_value=tmp_path / "main",
            ):
                ids, path = load_governed_session_ids_from_evidence(worktree, "FTEP-V1-002")
        self.assertEqual(ids, ["fts-WORKTREE"])
        self.assertIsNotNone(path)
        self.assertIn("wt", str(path).replace("\\", "/"))


if __name__ == "__main__":
    unittest.main()
