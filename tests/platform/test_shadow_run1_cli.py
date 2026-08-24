import argparse
import contextlib
import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools" / "research"))

import run_shadow_run as cli


PINNED_HEAD = "a" * 40


def _write_json(path: Path, payload: dict) -> str:
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _offline_full_suites() -> list[str]:
    manifest = json.loads(
        (Path(__file__).resolve().parents[2] / "tools" / "validation_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    return [
        row["id"]
        for row in manifest["suites"]
        if row["classification"] == "offline" and "full" in row["tiers"]
    ]


def _validation_receipt(**overrides) -> dict:
    payload = {
        "schema_version": "1.0",
        "mode": "full",
        "status": "passed",
        "selected_suites": _offline_full_suites(),
        "failures": 0,
        "errors": 0,
        "interrupted": False,
        "not_run_suites": [],
        "started_at": "2026-08-24T14:00:00+00:00",
    }
    payload.update(overrides)
    return payload


def _runtime_health_receipt(**overrides) -> dict:
    payload = {
        "provider": "MOOMOO",
        "status": "READY",
        "ready_for_live_observational": True,
        "imp_moomoo_live": True,
        "opend": {"host": "127.0.0.1", "port": 11111, "reachable": True},
        "quote_context": {"ok": True},
        "verified_at": "2026-08-24T14:05:00+00:00",
    }
    payload.update(overrides)
    return payload


def _preflight_args(root: Path, **overrides) -> dict:
    validation_path = root / "full-validation.json"
    runtime_path = root / "runtime-health.json"
    validation_sha = _write_json(validation_path, _validation_receipt())
    runtime_sha = _write_json(runtime_path, _runtime_health_receipt())

    def fake_git(operation: str):
        return {"rev-parse": (PINNED_HEAD + "\n").encode(), "status": b""}[operation]

    args = {
        "instrument": "BIYA",
        "first_session": "2026-08-24",
        "holidays": "NONE",
        "early_closes": "NONE",
        "capture_id": "CAP-BIYA-SR1",
        "store_root": root / "shadow",
        "expected_head": PINNED_HEAD,
        "validation_evidence": validation_path,
        "validation_sha256": validation_sha,
        "runtime_health_evidence": runtime_path,
        "runtime_health_sha256": runtime_sha,
        "report": "",
        "_git_head": fake_git,
        "_environ": {
            "IMP_LIVE_OBSERVATIONAL": "1",
            "IMP_MOOMOO_LIVE": "1",
            "IMP_SHADOW_RECORDING": "0",
        },
    }
    args.update(overrides)
    return args


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


class CliPreflightTests(unittest.TestCase):
    def test_ready_report_is_local_only_and_hands_off_exact_open_argv(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            args = _preflight_args(root)
            with (
                mock.patch.object(cli, "build_manifest_body", side_effect=AssertionError("opened")),
                mock.patch.object(cli, "open_experiment_store", side_effect=AssertionError("opened")),
                mock.patch("socket.create_connection", side_effect=AssertionError("network")),
                mock.patch("urllib.request.urlopen", side_effect=AssertionError("network")),
            ):
                rc, report = cli.cmd_preflight(args)

            self.assertEqual(rc, 0)
            self.assertEqual(report["status"], "READY")
            self.assertEqual(report["protocol"], "SHADOW_RUN_1_BIYA_FROZEN")
            argv = report["opening_handoff"]["argv"]
            self.assertEqual(argv[1:4], ["tools/research/run_shadow_run.py", "open", "--instrument"])
            self.assertEqual(argv[4], "BIYA")
            self.assertIn("--first-session", argv)
            self.assertIn("--capture-id", argv)
            self.assertEqual(report["calendar"]["session_dates"][0], "2026-08-24")
            self.assertEqual(len(report["calendar"]["session_dates"]), 8)
            self.assertFalse(report["side_effects"]["network_calls"])
            self.assertFalse(report["side_effects"]["run_opened"])

    def test_blocks_dirty_or_unpinned_worktree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, git_result in (
                ("dirty", {"rev-parse": (PINNED_HEAD + "\n").encode(), "status": b"?? local.txt\n"}),
                ("unpinned", {"rev-parse": ("b" * 40 + "\n").encode(), "status": b""}),
            ):
                with self.subTest(name=name):
                    args = _preflight_args(root)
                    args["_git_head"] = lambda operation, rows=git_result: rows[operation]
                    rc, report = cli.cmd_preflight(args)
                    self.assertEqual(rc, 2)
                    self.assertEqual(report["status"], "BLOCKED")
                    self.assertIsNone(report["opening_handoff"])
                    self.assertFalse(next(c for c in report["checks"] if c["name"] == "worktree")["passed"])

    def test_blocks_invalid_or_unpinned_full_validation_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cases = (
                ("not-full", _validation_receipt(mode="changed"), None),
                ("incomplete", _validation_receipt(not_run_suites=["platform"]), None),
                ("wrong-digest", _validation_receipt(), "0" * 64),
            )
            for name, receipt, digest_override in cases:
                with self.subTest(name=name):
                    args = _preflight_args(root)
                    digest = _write_json(Path(args["validation_evidence"]), receipt)
                    args["validation_sha256"] = digest_override or digest
                    rc, report = cli.cmd_preflight(args)
                    self.assertEqual(rc, 2)
                    self.assertFalse(next(c for c in report["checks"] if c["name"] == "offline_full_validation")["passed"])

    def test_blocks_armed_recording_or_execution_configuration(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, environment in (
                ("recording", {"IMP_LIVE_OBSERVATIONAL": "1", "IMP_MOOMOO_LIVE": "1", "IMP_SHADOW_RECORDING": "1"}),
                ("execution", {"IMP_LIVE_OBSERVATIONAL": "1", "IMP_MOOMOO_LIVE": "1", "IMP_LIVE_EXECUTION": "1"}),
            ):
                with self.subTest(name=name):
                    rc, report = cli.cmd_preflight(_preflight_args(root, _environ=environment))
                    self.assertEqual(rc, 2)
                    self.assertFalse(next(c for c in report["checks"] if c["name"] == "runtime_configuration")["passed"])

    def test_blocks_unhealthy_or_nonlocal_runtime_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cases = (
                ("unhealthy", _runtime_health_receipt(status="PORT_UNREACHABLE", ready_for_live_observational=False)),
                ("nonlocal", _runtime_health_receipt(opend={"host": "10.0.0.2", "port": 11111, "reachable": True})),
            )
            for name, receipt in cases:
                with self.subTest(name=name):
                    args = _preflight_args(root)
                    digest = _write_json(Path(args["runtime_health_evidence"]), receipt)
                    args["runtime_health_sha256"] = digest
                    rc, report = cli.cmd_preflight(args)
                    self.assertEqual(rc, 2)
                    self.assertFalse(next(c for c in report["checks"] if c["name"] == "observational_runtime_health")["passed"])

    def test_blocks_ineligible_or_ambiguous_calendar(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, changes in (
                ("weekend", {"first_session": "2026-08-23"}),
                ("holiday-first", {"holidays": "2026-08-24"}),
                ("overlap", {"holidays": "2026-09-07", "early_closes": "2026-09-07"}),
                ("implicit", {"holidays": ""}),
            ):
                with self.subTest(name=name):
                    rc, report = cli.cmd_preflight(_preflight_args(root, **changes))
                    self.assertEqual(rc, 2)
                    self.assertFalse(next(c for c in report["checks"] if c["name"] == "session_calendar")["passed"])

    def test_main_writes_identical_report_and_never_opens(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            args = _preflight_args(root)
            output = root / "preflight.json"
            argv = [
                "preflight", "--instrument", "BIYA", "--first-session", "2026-08-24",
                "--holidays", "NONE", "--early-closes", "NONE",
                "--capture-id", "CAP-BIYA-SR1", "--store-root", str(root / "shadow"),
                "--expected-head", PINNED_HEAD,
                "--validation-evidence", str(args["validation_evidence"]),
                "--validation-sha256", args["validation_sha256"],
                "--runtime-health-evidence", str(args["runtime_health_evidence"]),
                "--runtime-health-sha256", args["runtime_health_sha256"],
                "--report", str(output),
            ]
            fake_git = args["_git_head"]
            with mock.patch.object(cli, "_git", side_effect=lambda op=None: fake_git(op)):
                with contextlib.redirect_stdout(io.StringIO()) as stdout:
                    rc = cli.main(argv)
            printed = json.loads(stdout.getvalue())
            self.assertEqual(rc, 2)  # process environment is intentionally not observationally armed
            self.assertEqual(printed, json.loads(output.read_text(encoding="utf-8")))
            self.assertEqual(printed["status"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
