from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.platform.bootstrap import collect_preflight, write_preflight_reports


class OperatorBootstrapTests(unittest.TestCase):
    def test_preflight_reports_project_checks_without_secret_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tools/ui1").mkdir(parents=True)
            (root / "tools/ui1/run_ui_api.py").write_text("# fixture", encoding="utf-8")
            (root / "ui").mkdir()
            (root / ".env").write_text(
                "FINVIZ_API_KEY=do-not-return-this\nIMP_PERSIST_STATE=1\n",
                encoding="utf-8",
            )

            report = collect_preflight(
                root,
                python_version=(3, 11),
                node_available=True,
                npm_available=True,
                git_available=True,
            )

            self.assertEqual(report["schema_version"], "operator-preflight/1.0")
            self.assertIn("checks", report)
            self.assertFalse(report["secrets_included"])
            serialized = str(report)
            self.assertNotIn("do-not-return-this", serialized)
            self.assertTrue(any(row["id"] == "python" for row in report["checks"]))

    def test_preflight_is_ready_only_when_required_project_checks_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tools/ui1").mkdir(parents=True)
            (root / "tools/ui1/run_ui_api.py").write_text("# fixture", encoding="utf-8")
            (root / "ui/node_modules").mkdir(parents=True)
            (root / ".venv/Scripts").mkdir(parents=True)
            (root / ".venv/Scripts/python.exe").write_text("# fixture", encoding="utf-8")

            report = collect_preflight(
                root,
                python_version=(3, 11),
                node_available=True,
                npm_available=True,
                git_available=True,
            )

            self.assertEqual(report["status"], "READY")
            self.assertTrue(all(row["status"] in {"PASS", "OPTIONAL"} for row in report["checks"]))

    def test_reports_are_persisted_in_machine_and_human_readable_forms(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = collect_preflight(
                root,
                python_version=(3, 11),
                node_available=True,
                npm_available=True,
                git_available=True,
            )

            write_preflight_reports(root, report)

            self.assertEqual(
                json.loads((root / ".local/preflight.json").read_text(encoding="utf-8")),
                report,
            )
            readable = (root / ".local/preflight.txt").read_text(encoding="utf-8")
            self.assertIn("Integrated Market Platform preflight", readable)
            self.assertIn("Status:", readable)


if __name__ == "__main__":
    unittest.main()
