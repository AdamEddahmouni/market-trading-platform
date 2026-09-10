"""Tests for portable IMP environment discovery and bootstrap helpers."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    from tools import environment
except ModuleNotFoundError as exc:
    IMPORT_ERROR = exc
else:
    IMPORT_ERROR = None


class EnvironmentResolutionTests(unittest.TestCase):
    def setUp(self) -> None:
        if IMPORT_ERROR is not None:
            self.fail(f"environment helpers are missing: {IMPORT_ERROR}")

    def test_python_supported_requires_311(self) -> None:
        self.assertTrue(environment.python_supported("3.11.9"))
        self.assertFalse(environment.python_supported("3.10.11"))

    def test_imp_project_root_prefers_platform_anchor(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / ".git").mkdir()
            project = root / "projects" / "integrated-market-platform"
            project.mkdir(parents=True)
            (project / "phase0-dependency-lock.json").write_text("{}", encoding="utf-8")
            (project / "tools").mkdir()
            self.assertEqual(environment.imp_project_root(project / "tools"), project.resolve())

    def test_resolve_python_honors_imp_python_override(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "phase0-dependency-lock.json").write_text("{}", encoding="utf-8")
            fake = root / "python311.exe"
            fake.write_text("", encoding="utf-8")
            previous = os.environ.get(environment.IMP_PYTHON_ENV)
            os.environ[environment.IMP_PYTHON_ENV] = str(fake)
            try:
                with patch.object(environment, "_python_version_from_executable", return_value="3.11.0"):
                    resolution = environment.resolve_python(root)
            finally:
                if previous is None:
                    os.environ.pop(environment.IMP_PYTHON_ENV, None)
                else:
                    os.environ[environment.IMP_PYTHON_ENV] = previous
            self.assertEqual(resolution.executable, fake.resolve())
            self.assertEqual(resolution.source, environment.IMP_PYTHON_ENV)

    def test_link_local_venv_refuses_real_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "phase0-dependency-lock.json").write_text("{}", encoding="utf-8")
            canonical = root / "canonical"
            canonical.mkdir()
            if os.name == "nt":
                (canonical / "Scripts").mkdir()
                python_exe = canonical / "Scripts" / "python.exe"
                python_exe.write_text("", encoding="utf-8")
            else:
                (canonical / "bin").mkdir()
                python_exe = canonical / "bin" / "python"
                python_exe.write_text("", encoding="utf-8")
            real_venv = root / environment.VENV_DIRNAME
            real_venv.mkdir()
            with patch.object(environment, "resolve_python") as resolve:
                resolve.return_value = environment.PythonResolution(
                    executable=python_exe,
                    source="shared_worktree_venv",
                    supported=True,
                    environment_root=canonical,
                )
                with self.assertRaisesRegex(RuntimeError, "real directory"):
                    environment.link_local_venv(root)

    def test_build_environment_report_includes_next_commands(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "phase0-dependency-lock.json").write_text("{}", encoding="utf-8")
            fake = root / "python311.exe"
            fake.write_text("", encoding="utf-8")
            with patch.object(environment, "resolve_python") as resolve:
                resolve.return_value = environment.PythonResolution(
                    executable=fake,
                    source="shared_worktree_venv",
                    supported=True,
                    environment_root=root / "venv",
                )
                with patch.object(environment, "_python_version_from_executable", return_value="3.11.0"):
                    with patch.object(environment, "timezone_ready", return_value=(True, "ok")):
                        report = environment.build_environment_report(root)
            self.assertIn("next_commands", report)
            self.assertTrue(report["next_commands"])


if __name__ == "__main__":
    unittest.main()
