"""Tests for CI job-slice classification. Tooling only; no product runtime."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

try:
    from tools.ci_job_selector import (
        load_paths,
        main,
        normalize_changed_path,
        select_ci_jobs,
        write_github_output,
    )
    from tools.imp import build_parser
except ModuleNotFoundError as exc:
    IMPORT_ERROR = exc
else:
    IMPORT_ERROR = None

IMP_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = IMP_ROOT.parent.parent


class CiJobSelectorTests(unittest.TestCase):
    def setUp(self) -> None:
        if IMPORT_ERROR is not None:
            self.fail(f"ci_job_selector is missing: {IMPORT_ERROR}")

    def test_normalizes_monorepo_prefix(self) -> None:
        self.assertEqual(
            normalize_changed_path("projects/integrated-market-platform/ui/src/App.tsx"),
            "ui/src/App.tsx",
        )
        self.assertEqual(
            normalize_changed_path(".github/workflows/imp-validate.yml"),
            ".github/workflows/imp-validate.yml",
        )

    def test_docs_only_skips_ui_and_replay_fixture(self) -> None:
        selection = select_ci_jobs(("docs/engineering/VALIDATION.md", "README.md"))
        self.assertFalse(selection["run_ui"])
        self.assertTrue(selection["run_docs"])
        self.assertFalse(selection["checkout_replay_fixture"])
        self.assertTrue(selection["run_python_fast"])
        self.assertTrue(selection["run_python_changed"])

    def test_ui_source_runs_ui_but_not_replay_fixture(self) -> None:
        selection = select_ci_jobs(("ui/src/App.tsx",))
        self.assertTrue(selection["run_ui"])
        self.assertFalse(selection["run_docs"])
        self.assertFalse(selection["checkout_replay_fixture"])

    def test_ui_agents_markdown_is_docs_not_frontend_runtime(self) -> None:
        selection = select_ci_jobs(("ui/AGENTS.md",))
        self.assertFalse(selection["run_ui"])
        self.assertTrue(selection["run_docs"])

    def test_backend_error_taxonomy_skips_ui_docs_and_fixture(self) -> None:
        selection = select_ci_jobs(
            (
                "src/market_platform_foundation/ui_api/errors.py",
                "tools/platform/control_service.py",
            )
        )
        self.assertFalse(selection["run_ui"])
        self.assertFalse(selection["run_docs"])
        self.assertFalse(selection["checkout_replay_fixture"])

    def test_formulas_paths_require_replay_fixture(self) -> None:
        selection = select_ci_jobs(("tests/formulas/test_heuristic_pin_drift.py",))
        self.assertTrue(selection["checkout_replay_fixture"])
        self.assertFalse(selection["run_ui"])

    def test_donor_bridge_paths_require_replay_fixture(self) -> None:
        selection = select_ci_jobs(
            (
                "src/market_platform_foundation/donor_bridge/cross_lane_adapter.py",
                "tests/donor_bridge/test_ss_p5.py",
            )
        )
        self.assertTrue(selection["checkout_replay_fixture"])
        self.assertFalse(selection["run_ui"])
        self.assertFalse(selection["run_docs"])

    def test_imp_validate_workflow_forces_ui(self) -> None:
        selection = select_ci_jobs((".github/workflows/imp-validate.yml",))
        self.assertTrue(selection["run_ui"])

    def test_imp_python_workflow_forces_replay_fixture(self) -> None:
        selection = select_ci_jobs((".github/workflows/imp-python.yml",))
        self.assertTrue(selection["checkout_replay_fixture"])

    def test_empty_or_unreadable_paths_fail_closed(self) -> None:
        empty = select_ci_jobs(())
        unread = select_ci_jobs((), paths_readable=False)
        always = select_ci_jobs(("docs/README.md",), always_run=True)
        for selection in (empty, unread, always):
            self.assertTrue(selection["run_ui"])
            self.assertTrue(selection["run_docs"])
            self.assertTrue(selection["checkout_replay_fixture"])

    def test_github_output_writes_lowercase_booleans(self) -> None:
        selection = select_ci_jobs(("docs/engineering/VALIDATION.md",))
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "github-output"
            write_github_output(selection, target)
            text = target.read_text(encoding="utf-8")
        self.assertIn("run_ui=false\n", text)
        self.assertIn("run_docs=true\n", text)
        self.assertIn("checkout_replay_fixture=false\n", text)

    def test_cli_reads_paths_file_and_writes_json(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths_file = root / "changed.txt"
            paths_file.write_text(
                "projects/integrated-market-platform/docs/engineering/VALIDATION.md\n",
                encoding="utf-8",
            )
            json_path = root / "selection.json"
            github_output = root / "output"
            exit_code = main(
                [
                    "--paths-file",
                    str(paths_file),
                    "--json",
                    str(json_path),
                    "--github-output-path",
                    str(github_output),
                    "--quiet",
                ]
            )
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            github_text = github_output.read_text(encoding="utf-8")
        self.assertEqual(exit_code, 0)
        self.assertFalse(payload["run_ui"])
        self.assertTrue(payload["run_docs"])
        self.assertIn("run_ui=false", github_text)

    def test_imp_router_exposes_ci_jobs(self) -> None:
        parsed = build_parser().parse_args(["ci", "jobs", "--always-run"])
        self.assertEqual((parsed.group, parsed.action, parsed.always_run), ("ci", "jobs", True))

    def test_parent_workflows_gate_expensive_steps(self) -> None:
        validate_path = REPO_ROOT / ".github" / "workflows" / "imp-validate.yml"
        python_path = REPO_ROOT / ".github" / "workflows" / "imp-python.yml"
        if not validate_path.is_file() or not python_path.is_file():
            self.skipTest("parent monorepo workflows are not in this checkout")
        validate = validate_path.read_text(encoding="utf-8")
        python_workflow = python_path.read_text(encoding="utf-8")
        self.assertIn("tools/ci_job_selector.py", validate)
        self.assertIn("steps.ci_slices.outputs.run_ui == 'true'", validate)
        self.assertIn("steps.ci_slices.outputs.run_docs == 'true'", validate)
        self.assertIn("--always-run", validate)
        self.assertIn('!= "pull_request"', validate)
        self.assertIn("Checkout repository (shallow)", python_workflow)
        self.assertIn("checkout_replay_fixture == 'true'", python_workflow)
        self.assertIn(
            "inputs.mode == 'changed' && steps.ci_slices.outputs.checkout_replay_fixture == 'true'",
            python_workflow,
        )
        self.assertNotIn("bash <(curl https://raw.githubusercontent.com/rhysd/actionlint", validate)

    def test_load_paths_skips_blanks_and_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "paths.txt"
            path.write_text(
                "\nui/src/App.tsx\nprojects/integrated-market-platform/ui/src/App.tsx\n# ignore\n",
                encoding="utf-8",
            )
            self.assertEqual(load_paths(paths_file=path), ("ui/src/App.tsx",))


if __name__ == "__main__":
    unittest.main()
