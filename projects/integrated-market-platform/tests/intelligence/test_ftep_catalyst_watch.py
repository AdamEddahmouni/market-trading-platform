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
    load_governed_session_observation_window_start_ns,
)
from market_platform_foundation.local_state.paths import REPO_ROOT

# SOFTWARE_CONTROLLED clocks — not market evidence.
_OLD_SEGMENT_NS = 1_700_000_000_000_000_000
_CURRENT_SEGMENT_NS = 1_750_000_000_000_000_000
_STRAY_LATER_NS = 1_760_000_000_000_000_000


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

    def test_observation_window_none_when_only_older_history_and_no_current_segment_arg(
        self,
    ) -> None:
        """Older successful sessions_created alone must not become THIS arm's window."""

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            root = tmp_path / "projects" / "integrated-market-platform"
            root.mkdir(parents=True)
            evid_dir = root / "artifacts" / "ftep-v1-002"
            evid_dir.mkdir(parents=True)
            (evid_dir / "governed-session-start-evidence.jsonl").write_text(
                json.dumps(
                    {
                        "artifact_kind": "ftep_governed_session_start_evidence",
                        "recorded_at_ns": _OLD_SEGMENT_NS,
                        "sessions_created": [{"session_id": "fts-OLD-ONLY"}],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            with patch(
                "market_platform_foundation.intelligence.paper_forward_bridge.ftep_catalyst_watch.operator_primary_imp_root_for_evidence",
                return_value=None,
            ):
                # Caller did not pass this arm's id/start → fail closed.
                window_ns = load_governed_session_observation_window_start_ns(
                    root,
                    "FTEP-V1-002",
                )

        self.assertIsNone(window_ns)

    def test_observation_window_uses_explicit_current_segment_not_history_extrema(
        self,
    ) -> None:
        """Explicit current start wins; older + stray-later (other id) must not."""

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            worktree = tmp_path / "wt" / "projects" / "integrated-market-platform"
            primary = tmp_path / "main" / "projects" / "integrated-market-platform"
            worktree.mkdir(parents=True)
            primary.mkdir(parents=True)
            (primary / "phase0-dependency-lock.json").write_text("{}", encoding="utf-8")

            primary_evid = primary / "artifacts" / "ftep-v1-002"
            primary_evid.mkdir(parents=True)
            (primary_evid / "governed-session-start-evidence.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "artifact_kind": "ftep_governed_session_start_evidence",
                                "recorded_at_ns": _OLD_SEGMENT_NS,
                                "sessions_created": [{"session_id": "fts-OLD-PRIMARY"}],
                            }
                        ),
                        json.dumps(
                            {
                                "artifact_kind": "ftep_governed_session_start_evidence",
                                "recorded_at_ns": _STRAY_LATER_NS,
                                "sessions_created": [{"session_id": "fts-STRAY-LATER"}],
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            worktree_evid = worktree / "artifacts" / "ftep-v1-002"
            worktree_evid.mkdir(parents=True)
            (worktree_evid / "governed-session-start-evidence.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "artifact_kind": "ftep_governed_session_start_evidence",
                                "recorded_at_ns": _OLD_SEGMENT_NS + 1,
                                "sessions_created": [{"session_id": "fts-OLD-WT"}],
                            }
                        ),
                        json.dumps(
                            {
                                "artifact_kind": "ftep_governed_session_start_evidence",
                                "recorded_at_ns": _CURRENT_SEGMENT_NS,
                                "sessions_created": [{"session_id": "fts-CURRENT"}],
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            with patch(
                "market_platform_foundation.intelligence.paper_forward_bridge.ftep_catalyst_watch.main_working_tree",
                return_value=tmp_path / "main",
            ):
                by_start = load_governed_session_observation_window_start_ns(
                    worktree,
                    "FTEP-V1-002",
                    current_segment_start_ns=_CURRENT_SEGMENT_NS,
                )
                by_id = load_governed_session_observation_window_start_ns(
                    worktree,
                    "FTEP-V1-002",
                    current_segment_session_id="fts-CURRENT",
                )

        self.assertEqual(by_start, _CURRENT_SEGMENT_NS)
        self.assertEqual(by_id, _CURRENT_SEGMENT_NS)
        self.assertNotEqual(by_start, _OLD_SEGMENT_NS)
        self.assertNotEqual(by_start, _STRAY_LATER_NS)
        self.assertNotEqual(by_id, _STRAY_LATER_NS)

    def test_observation_window_none_without_current_segment_even_if_other_roots_have_history(
        self,
    ) -> None:
        """Missing current-segment arg → None despite successful history on other roots."""

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            worktree = tmp_path / "wt" / "projects" / "integrated-market-platform"
            primary = tmp_path / "main" / "projects" / "integrated-market-platform"
            worktree.mkdir(parents=True)
            primary.mkdir(parents=True)
            (primary / "phase0-dependency-lock.json").write_text("{}", encoding="utf-8")

            primary_evid = primary / "artifacts" / "ftep-v1-002"
            primary_evid.mkdir(parents=True)
            (primary_evid / "governed-session-start-evidence.jsonl").write_text(
                json.dumps(
                    {
                        "artifact_kind": "ftep_governed_session_start_evidence",
                        "recorded_at_ns": _OLD_SEGMENT_NS,
                        "sessions_created": [{"session_id": "fts-OTHER-ROOT"}],
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            with patch(
                "market_platform_foundation.intelligence.paper_forward_bridge.ftep_catalyst_watch.main_working_tree",
                return_value=tmp_path / "main",
            ):
                window_ns = load_governed_session_observation_window_start_ns(
                    worktree,
                    "FTEP-V1-002",
                )
                missing_root = load_governed_session_observation_window_start_ns(
                    tmp_path / "absent-root",
                    "FTEP-V1-002",
                )
                unknown_id = load_governed_session_observation_window_start_ns(
                    worktree,
                    "FTEP-V1-002",
                    current_segment_session_id="fts-THIS-ARM-ABSENT",
                )

        self.assertIsNone(window_ns)
        self.assertIsNone(missing_root)
        self.assertIsNone(unknown_id)


if __name__ == "__main__":
    unittest.main()
