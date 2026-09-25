"""Durable Workspace investigation and authority boundary."""

from __future__ import annotations

import tempfile
import unittest
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from market_platform_foundation.local_state.connection import LocalStateConnection
from market_platform_foundation.local_state.migrations import MIGRATIONS
from market_platform_foundation.local_state.repository import LocalStateRepository
from market_platform_foundation.local_state.schema import SCHEMA_VERSION
from market_platform_foundation.ui_api import workspace_investigations as api


class WorkspaceInvestigationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "state.sqlite"
        self.connection = LocalStateConnection(self.db)
        self.repo = LocalStateRepository(self.connection)
        self.patch = patch.object(api, "open_local_state", side_effect=lambda: self.repo)
        self.patch.start()

    def tearDown(self) -> None:
        self.patch.stop()
        self.connection.close()
        self.temp.cleanup()

    def test_radar_context_and_note_resume_after_reopen(self) -> None:
        row = api.create_investigation({
            "title": "AAPL catalyst", "instrument_id": "AAPL",
            "source_kind": "radar_attention", "source_id": "summary-42",
            "opportunity_id": "opp-42",
        }, data_mode="FIXTURE_REPLAY", execution_mode="INTERNAL_SIMULATION", execution_authority="PAPER_ONLY", opportunity_repository=SimpleNamespace(
            get_opportunity=lambda _id: SimpleNamespace(scope=SimpleNamespace(instrument_ids=("AAPL",)))
        ))
        self.assertEqual(row["source_id"], "summary-42")
        self.assertEqual(row["opportunity_id"], "opp-42")
        again = api.create_investigation({
            "title": "AAPL catalyst", "instrument_id": "AAPL", "source_kind": "radar_attention",
            "source_id": "summary-42", "opportunity_id": "opp-42",
        }, data_mode="FIXTURE_REPLAY", execution_mode="INTERNAL_SIMULATION", execution_authority="PAPER_ONLY", opportunity_repository=SimpleNamespace(
            get_opportunity=lambda _id: SimpleNamespace(scope=SimpleNamespace(instrument_ids=("AAPL",)))
        ))
        self.assertEqual(again["workspace_id"], row["workspace_id"])
        saved = api.save_note(row["workspace_id"], {"note": "Check source timestamp", "expected_note": ""}, data_mode="FIXTURE_REPLAY", execution_mode="INTERNAL_SIMULATION", execution_authority="PAPER_ONLY")
        self.assertEqual(saved["note"], "Check source timestamp")
        with self.assertRaisesRegex(ValueError, "WORKSPACE_NOTE_CONFLICT"):
            api.save_note(row["workspace_id"], {"note": "stale overwrite", "expected_note": ""}, data_mode="FIXTURE_REPLAY", execution_mode="INTERNAL_SIMULATION", execution_authority="PAPER_ONLY")
        self.connection.close()
        self.connection = LocalStateConnection(self.db)
        self.repo = LocalStateRepository(self.connection)
        self.assertEqual(self.connection.schema_version(), SCHEMA_VERSION)
        self.assertEqual(api.get_investigation(row["workspace_id"])["note"], "Check source timestamp")
        self.assertEqual(api.get_investigation(row["workspace_id"])["opportunity_id"], "opp-42")
        self.assertEqual(api.list_investigations()["investigations"][0]["instrument_id"], "AAPL")

    def test_demo_and_invalid_inputs_fail_closed(self) -> None:
        body = {"title": "AAPL", "instrument_id": "AAPL"}
        with self.assertRaises(PermissionError):
            api.create_investigation(body, data_mode="FIXTURE_REPLAY")
        paper = api.create_investigation(
            body, data_mode="FIXTURE_REPLAY", execution_mode="INTERNAL_SIMULATION",
            execution_authority="PAPER_ONLY",
        )
        self.assertEqual(paper["instrument_id"], "AAPL")
        with self.assertRaises(PermissionError):
            api.save_note(paper["workspace_id"], {"note": "x", "expected_note": ""}, data_mode="FIXTURE_REPLAY")
        with self.assertRaises(PermissionError):
            api.create_investigation(body, data_mode="LIVE_OBSERVATIONAL")
        with self.assertRaises(PermissionError):
            api.create_investigation(body, data_mode="FIXTURE_REPLAY", execution_mode="INTERNAL_SIMULATION", execution_authority="AUTHORIZED")
        with self.assertRaises(ValueError):
            api.create_investigation({**body, "source_kind": "radar_attention"}, data_mode="FIXTURE_REPLAY", execution_mode="INTERNAL_SIMULATION", execution_authority="PAPER_ONLY")
        with self.assertRaises(KeyError):
            api.save_note("missing", {"note": "x", "expected_note": ""}, data_mode="FIXTURE_REPLAY", execution_mode="INTERNAL_SIMULATION", execution_authority="PAPER_ONLY")
        with self.assertRaisesRegex(ValueError, "WORKSPACE_OPPORTUNITY_NOT_FOUND"):
            api.create_investigation({**body, "source_kind": "radar_attention", "source_id": "summary-1", "opportunity_id": "missing"}, data_mode="FIXTURE_REPLAY", execution_mode="INTERNAL_SIMULATION", execution_authority="PAPER_ONLY")

    def test_upgrade_from_v9_retains_existing_state(self) -> None:
        self.connection.close()
        self.db.unlink()
        raw = sqlite3.connect(self.db)
        try:
            for version in range(1, 10):
                for statement in MIGRATIONS[version]:
                    raw.execute(statement)
                raw.execute("INSERT INTO schema_meta(schema_version, applied_at) VALUES (?, 'prior')", (version,))
            raw.execute("INSERT INTO operator_preferences(pref_key, pref_value, updated_at) VALUES ('workspace-test', 'prior', 1)")
            raw.commit()
        finally:
            raw.close()
        self.connection = LocalStateConnection(self.db)
        self.repo = LocalStateRepository(self.connection)
        self.assertEqual(self.connection.schema_version(), SCHEMA_VERSION)
        self.assertEqual(self.connection.execute("SELECT pref_value FROM operator_preferences WHERE pref_key='workspace-test'").fetchone()[0], "prior")
        self.assertEqual(self.repo.list_investigations(), [])

    def test_parallel_radar_handoff_reuses_one_record(self) -> None:
        body = {
            "title": "BIYA investigation", "instrument_id": "BIYA",
            "source_kind": "radar_attention", "source_id": "attention-1",
        }
        with ThreadPoolExecutor(max_workers=6) as pool:
            rows = list(pool.map(lambda _: api.create_investigation(body, data_mode="FIXTURE_REPLAY", execution_mode="INTERNAL_SIMULATION", execution_authority="PAPER_ONLY"), range(12)))
        self.assertEqual(len({row["workspace_id"] for row in rows}), 1)
        self.assertEqual(len(self.repo.list_investigations()), 1)


if __name__ == "__main__":
    unittest.main()
