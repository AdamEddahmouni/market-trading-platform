"""FTEP Finviz prospective preflight — software only, no live fetch."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.paper_forward_bridge.ftep_finviz_prospective_preflight import (  # noqa: E402
    FtepFinvizProspectivePreflightOptions,
    run_ftep_finviz_prospective_preflight,
)

T_RTH_OPEN_NS = 1_789_394_400_000_000_000
T_RTH_CLOSED_NS = 1_789_322_400_000_000_000


def _status_ok() -> dict:
    return {
        "us_equity_rth_open": True,
        "governed_session_count": 2,
        "empirical_lock_count": 0,
        "manifest_fingerprint": (
            "F7083180990BC59578CA045E1E1318A356421BBC9B81EE514C14130CB0B356B1"
        ),
        "manifest_status": "FROZEN",
        "signal_only_authorized": True,
        "campaign_readiness_disposition": "READY",
        "empirical_counts_source": "durable",
    }


class FtepFinvizProspectivePreflightTests(unittest.TestCase):
    _ENV_KEYS = (
        "IMP_FINVIZ_LIVE",
        "IMP_FTEP_PROSPECTIVE_CATALYST_INGRESS",
        "IMP_PERSIST_STATE",
        "IMP_STATE_DIR",
    )

    def setUp(self) -> None:
        self._saved_env = {key: os.environ.get(key) for key in self._ENV_KEYS}
        for key in self._ENV_KEYS:
            os.environ.pop(key, None)

    def tearDown(self) -> None:
        for key, value in self._saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_software_ready_rth_required_when_closed_market(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_dir = Path(tmp) / "state"
            state_dir.mkdir()
            db = state_dir / "imp-state.sqlite3"
            db.write_text("", encoding="utf-8")
            os.environ["IMP_STATE_DIR"] = str(state_dir)
            with (
                patch(
                    "market_platform_foundation.intelligence.paper_forward_bridge."
                    "ftep_finviz_prospective_preflight.collect_ftep_campaign_status",
                    return_value={**_status_ok(), "us_equity_rth_open": False},
                ),
                patch(
                    "market_platform_foundation.intelligence.paper_forward_bridge."
                    "ftep_finviz_prospective_preflight.collect_ftep_integrity_checks",
                    return_value={"disposition": "PASS"},
                ),
                patch(
                    "market_platform_foundation.intelligence.paper_forward_bridge."
                    "ftep_finviz_prospective_preflight.load_governed_session_ids_from_evidence",
                    return_value=(["fts-A", "fts-B"], "evidence.jsonl"),
                ),
                patch(
                    "market_platform_foundation.intelligence.paper_forward_bridge."
                    "ftep_finviz_prospective_preflight.configured_token",
                    return_value="token",
                ),
                patch(
                    "market_platform_foundation.intelligence.paper_forward_bridge."
                    "ftep_finviz_prospective_preflight.canonical_primary_state_database",
                    return_value=db.resolve(),
                ),
                patch(
                    "market_platform_foundation.intelligence.paper_forward_bridge."
                    "ftep_finviz_prospective_preflight._private_credential_paths",
                    return_value={
                        "finviz_login_json_paths": ["/x/.private/finviz-login.json"],
                        "finviz_token_txt_paths": [],
                        "finviz_login_present": True,
                        "finviz_token_file_present": False,
                    },
                ),
            ):
                report = run_ftep_finviz_prospective_preflight(
                    ROOT,
                    options=FtepFinvizProspectivePreflightOptions(now_ns=T_RTH_CLOSED_NS),
                )
        self.assertEqual(report["disposition"], "SOFTWARE_READY_RTH_REQUIRED")
        self.assertIn("RTH_CLOSED", report["reason_codes"])
        self.assertIn("FINVIZ_LIVE_DISABLED", report["reason_codes"])

    def test_blocked_when_canonical_state_not_selected(self) -> None:
        with (
            patch(
                "market_platform_foundation.intelligence.paper_forward_bridge."
                "ftep_finviz_prospective_preflight.collect_ftep_campaign_status",
                return_value=_status_ok(),
            ),
            patch(
                "market_platform_foundation.intelligence.paper_forward_bridge."
                "ftep_finviz_prospective_preflight.collect_ftep_integrity_checks",
                return_value={"disposition": "PASS"},
            ),
            patch(
                "market_platform_foundation.intelligence.paper_forward_bridge."
                "ftep_finviz_prospective_preflight.load_governed_session_ids_from_evidence",
                return_value=(["fts-A", "fts-B"], "evidence.jsonl"),
            ),
            patch(
                "market_platform_foundation.intelligence.paper_forward_bridge."
                "ftep_finviz_prospective_preflight.configured_token",
                return_value="token",
            ),
            patch(
                "market_platform_foundation.intelligence.paper_forward_bridge."
                "ftep_finviz_prospective_preflight.canonical_primary_state_database",
                return_value=Path("/canonical/imp-state.sqlite3"),
            ),
            patch(
                "market_platform_foundation.intelligence.paper_forward_bridge."
                "ftep_finviz_prospective_preflight.persistence_enabled",
                return_value=False,
            ),
        ):
            report = run_ftep_finviz_prospective_preflight(
                ROOT,
                options=FtepFinvizProspectivePreflightOptions(now_ns=T_RTH_OPEN_NS),
            )
        self.assertEqual(report["disposition"], "BLOCKED")
        self.assertIn("CANONICAL_STATE_NOT_SELECTED", report["blockers"])

    def test_ready_at_rth_with_gates_enabled(self) -> None:
        os.environ["IMP_FINVIZ_LIVE"] = "1"
        os.environ["IMP_FTEP_PROSPECTIVE_CATALYST_INGRESS"] = "1"
        with tempfile.TemporaryDirectory() as tmp:
            state_dir = Path(tmp) / "state"
            state_dir.mkdir()
            db = state_dir / "imp-state.sqlite3"
            db.write_text("", encoding="utf-8")
            os.environ["IMP_STATE_DIR"] = str(state_dir)
            with (
                patch(
                    "market_platform_foundation.intelligence.paper_forward_bridge."
                    "ftep_finviz_prospective_preflight.collect_ftep_campaign_status",
                    return_value=_status_ok(),
                ),
                patch(
                    "market_platform_foundation.intelligence.paper_forward_bridge."
                    "ftep_finviz_prospective_preflight.collect_ftep_integrity_checks",
                    return_value={"disposition": "PASS"},
                ),
                patch(
                    "market_platform_foundation.intelligence.paper_forward_bridge."
                    "ftep_finviz_prospective_preflight.load_governed_session_ids_from_evidence",
                    return_value=(["fts-A", "fts-B"], "evidence.jsonl"),
                ),
                patch(
                    "market_platform_foundation.intelligence.paper_forward_bridge."
                    "ftep_finviz_prospective_preflight.configured_token",
                    return_value="token",
                ),
                patch(
                    "market_platform_foundation.intelligence.paper_forward_bridge."
                    "ftep_finviz_prospective_preflight.canonical_primary_state_database",
                    return_value=db.resolve(),
                ),
                patch(
                    "market_platform_foundation.intelligence.paper_forward_bridge."
                    "ftep_finviz_prospective_preflight._private_credential_paths",
                    return_value={
                        "finviz_login_json_paths": ["/x/.private/finviz-login.json"],
                        "finviz_token_txt_paths": ["/x/.private/finviz-token.txt"],
                        "finviz_login_present": True,
                        "finviz_token_file_present": True,
                    },
                ),
            ):
                report = run_ftep_finviz_prospective_preflight(
                    ROOT,
                    options=FtepFinvizProspectivePreflightOptions(now_ns=T_RTH_OPEN_NS),
                )
        self.assertEqual(report["disposition"], "READY")
        self.assertEqual(report["blockers"], [])
        self.assertIn("--live-ingress", report["live_watch_command"])
