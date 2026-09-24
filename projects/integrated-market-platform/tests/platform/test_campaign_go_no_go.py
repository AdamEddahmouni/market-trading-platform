"""Fail-closed GO/NO-GO for the next prospective RTH campaign. Not empirical."""

from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from tools.platform.campaign_go_no_go import (
    build_freeze_document,
    canonical_freeze_sha256,
    evaluate_campaign_go_no_go,
    next_trading_session,
)
from tools.platform.campaign_supervisor import main as supervisor_main

ET = ZoneInfo("America/New_York")
RUNTIME = "a" * 40
TREE = "b" * 40


def _freeze(session_iso: str = "2026-09-25") -> dict:
    year, month, day = (int(p) for p in session_iso.split("-"))
    from datetime import date

    doc = build_freeze_document(
        session=date(year, month, day),
        runtime_sha=RUNTIME,
        runtime_tree_sha=TREE,
        source_main=RUNTIME,
        prior_campaign_id="RTH-OBS-NEWS-20260924",
        prior_runtime_sha="1cbc8b0551179e1724033ee0036fb3366174daca",
        prior_classification="OPERATIONAL_ONLY",
    )
    assert doc["freeze_sha256"] == canonical_freeze_sha256(doc)
    return doc


def _eval(doc: dict, *, now: str, state: Path, **kwargs):
    path = state / "freeze.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    env = {
        "IMP_FINVIZ_LIVE": "1",
        "IMP_FTEP_PROSPECTIVE_CATALYST_INGRESS": "1",
    }
    env.update(kwargs.pop("environ", {}))
    return evaluate_campaign_go_no_go(
        freeze_path=path,
        root=Path(__file__).resolve().parents[2],
        state_dir=state / "rth-campaign-20260925",
        now_et=datetime.fromisoformat(now).replace(tzinfo=ET),
        environ=env,
        git_head=kwargs.pop("git_head", RUNTIME),
        git_tree=kwargs.pop("git_tree", TREE),
        worktree_dirty=kwargs.pop("worktree_dirty", False),
        port_open=kwargs.pop("port_open", False),
        credential_available=kwargs.pop("credential_available", True),
        credential_source="environment",
        probe_network=False,
        **kwargs,
    )


class CampaignGoNoGoTests(unittest.TestCase):
    def test_next_session_after_sep24_is_sep25(self) -> None:
        from datetime import date

        self.assertEqual(next_trading_session(date(2026, 9, 24)).isoformat(), "2026-09-25")
        self.assertEqual(next_trading_session(date(2026, 9, 25)).isoformat(), "2026-09-28")

    def test_ready_before_open(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = _eval(_freeze(), now="2026-09-25T09:00:00", state=Path(tmp))
        self.assertEqual(report["disposition"], "READY_FOR_PRE_RTH_ARM")
        self.assertTrue(report["arm_allowed"])
        self.assertEqual(report["blockers"], [])

    def test_not_yet_in_window_does_not_arm(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = _eval(_freeze(), now="2026-09-24T20:00:00", state=Path(tmp))
        self.assertEqual(report["disposition"], "NOT_YET_IN_WINDOW")
        self.assertFalse(report["arm_allowed"])

    def _blocked(self, mutate, needle: str) -> None:
        doc = _freeze()
        mutate(doc)
        if needle != "FREEZE_HASH_MISMATCH":
            doc["freeze_sha256"] = canonical_freeze_sha256(doc)
        with tempfile.TemporaryDirectory() as tmp:
            report = _eval(doc, now="2026-09-25T09:00:00", state=Path(tmp))
        self.assertEqual(report["disposition"], "BLOCKED", report["blockers"])
        self.assertIn(needle, report["blockers"])
        self.assertFalse(report["arm_allowed"])

    def test_failure_injection(self) -> None:
        cases = [
            (lambda d: d.update(runtime_sha="c" * 40), "RUNTIME_SHA_MISMATCH"),
            (lambda d: d.update(runtime_tree_sha="d" * 40), "RUNTIME_TREE_MISMATCH"),
            (lambda d: d.update(campaign_id="RTH-OBS-NEWS-20260924"), "CAMPAIGN_ID_MISMATCH"),
            (lambda d: d.update(session_date="2026-09-26"), "SESSION_DATE_NOT_TRADING_DAY"),
            (lambda d: d.update(freeze_sha256="0" * 64), "FREEZE_HASH_MISMATCH"),
            (lambda d: d.update(live_execution="ON"), "FREEZE_LIVE_NOT_OFF"),
            (lambda d: d.update(item9_calibration_run="ALLOWED"), "CALIBRATION_UNEXPECTEDLY_ENABLED"),
            (lambda d: d.update(full30="RUN"), "FULL30_UNEXPECTEDLY_ENABLED"),
            (lambda d: d.update(rehearsal_namespace=d["evidence_namespace"]), "REHEARSAL_EMPIRICAL_PATH_COLLISION"),
            (lambda d: d.update(campaign_state="ARMED"), "FREEZE_NOT_FROZEN_NOT_ARMED"),
        ]
        for mutate, needle in cases:
            with self.subTest(needle=needle):
                self._blocked(mutate, needle)

    def test_dirty_missing_credential_and_port(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp)
            dirty = _eval(_freeze(), now="2026-09-25T09:00:00", state=state, worktree_dirty=True)
            self.assertIn("DIRTY_WORKTREE", dirty["blockers"])
            missing = _eval(
                _freeze(),
                now="2026-09-25T09:00:00",
                state=state,
                credential_available=False,
            )
            self.assertIn("PROVIDER_CREDENTIAL_ABSENT", missing["blockers"])
            disabled = _eval(
                _freeze(),
                now="2026-09-25T09:00:00",
                state=state,
                environ={"IMP_FINVIZ_LIVE": "0", "IMP_FTEP_PROSPECTIVE_CATALYST_INGRESS": "1"},
            )
            self.assertIn("PROVIDER_DISABLED", disabled["blockers"])
            port = _eval(
                _freeze(),
                now="2026-09-25T09:00:00",
                state=state,
                port_open=True,
                api_identity_sha="e" * 40,
            )
            self.assertIn("API_RUNTIME_MISMATCH", port["blockers"])

    def test_git_status_failure_blocks_arm(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch("tools.platform.campaign_go_no_go._git", return_value=None):
                report = _eval(
                    _freeze(), now="2026-09-25T09:00:00", state=Path(tmp),
                    worktree_dirty=None,
                )
        self.assertIn("WORKTREE_STATUS_UNAVAILABLE", report["blockers"])
        self.assertFalse(report["arm_allowed"])

    def test_missing_freeze_and_late_arm(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = evaluate_campaign_go_no_go(
                freeze_path=Path(tmp) / "nope.json",
                root=Path(tmp),
                state_dir=Path(tmp) / "rth-campaign-20260925",
                now_et=datetime(2026, 9, 25, 9, 0, tzinfo=ET),
                probe_network=False,
                credential_available=True,
                git_head=RUNTIME,
                git_tree=TREE,
                worktree_dirty=False,
                port_open=False,
            )
            self.assertIn("FREEZE_MISSING_OR_UNREADABLE", missing["blockers"])
            late = _eval(_freeze(), now="2026-09-25T09:30:00", state=Path(tmp))
            self.assertEqual(late["disposition"], "MISSED_WINDOW")
            self.assertFalse(late["arm_allowed"])

    def test_already_armed_terminal_and_foreign(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp)
            campaign = state / "rth-campaign-20260925"
            sup = campaign / "campaign-supervision"
            sup.mkdir(parents=True)
            (sup / "ownership.json").write_text(
                json.dumps({"campaign_id": "RTH-OBS-NEWS-20260925", "arm_status": "ARMED_RUNNING"}),
                encoding="utf-8",
            )
            (sup / "heartbeat.json").write_text(
                json.dumps({"last_heartbeat_utc": "2026-09-25T13:00:00Z"}),
                encoding="utf-8",
            )
            armed = _eval(_freeze(), now="2026-09-25T09:00:00", state=state)
            self.assertEqual(armed["disposition"], "ALREADY_ARMED")
            (sup / "ownership.json").write_text(
                json.dumps({"campaign_id": "RTH-OBS-NEWS-20260923", "arm_status": "NOT_ARMED"}),
                encoding="utf-8",
            )
            foreign = _eval(_freeze(), now="2026-09-25T09:00:00", state=state)
            self.assertIn("FOREIGN_CAMPAIGN_STATE", foreign["blockers"])
            (sup / "ownership.json").write_text(
                json.dumps({"campaign_id": "RTH-OBS-NEWS-20260925", "arm_status": "RTH_CLOSE_SHUTDOWN"}),
                encoding="utf-8",
            )
            terminal = _eval(_freeze(), now="2026-09-25T09:00:00", state=state)
            self.assertEqual(terminal["disposition"], "TERMINAL")

    def test_unreadable_or_unknown_ownership_blocks_arm(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp)
            sup = state / "rth-campaign-20260925" / "campaign-supervision"
            sup.mkdir(parents=True)
            path = sup / "ownership.json"
            path.write_text("{broken", encoding="utf-8")
            corrupt = _eval(_freeze(), now="2026-09-25T09:00:00", state=state)
            self.assertIn("OWNERSHIP_UNREADABLE", corrupt["blockers"])
            self.assertFalse(corrupt["arm_allowed"])
            path.write_text(
                json.dumps({"campaign_id": "RTH-OBS-NEWS-20260925", "arm_status": "UNKNOWN"}),
                encoding="utf-8",
            )
            unknown = _eval(_freeze(), now="2026-09-25T09:00:00", state=state)
            self.assertIn("ARM_STATUS_UNKNOWN", unknown["blockers"])
            self.assertFalse(unknown["arm_allowed"])
            path.write_text(json.dumps({"arm_status": "NOT_ARMED"}), encoding="utf-8")
            missing_id = _eval(_freeze(), now="2026-09-25T09:00:00", state=state)
            self.assertIn("FOREIGN_CAMPAIGN_STATE", missing_id["blockers"])
            self.assertFalse(missing_id["arm_allowed"])

    def test_live_and_calibration_env_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            live = _eval(
                _freeze(),
                now="2026-09-25T09:00:00",
                state=Path(tmp),
                environ={
                    "IMP_FINVIZ_LIVE": "1",
                    "IMP_FTEP_PROSPECTIVE_CATALYST_INGRESS": "1",
                    "IMP_LIVE_EXECUTION": "1",
                    "ITEM9_CALIBRATION_RUN": "1",
                },
            )
        self.assertIn("LIVE_UNEXPECTEDLY_ON", live["blockers"])
        self.assertIn("CALIBRATION_UNEXPECTEDLY_ENABLED", live["blockers"])
        self.assertFalse(live["arm_allowed"])

    def test_arm_refuses_when_not_in_window(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp)
            freeze = state / "freeze.json"
            freeze.write_text(json.dumps(_freeze()), encoding="utf-8")
            code = supervisor_main(
                [
                    "arm",
                    "--state-dir",
                    str(state / "rth-campaign-20260925"),
                    "--campaign-id",
                    "RTH-OBS-NEWS-20260925",
                    "--observation-window-id",
                    "RTH-OBS-NEWS-20260925-A",
                    "--freeze",
                    str(freeze),
                    "--skip-environment-preflight",
                ]
            )
            self.assertEqual(code, 2)
            self.assertFalse((state / "rth-campaign-20260925" / "campaign-supervision" / "ownership.json").exists())

    def test_arm_refuses_mismatched_freeze_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp)
            freeze = state / "freeze.json"
            freeze.write_text(json.dumps(_freeze()), encoding="utf-8")
            gate = {
                "arm_allowed": True,
                "runtime_sha": RUNTIME,
                "campaign_id": "RTH-OBS-NEWS-20260925",
                "observation_window_id": "RTH-OBS-NEWS-20260925-A",
            }
            for campaign_id, window_id in (
                ("RTH-OBS-NEWS-20260924", "RTH-OBS-NEWS-20260925-A"),
                ("RTH-OBS-NEWS-20260925", "RTH-OBS-NEWS-20260925-B"),
            ):
                with self.subTest(campaign_id=campaign_id, window_id=window_id):
                    with patch("tools.platform.campaign_go_no_go.evaluate_campaign_go_no_go", return_value=gate.copy()):
                        code = supervisor_main([
                            "arm", "--state-dir", str(state / "rth-campaign-20260925"),
                            "--campaign-id", campaign_id,
                            "--observation-window-id", window_id,
                            "--freeze", str(freeze), "--skip-environment-preflight",
                        ])
                    self.assertEqual(code, 2)
                    self.assertFalse((state / "rth-campaign-20260925" / "campaign-supervision" / "ownership.json").exists())


if __name__ == "__main__":
    unittest.main()
