from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from tools.platform.local_launcher import (
    LauncherError,
    PlatformController,
    build_backend_environment,
    select_backend_python,
)


def always_usable(_python: Path) -> bool:
    return True


class FakeSystem:
    def __init__(self) -> None:
        self.next_pid = 1000
        self.spawn_calls: list[dict[str, object]] = []
        self.command_lines: dict[int, str] = {}
        self.terminated: list[int] = []
        self.opened: list[str] = []
        self.ready: dict[str, bool] = {}
        self.open_ports: set[int] = set()

    def which(self, executable: str) -> str | None:
        if executable == "npm.cmd":
            return r"C:\Program Files\nodejs\npm.cmd"
        return None

    def port_is_open(self, host: str, port: int) -> bool:
        return int(port) in self.open_ports

    def spawn(self, argv, *, cwd: Path, env, log_path: Path) -> int:  # type: ignore[no-untyped-def]
        pid = self.next_pid
        self.next_pid += 1
        command_line = " ".join(str(item) for item in argv)
        self.command_lines[pid] = command_line
        self.spawn_calls.append(
            {
                "argv": list(argv),
                "cwd": cwd,
                "env": dict(env),
                "log_path": log_path,
                "pid": pid,
            }
        )
        return pid

    def command_line(self, pid: int) -> str | None:
        return self.command_lines.get(pid)

    def terminate_tree(self, pid: int) -> bool:
        self.terminated.append(pid)
        self.command_lines.pop(pid, None)
        return True

    def url_ready(self, url: str, timeout_seconds: float = 1.0) -> bool:
        return self.ready.get(url, False)

    def open_browser(self, url: str) -> bool:
        self.opened.append(url)
        return True

    def sleep(self, seconds: float) -> None:
        return None

    def process_alive(self, pid: int) -> bool:
        return pid in self.command_lines


def make_root(base: Path) -> Path:
    root = base / "repo"
    for relative in (
        ".venv/Scripts/python.exe",
        "tools/ui1/run_ui_api.py",
        "ui/node_modules/.ready",
    ):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture", encoding="utf-8")
    return root


class LocalLauncherTests(unittest.TestCase):
    def test_backend_python_precedence_is_override_then_repo_not_moomoo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = make_root(base)
            profile = base / "profile"
            moomoo = profile / "moomoo-api-test/.venv/Scripts/python.exe"
            override = base / "custom/python.exe"
            moomoo.parent.mkdir(parents=True)
            override.parent.mkdir(parents=True)
            moomoo.write_text("fixture", encoding="utf-8")
            override.write_text("fixture", encoding="utf-8")

            self.assertEqual(select_backend_python(root, {"IMP_PLATFORM_BACKEND_PYTHON": str(override)}, profile), override)
            self.assertEqual(select_backend_python(root, {}, profile), root / ".venv/Scripts/python.exe")
            (root / ".venv/Scripts/python.exe").unlink()
            with self.assertRaises(LauncherError):
                select_backend_python(root, {}, profile)

    def test_backend_environment_defaults_to_observational_and_paper_only(self) -> None:
        env = build_backend_environment({"IMP_MOOMOO_LIVE": "0", "EXISTING": "yes"})

        self.assertEqual(env["IMP_LIVE_OBSERVATIONAL"], "1")
        self.assertEqual(env["IMP_MOOMOO_LIVE"], "0")
        self.assertEqual(env["IMP_FINVIZ_LIVE"], "1")
        self.assertEqual(env["IMP_PAPER_EXECUTION"], "1")
        self.assertEqual(env["IMP_LIVE_INTERNAL_SIMULATION"], "1")
        self.assertEqual(env["IMP_PERSIST_STATE"], "1")
        self.assertEqual(env["PYTHONUNBUFFERED"], "1")
        self.assertNotIn("IMP_LIVE_EXECUTION", env)
        self.assertNotIn("IMP_BROKER_LIVE_EXECUTION", env)

    def test_start_is_idempotent_when_owned_services_are_healthy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = make_root(Path(tmp))
            fake = FakeSystem()
            fake.ready = {
                "http://127.0.0.1:8766/context": True,
                "http://127.0.0.1:5173/": True,
            }
            controller = PlatformController(
                root=root,
                system=fake,
                environ={"USERPROFILE": str(Path(tmp) / "profile")},
                python_runtime_probe=always_usable,
            )

            self.assertEqual(controller.start(open_browser=False), 0)
            self.assertEqual(len(fake.spawn_calls), 3)
            self.assertEqual(controller.start(open_browser=True), 0)

            self.assertEqual(len(fake.spawn_calls), 3)
            self.assertEqual(fake.opened, ["http://127.0.0.1:5173/"])

    def test_failed_readiness_rolls_back_every_process_started(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = make_root(Path(tmp))
            fake = FakeSystem()
            fake.ready = {"http://127.0.0.1:8766/context": True}
            controller = PlatformController(
                root=root,
                system=fake,
                environ={"USERPROFILE": str(Path(tmp) / "profile")},
                readiness_attempts=1,
                python_runtime_probe=always_usable,
            )

            self.assertEqual(controller.start(open_browser=False), 1)

            self.assertEqual(fake.terminated, [1002, 1001, 1000])
            self.assertFalse((root / ".local/platform-launcher.json").exists())

    def test_stop_never_kills_a_reused_pid_with_changed_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = make_root(Path(tmp))
            state_path = root / ".local/platform-launcher.json"
            state_path.parent.mkdir(parents=True)
            state_path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "services": [
                            {"name": "api", "pid": 42, "identity": ["run_ui_api.py", "--serve"], "log_path": "api.log"}
                        ],
                    }
                ),
                encoding="utf-8",
            )
            fake = FakeSystem()
            fake.command_lines[42] = "python unrelated_backup.py"
            controller = PlatformController(root=root, system=fake, environ={})

            self.assertEqual(controller.stop(), 0)

            self.assertEqual(fake.terminated, [])
            self.assertFalse(state_path.exists())

    def test_stop_terminates_only_verified_owned_process_trees(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = make_root(Path(tmp))
            fake = FakeSystem()
            fake.ready = {
                "http://127.0.0.1:8766/context": True,
                "http://127.0.0.1:5173/": True,
            }
            controller = PlatformController(
                root=root,
                system=fake,
                environ={"USERPROFILE": str(Path(tmp) / "profile")},
                python_runtime_probe=always_usable,
            )
            self.assertEqual(controller.start(open_browser=False), 0)

            self.assertEqual(controller.stop(), 0)

            self.assertEqual(fake.terminated, [1002, 1001, 1000])

    def test_missing_node_modules_blocks_start(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = make_root(Path(tmp))
            (root / "ui/node_modules/.ready").unlink()
            (root / "ui/node_modules").rmdir()
            fake = FakeSystem()
            controller = PlatformController(
                root=root,
                system=fake,
                environ={"USERPROFILE": str(Path(tmp) / "profile")},
                python_runtime_probe=always_usable,
            )
            self.assertEqual(controller.start(open_browser=False), 1)
            self.assertEqual(fake.spawn_calls, [])

    def test_missing_venv_blocks_start_even_when_moomoo_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = make_root(Path(tmp))
            (root / ".venv/Scripts/python.exe").unlink()
            (root / ".venv/Scripts").rmdir()
            (root / ".venv").rmdir()
            profile = Path(tmp) / "profile"
            moomoo = profile / "moomoo-api-test/.venv/Scripts/python.exe"
            moomoo.parent.mkdir(parents=True)
            moomoo.write_text("fixture", encoding="utf-8")
            fake = FakeSystem()
            controller = PlatformController(
                root=root,
                system=fake,
                environ={"USERPROFILE": str(profile)},
                python_runtime_probe=always_usable,
            )
            self.assertEqual(controller.start(open_browser=False), 1)
            self.assertEqual(fake.spawn_calls, [])
            with self.assertRaises(LauncherError):
                select_backend_python(root, {}, profile)

    def test_override_missing_file_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = make_root(Path(tmp))
            missing = Path(tmp) / "missing-python.exe"
            with self.assertRaises(LauncherError):
                select_backend_python(root, {"IMP_PLATFORM_BACKEND_PYTHON": str(missing)})

    def test_open_uses_spa_root_not_discover_proxy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = make_root(Path(tmp))
            fake = FakeSystem()
            fake.ready = {"http://127.0.0.1:5173/": True}
            controller = PlatformController(
                root=root,
                system=fake,
                environ={"USERPROFILE": str(Path(tmp) / "profile")},
                python_runtime_probe=always_usable,
            )
            self.assertEqual(controller.open(), 0)
            self.assertEqual(fake.opened, ["http://127.0.0.1:5173/"])

    def test_status_ready_prints_spa_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = make_root(Path(tmp))
            fake = FakeSystem()
            fake.ready = {
                "http://127.0.0.1:8766/context": True,
                "http://127.0.0.1:5173/": True,
            }
            controller = PlatformController(
                root=root,
                system=fake,
                environ={"USERPROFILE": str(Path(tmp) / "profile")},
                python_runtime_probe=always_usable,
            )
            self.assertEqual(controller.start(open_browser=False), 0)
            fake.open_ports.update({8766, 5173, 8767})
            captured = io.StringIO()
            with contextlib.redirect_stdout(captured):
                self.assertEqual(controller.status(), 0)
            text = captured.getvalue()
            self.assertIn("http://127.0.0.1:5173/", text)
            self.assertNotIn("/discover", text)

    def test_status_partial_when_owned_identity_lost(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = make_root(Path(tmp))
            fake = FakeSystem()
            fake.ready = {
                "http://127.0.0.1:8766/context": True,
                "http://127.0.0.1:5173/": True,
            }
            controller = PlatformController(
                root=root,
                system=fake,
                environ={"USERPROFILE": str(Path(tmp) / "profile")},
                python_runtime_probe=always_usable,
            )
            self.assertEqual(controller.start(open_browser=False), 0)
            fake.command_lines[1000] = "python unrelated_backup.py"
            captured = io.StringIO()
            with contextlib.redirect_stdout(captured):
                self.assertEqual(controller.status(), 1)
            text = captured.getvalue()
            self.assertIn("NOT RUNNING OR PARTIAL", text)
            self.assertIn("API identity owned  NO", text)

    def test_occupied_unowned_port_blocks_start(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = make_root(Path(tmp))
            fake = FakeSystem()
            fake.open_ports.add(8766)
            controller = PlatformController(
                root=root,
                system=fake,
                environ={"USERPROFILE": str(Path(tmp) / "profile")},
                python_runtime_probe=always_usable,
            )
            self.assertEqual(controller.start(open_browser=False), 1)
            self.assertEqual(fake.spawn_calls, [])

    def test_stop_is_noop_without_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = make_root(Path(tmp))
            fake = FakeSystem()
            controller = PlatformController(root=root, system=fake, environ={})
            self.assertEqual(controller.stop(), 0)
            self.assertEqual(fake.terminated, [])

    def test_root_command_files_expose_start_stop_and_control(self) -> None:
        repository = Path(__file__).resolve().parents[2]
        expected = {
            "START_PLATFORM.cmd": ("start", "--open"),
            "STOP_PLATFORM.cmd": ("stop",),
            "PLATFORM_CONTROL.cmd": ("menu",),
        }
        for filename, tokens in expected.items():
            with self.subTest(filename=filename):
                text = (repository / filename).read_text(encoding="utf-8")
                self.assertIn("%~dp0", text)
                self.assertIn(".venv\\Scripts\\python.exe", text)
                self.assertIn("tools\\platform\\local_launcher.py", text)
                for token in tokens:
                    self.assertIn(token, text)
                if filename != "PLATFORM_CONTROL.cmd":
                    self.assertIn('set "IMP_EXIT_CODE=%ERRORLEVEL%"', text)
                    self.assertIn("exit /b %IMP_EXIT_CODE%", text)

                if filename == "START_PLATFORM.cmd":
                    self.assertIn("IMP_PLATFORM_BACKEND_PYTHON", text)

    def test_missing_sklearn_blocks_start(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = make_root(Path(tmp))
            fake = FakeSystem()
            controller = PlatformController(
                root=root,
                system=fake,
                environ={"USERPROFILE": str(Path(tmp) / "profile")},
                python_runtime_probe=lambda _python: False,
            )
            self.assertEqual(controller.start(open_browser=False), 1)
            self.assertEqual(fake.spawn_calls, [])

    def test_vite_proxy_covers_operator_json_and_spa_html_bypass(self) -> None:
        repository = Path(__file__).resolve().parents[2]
        text = (repository / "ui/vite.config.ts").read_text(encoding="utf-8")
        for token in (
            '"/opportunities"',
            '"/intelligence"',
            '"/canary"',
            "spaHtmlBypass",
            '"/discover"',
            '"/control"',
        ):
            with self.subTest(token=token):
                self.assertIn(token, text)

    def test_restart_subcommand_stops_then_starts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = make_root(Path(tmp))
            fake = FakeSystem()
            fake.ready = {
                "http://127.0.0.1:8766/context": True,
                "http://127.0.0.1:5173/": True,
            }
            controller = PlatformController(
                root=root,
                system=fake,
                environ={"USERPROFILE": str(Path(tmp) / "profile")},
                python_runtime_probe=lambda _python: True,
            )
            self.assertEqual(controller.start(open_browser=False), 0)
            self.assertEqual(len(fake.spawn_calls), 3)
            self.assertEqual(controller.restart(open_browser=False), 0)
            self.assertEqual(len(fake.spawn_calls), 6)
            self.assertEqual(fake.terminated, [1002, 1001, 1000])

    def test_operator_docs_name_one_click_start_logs_and_safe_stop(self) -> None:
        repository = Path(__file__).resolve().parents[2]
        docs = (repository / "README.md").read_text(encoding="utf-8") + (repository / "ui/README.md").read_text(
            encoding="utf-8"
        )
        for phrase in (
            "START_PLATFORM.cmd",
            "STOP_PLATFORM.cmd",
            ".local/platform-backend.log",
            ".local/platform-ui.log",
            "launcher-owned",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, docs)


if __name__ == "__main__":
    unittest.main()
