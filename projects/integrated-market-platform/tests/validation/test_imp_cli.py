"""Tests for the canonical IMP developer command router."""

from __future__ import annotations

import unittest
import importlib.util
import json
import os
import tempfile
from unittest.mock import patch
from pathlib import Path

try:
    from tools.imp import (
        build_closure_report,
        build_parser,
        classify_changed_area,
        _npm_executable,
        _run,
        summarize_telemetry,
    )
except ModuleNotFoundError as exc:
    IMPORT_ERROR = exc
else:
    IMPORT_ERROR = None


class ImpCliTests(unittest.TestCase):
    def setUp(self) -> None:
        if IMPORT_ERROR is not None:
            self.fail(f"IMP command router is missing: {IMPORT_ERROR}")

    def test_parser_exposes_canonical_validation_and_test_commands(self) -> None:
        affected = build_parser().parse_args(["test", "affected", "--workers", "4"])
        focused = build_parser().parse_args(
            ["test", "focused", "tests/validation/test_imp_cli.py::ImpCliTests::test_parser_exposes_canonical_validation_and_test_commands"]
        )
        fast = build_parser().parse_args(["validate", "fast"])
        changed = build_parser().parse_args(["validate", "changed", "--json", "result.json"])

        self.assertEqual((affected.group, affected.action, affected.workers), ("test", "affected", 4))
        self.assertEqual((focused.group, focused.action), ("test", "focused"))
        self.assertEqual(fast.action, "fast")
        self.assertEqual(changed.action, "changed")
        self.assertIn(_npm_executable(), ("npm", "npm.cmd"))

    def test_changed_area_classification_is_deterministic_and_non_authoritative(self) -> None:
        self.assertEqual(classify_changed_area("src/market_platform_foundation/paper/ledger.py"), "paper")
        self.assertEqual(classify_changed_area("ui/src/App.tsx"), "ui")
        self.assertEqual(classify_changed_area("docs/engineering/VALIDATION.md"), "documentation")
        self.assertEqual(classify_changed_area("tools/validate.py"), "developer-tooling")
        self.assertEqual(classify_changed_area("manifests/developer-operating-system.json"), "developer-tooling")
        self.assertEqual(classify_changed_area("fixtures/sample.json"), "fixtures")
        self.assertEqual(classify_changed_area("unknown.txt"), "other")

    def test_closure_report_preserves_baseline_failures_and_risk_status(self) -> None:
        report = build_closure_report(
            repository_root=Path("C:/repo"),
            changed_files=("tools/imp.py", "docs/engineering/VALIDATION.md"),
            validation_evidence={"full": {"status": "passed", "wall_seconds": 12.5}},
            baseline_failures=({"suite": "platform", "count": 2},),
            documentation_changes=("docs/engineering/VALIDATION.md",),
            risk_status="requires_safety_review",
        )

        self.assertEqual(report["schema_version"], "1.0")
        self.assertEqual(report["report_type"], "imp_closure")
        self.assertEqual(report["risk"]["status"], "requires_safety_review")
        self.assertEqual(report["baseline"]["failures"][0]["suite"], "platform")
        self.assertEqual(report["changed_areas"], ["developer-tooling", "documentation"])
        self.assertEqual(report["documentation_changes"], ["docs/engineering/VALIDATION.md"])
        self.assertEqual(report["validation"]["full"]["status"], "passed")

    def test_shell_policy_blocks_destructive_and_protected_branch_commands(self) -> None:
        path = Path(__file__).resolve().parents[2] / ".cursor" / "hooks" / "policy.py"
        spec = importlib.util.spec_from_file_location("imp_hook_policy", path)
        self.assertIsNotNone(spec)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        self.assertEqual(module.decision_for("git reset --hard HEAD"), "deny")
        self.assertEqual(module.decision_for("git push origin main"), "deny")
        self.assertEqual(module.decision_for("git push origin HEAD:main"), "deny")
        self.assertEqual(module.decision_for("python tools/imp.py test focused x"), "allow")

    def test_telemetry_summary_measures_repeats_validation_and_ci(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            telemetry = Path(temporary) / "events.jsonl"
            telemetry.write_text(
                "\n".join(
                    json.dumps(
                        {
                            "event_type": "developer_command",
                            "command": command,
                            "wall_seconds": seconds,
                            "ci": ci,
                        }
                    )
                    for command, seconds, ci in (
                        ("validate changed", 2.0, False),
                        ("validate changed", 3.0, True),
                        ("lint", 1.0, False),
                    )
                )
                + "\n",
                encoding="utf-8",
            )
            previous = os.environ.get("IMP_TELEMETRY_PATH")
            os.environ["IMP_TELEMETRY_PATH"] = str(telemetry)
            try:
                summary = summarize_telemetry(Path(temporary))
            finally:
                if previous is None:
                    os.environ.pop("IMP_TELEMETRY_PATH", None)
                else:
                    os.environ["IMP_TELEMETRY_PATH"] = previous

        self.assertEqual(summary["events"], 3)
        self.assertEqual(summary["redundant_command_events"], 1)
        self.assertEqual(summary["validation_wall_seconds"], 5.0)
        self.assertEqual(summary["ci_wall_seconds"], 3.0)

    def test_validation_runner_can_stream_child_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            completed = type("Completed", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            with patch("tools.imp.subprocess.run", return_value=completed) as run:
                result = _run(root, label="validate changed", command=["validation"], stream_output=True)

            self.assertEqual(result["exit_code"], 0)
            self.assertNotIn("capture_output", run.call_args.kwargs)


if __name__ == "__main__":
    unittest.main()
