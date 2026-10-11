from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path, PureWindowsPath
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]

from tools.platform.local_launcher import (
    LauncherError,
    PlatformController,
    build_backend_environment,
    select_backend_python,
    WindowsSystem,
)


def always_usable(_python: Path) -> bool:
    return True


class FakeSystem:
    def __init__(self) -> None:
        self.next_pid = 1000
        self.spawn_calls: list[dict[str, object]] = []
        self.command_lines: dict[int, str] = {}
        self.terminated: list[int] = []
        self.creation_times: dict[int, str] = {}
        self.failed_terminations: set[int] = set()
        self.opened: list[str] = []
        self.ready: dict[str, bool] = {}
        self.open_ports: set[int] = set()

    def which(self, executable: str) -> str | None:
        if executable == "npm.cmd":
            # The Windows launcher contract is tested on Linux too. Supply a
            # host-native absolute fixture, including spaces to retain quoting coverage.
            return str(Path(tempfile.gettempdir()) / "Program Files/nodejs/npm.cmd")
        return None

    def port_is_open(self, host: str, port: int) -> bool:
        return int(port) in self.open_ports

    def spawn(self, argv, *, cwd: Path, env, log_path: Path) -> int:  # type: ignore[no-untyped-def]
        pid = self.next_pid
        self.next_pid += 1
        command_line = subprocess.list2cmdline([str(item) for item in argv])
        self.creation_times[pid] = str(100_000 + pid)
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

    def creation_time(self, pid: int) -> str | None:
        return self.creation_times.get(pid)

    def terminate_tree(self, pid: int, *, creation_time: str | None = None) -> bool:
        if creation_time is not None and self.creation_times.get(pid) != creation_time:
            return False
        if pid in self.failed_terminations:
            return False
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

    def test_backend_environment_enables_every_provider_source_unless_overridden(self) -> None:
        env = build_backend_environment({"IMP_CRYPTO_LIVE": "0"})

        for gate in ("IMP_NEWS_RSS_LIVE", "IMP_EDGAR_LIVE", "IMP_PUBLIC_RECORDS_LIVE", "IMP_TREASURY_LIVE",
                     "IMP_NEWSAPI_LIVE", "IMP_FINNHUB_LIVE", "IMP_FINRA_LIVE", "IMP_SEC_FTD_LIVE"):
            self.assertEqual(env[gate], "1", gate)
        self.assertEqual(env["IMP_CRYPTO_LIVE"], "0")
        # Broker transports and recorded replay are not data-source gates.
        self.assertNotIn("IMP_IBKR_LIVE", env)
        self.assertNotIn("IMP_ORDER_FLOW_LIVE", env)

    def test_controlled_replay_profile_strips_live_and_isolates_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = make_root(Path(tmp))
            env = build_backend_environment(
                {"IMP_LIVE_OBSERVATIONAL": "1", "IMP_MOOMOO_LIVE": "1"},
                profile="controlled-replay",
                root=root,
            )
            self.assertEqual(env["IMP_CONTROLLED_REPLAY"], "1")
            self.assertNotIn("IMP_LIVE_OBSERVATIONAL", env)
            self.assertNotIn("IMP_MOOMOO_LIVE", env)
            self.assertEqual(env["IMP_PAPER_EXECUTION"], "0")
            self.assertIn("controlled-replay", env["IMP_STATE_DIR"].replace("\\", "/"))
            self.assertNotIn("IMP_LIVE_EXECUTION", env)

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

            self.assertEqual(controller.stop(), 1)

            self.assertEqual(fake.terminated, [])
            self.assertTrue(state_path.exists())

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

    def running_controller(self, base: Path) -> tuple[Path, FakeSystem, PlatformController]:
        root = make_root(base)
        fake = FakeSystem()
        fake.ready = {"http://127.0.0.1:8766/context": True, "http://127.0.0.1:5173/": True}
        controller = PlatformController(root=root, system=fake, environ={}, python_runtime_probe=always_usable)
        self.assertEqual(controller.start(open_browser=False), 0)
        return root, fake, controller

    def test_saved_ownership_binds_birth_runtime_and_checkout_for_every_service(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, fake, controller = self.running_controller(Path(tmp))
            state = json.loads(controller.state_path.read_text(encoding="utf-8"))
            self.assertEqual(state["version"], 2)
            services = {row["name"]: row for row in state["services"]}
            for row in services.values():
                self.assertEqual(row["creation_time"], fake.creation_times[row["pid"]])
            for name, script in (("api", "tools/ui1/run_ui_api.py"), ("control", "tools/platform/control_service.py")):
                self.assertIn(str(root / ".venv/Scripts/python.exe"), services[name]["identity"])
                self.assertIn(str(root / script), services[name]["identity"])
            self.assertIn(str(root / "ui"), services["ui"]["identity"])
            self.assertIn("--prefix", fake.spawn_calls[1]["argv"])
            self.assertIn(str(root / "ui"), fake.spawn_calls[1]["argv"])

    def test_stop_preserves_reused_pid_with_identical_command_but_new_birth(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, fake, controller = self.running_controller(Path(tmp))
            fake.creation_times[1000] = "different-process-birth"
            self.assertEqual(controller.stop(), 1)
            self.assertEqual(fake.terminated, [1002, 1001])
            self.assertEqual([row.pid for row in controller._read_state()], [1000])

    def test_stop_preserves_matching_generic_signature_from_another_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, fake, controller = self.running_controller(Path(tmp))
            fake.command_lines[1000] = fake.command_lines[1000].replace(str(root), str(root.parent / "other-checkout"))
            self.assertEqual(controller.stop(), 1)
            self.assertEqual(fake.terminated, [1002, 1001])
            self.assertIn(1000, fake.command_lines)

    def test_legacy_or_missing_birth_state_never_authorizes_termination(self) -> None:
        for version in (1, 2):
            with self.subTest(version=version), tempfile.TemporaryDirectory() as tmp:
                root, fake, controller = self.running_controller(Path(tmp))
                state = json.loads(controller.state_path.read_text(encoding="utf-8"))
                state["version"] = version
                for row in state["services"]:
                    row.pop("creation_time", None)
                controller.state_path.write_text(json.dumps(state), encoding="utf-8")
                self.assertEqual(controller.stop(), 1)
                self.assertEqual(fake.terminated, [])
                self.assertTrue(controller.state_path.is_file())

    def test_relative_runtime_identity_never_authorizes_termination(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, fake, controller = self.running_controller(Path(tmp))
            state = json.loads(controller.state_path.read_text(encoding="utf-8"))
            service = state["services"][0]
            service["identity"][0] = "python.exe"
            fake.command_lines[service["pid"]] = subprocess.list2cmdline(service["identity"])
            controller.state_path.write_text(json.dumps(state), encoding="utf-8")
            self.assertEqual(controller.stop(), 1)
            self.assertEqual(fake.terminated, [1002, 1001])
            self.assertEqual([row.pid for row in controller._read_state()], [1000])

    def test_missing_command_identity_never_authorizes_termination(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, fake, controller = self.running_controller(Path(tmp))
            state = json.loads(controller.state_path.read_text(encoding="utf-8"))
            for row in state["services"]:
                row.pop("identity")
            controller.state_path.write_text(json.dumps(state), encoding="utf-8")
            self.assertEqual(controller.stop(), 1)
            self.assertEqual(fake.terminated, [])
            self.assertTrue(controller.state_path.exists())

    def test_partial_command_tokens_do_not_authorize_another_port(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, fake, controller = self.running_controller(Path(tmp))
            fake.command_lines[1000] = fake.command_lines[1000].replace("--port 8766", "--port 87660")
            self.assertEqual(controller.stop(), 1)
            self.assertEqual(fake.terminated, [1002, 1001])

    def test_birth_change_immediately_before_termination_is_rechecked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, fake, controller = self.running_controller(Path(tmp))
            terminate = fake.terminate_tree
            def replace_before_stop(pid: int, *, creation_time: str | None = None) -> bool:
                if pid == 1000:
                    fake.creation_times[pid] = "replacement-birth"
                return terminate(pid, creation_time=creation_time)
            fake.terminate_tree = replace_before_stop
            self.assertEqual(controller.stop(), 1)
            self.assertEqual(fake.terminated, [1002, 1001])
            self.assertEqual([row.pid for row in controller._read_state()], [1000])

    def test_rollback_preserves_pid_reused_after_spawn(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = make_root(Path(tmp))
            fake = FakeSystem()
            controller = PlatformController(root=root, system=fake, environ={}, python_runtime_probe=always_usable)
            def failed_readiness() -> bool:
                fake.creation_times[1000] = "replacement-birth"
                return False
            controller._wait_until_ready = failed_readiness
            self.assertEqual(controller.start(open_browser=False), 1)
            self.assertEqual(fake.terminated, [1002, 1001])
            self.assertEqual([row.pid for row in controller._read_state()], [1000])

    def test_partial_stop_failure_retains_retryable_state_and_blocks_restart(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, fake, controller = self.running_controller(Path(tmp))
            fake.failed_terminations.add(1001)
            self.assertEqual(controller.restart(open_browser=False), 1)
            self.assertEqual(len(fake.spawn_calls), 3)
            self.assertEqual([row.pid for row in controller._read_state()], [1001])
            fake.failed_terminations.clear()
            self.assertEqual(controller.stop(), 0)
            self.assertFalse(controller.state_path.exists())
            self.assertEqual(fake.terminated, [1002, 1000, 1001])

    def test_unavailable_birth_identity_blocks_start_without_killing_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = make_root(Path(tmp))
            fake = FakeSystem()
            fake.ready = {"http://127.0.0.1:8766/context": True, "http://127.0.0.1:5173/": True}
            fake.creation_time = lambda pid: None
            controller = PlatformController(root=root, system=fake, environ={}, python_runtime_probe=always_usable)
            self.assertEqual(controller.start(open_browser=False), 1)
            self.assertEqual(len(fake.spawn_calls), 1)
            self.assertEqual(fake.terminated, [])
            self.assertTrue(controller.state_path.exists())

    def test_status_does_not_report_pid_replacement_as_owned(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root, fake, controller = self.running_controller(Path(tmp))
            fake.open_ports.update({8766, 5173, 8767})
            fake.creation_times[1000] = "replacement-birth"
            captured = io.StringIO()
            with contextlib.redirect_stdout(captured):
                self.assertEqual(controller.status(), 1)
            self.assertIn("API identity owned  NO", captured.getvalue())

    def test_windows_creation_time_is_fail_closed_and_never_prints_commands(self) -> None:
        with mock.patch("tools.platform.local_launcher.os.name", "nt"), mock.patch("tools.platform.local_launcher.subprocess.run") as run:
            run.return_value = subprocess.CompletedProcess([], 0, stdout="638959968000000000\n")
            self.assertEqual(WindowsSystem().creation_time(42), "638959968000000000")
            self.assertIn("StartTime", run.call_args.args[0][-1])
            self.assertNotIn("CommandLine", run.call_args.args[0][-1])
            run.return_value = subprocess.CompletedProcess([], 1, stdout="638959968000000000\n")
            self.assertIsNone(WindowsSystem().creation_time(42))

    def test_windows_tree_termination_pins_process_and_checks_birth_before_taskkill(self) -> None:
        with mock.patch("tools.platform.local_launcher.os.name", "nt"), mock.patch("tools.platform.local_launcher.subprocess.run") as run:
            run.return_value = subprocess.CompletedProcess([], 0, stdout="")
            self.assertTrue(WindowsSystem().terminate_tree(42, creation_time="638959968000000000"))
            script = run.call_args.args[0][-1]
            self.assertIn(".Handle", script)
            self.assertIn("StartTime", script)
            self.assertIn("638959968000000000", script)
            self.assertLess(script.index("StartTime"), script.index("taskkill.exe"))
            run.reset_mock()
            self.assertFalse(WindowsSystem().terminate_tree(42))
            run.assert_not_called()

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
            self.assertIn("API pid               1000", text)

    def test_script_status_imports_without_pythonpath(self) -> None:
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        completed = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "platform" / "local_launcher.py"), "status"],
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        self.assertNotIn("ModuleNotFoundError", completed.stderr)
        self.assertIn("LOCAL PLATFORM STATUS", completed.stdout)
        self.assertEqual(completed.returncode, 1)

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

    def test_shortcut_runs_start_platform_from_the_checkout(self) -> None:
        from tools.platform.local_launcher import shortcut_script

        # Windows paths on every host: only Windows PowerShell ever runs the script.
        root = PureWindowsPath(r"C:\Users\o'neil\market platform")
        script = shortcut_script(
            shortcut=PureWindowsPath(r"C:\Users\o'neil\Desktop\Market Platform.lnk"),
            target=root / "START_PLATFORM.cmd",
            working_directory=root,
        )
        self.assertIn("WScript.Shell", script)
        # Single quotes are doubled so a path with an apostrophe stays one literal.
        self.assertIn(r"$link.TargetPath = 'C:\Users\o''neil\market platform\START_PLATFORM.cmd'", script)
        self.assertIn(r"$link.WorkingDirectory = 'C:\Users\o''neil\market platform'", script)
        self.assertIn("$link.Save()", script)
        # Minimized would hide a start failure, which waits for a key press.
        self.assertNotIn("WindowStyle = 7", script)

    def test_lifecycle_actions_run_outside_the_requesting_process_tree(self) -> None:
        from tools.platform import control_service

        command = [r"C:\repo\.venv\Scripts\python.exe", r"C:\repo\tools\platform\local_launcher.py", "restart"]
        detached = control_service.detached_action_command(command)
        if os.name == "nt":
            # Restart kills the API tree; a direct child of the API would die before it starts the new stack.
            self.assertIsInstance(detached, str)
            self.assertTrue(str(detached).startswith('cmd.exe /d /c start "" /b '))
            self.assertTrue(str(detached).endswith(subprocess.list2cmdline(command)))
        else:
            self.assertEqual(detached, command)

    def test_restart_waits_for_stopped_services_to_release_their_ports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = make_root(Path(tmp))
            fake = FakeSystem()
            fake.ready = {"http://127.0.0.1:8766/context": True, "http://127.0.0.1:5173/": True}
            controller = PlatformController(root=root, system=fake, environ={"USERPROFILE": str(Path(tmp) / "profile")},
                                            python_runtime_probe=always_usable)
            self.assertEqual(controller.start(open_browser=False), 0)
            # The old API socket lingers for two polls after taskkill returns.
            fake.open_ports.add(8766)
            sleeps: list[float] = []

            def sleep(seconds: float) -> None:
                sleeps.append(seconds)
                if len(sleeps) == 2:
                    fake.open_ports.discard(8766)

            fake.sleep = sleep  # type: ignore[method-assign]
            self.assertEqual(controller.restart(open_browser=False), 0)
            self.assertEqual(len(sleeps), 2)
            self.assertEqual(len(fake.spawn_calls), 6)

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
