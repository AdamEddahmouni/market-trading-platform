"""Safe Windows lifecycle controller for the local Integrated Market Platform."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import webbrowser
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping, Protocol, Sequence


ROOT = Path(__file__).resolve().parents[2]
API_HOST = "127.0.0.1"
API_PORT = 8766
UI_HOST = "127.0.0.1"
UI_PORT = 5173
API_URL = f"http://{API_HOST}:{API_PORT}/context"
UI_URL = f"http://{UI_HOST}:{UI_PORT}/"
DISCOVER_URL = f"http://{UI_HOST}:{UI_PORT}/discover"
STATE_RELATIVE_PATH = Path(".local/platform-launcher.json")


class LauncherError(RuntimeError):
    """An actionable local-launch failure that contains no secret values."""


class SystemOperations(Protocol):
    def which(self, executable: str) -> str | None: ...

    def port_is_open(self, host: str, port: int) -> bool: ...

    def spawn(
        self,
        argv: Sequence[str],
        *,
        cwd: Path,
        env: Mapping[str, str],
        log_path: Path,
    ) -> int: ...

    def command_line(self, pid: int) -> str | None: ...

    def terminate_tree(self, pid: int) -> bool: ...

    def url_ready(self, url: str, timeout_seconds: float = 1.0) -> bool: ...

    def open_browser(self, url: str) -> bool: ...

    def sleep(self, seconds: float) -> None: ...


@dataclass(frozen=True)
class ServiceRecord:
    name: str
    pid: int
    identity: list[str]
    log_path: str

    @classmethod
    def from_dict(cls, value: object) -> "ServiceRecord | None":
        if not isinstance(value, dict):
            return None
        try:
            name = str(value["name"])
            pid = int(value["pid"])
            identity = [str(token) for token in value["identity"]]
            log_path = str(value["log_path"])
        except (KeyError, TypeError, ValueError):
            return None
        if not name or pid <= 0 or not identity:
            return None
        return cls(name=name, pid=pid, identity=identity, log_path=log_path)


class WindowsSystem:
    def which(self, executable: str) -> str | None:
        return shutil.which(executable)

    def port_is_open(self, host: str, port: int) -> bool:
        try:
            with socket.create_connection((host, port), timeout=0.35):
                return True
        except OSError:
            return False

    def spawn(
        self,
        argv: Sequence[str],
        *,
        cwd: Path,
        env: Mapping[str, str],
        log_path: Path,
    ) -> int:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        creation_flags = 0
        if os.name == "nt":
            creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
        with log_path.open("ab") as log_handle:
            process = subprocess.Popen(
                list(argv),
                cwd=str(cwd),
                env=dict(env),
                stdin=subprocess.DEVNULL,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                creationflags=creation_flags,
                close_fds=True,
            )
        return int(process.pid)

    def command_line(self, pid: int) -> str | None:
        if os.name != "nt":
            return None
        script = (
            f"$p=Get-CimInstance Win32_Process -Filter \"ProcessId = {int(pid)}\" "
            "-ErrorAction SilentlyContinue; if ($p) { $p.CommandLine }"
        )
        try:
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                check=False,
                capture_output=True,
                text=True,
                timeout=8,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        line = result.stdout.strip()
        return line or None

    def terminate_tree(self, pid: int) -> bool:
        if os.name != "nt":
            return False
        try:
            result = subprocess.run(
                ["taskkill.exe", "/PID", str(int(pid)), "/T", "/F"],
                check=False,
                capture_output=True,
                text=True,
                timeout=15,
            )
        except (OSError, subprocess.TimeoutExpired):
            return False
        return result.returncode == 0

    def url_ready(self, url: str, timeout_seconds: float = 1.0) -> bool:
        request = urllib.request.Request(url, headers={"User-Agent": "imp-local-launcher/1.0"})
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                return 200 <= int(response.status) < 500
        except (OSError, urllib.error.URLError, ValueError):
            return False

    def open_browser(self, url: str) -> bool:
        return bool(webbrowser.open(url, new=2))

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


def select_backend_python(root: Path, environ: Mapping[str, str], user_profile: Path | None = None) -> Path:
    override = str(environ.get("IMP_PLATFORM_BACKEND_PYTHON") or "").strip()
    if override:
        candidate = Path(override).expanduser()
        if not candidate.is_file():
            raise LauncherError("IMP_PLATFORM_BACKEND_PYTHON does not point to an existing file")
        return candidate

    profile = user_profile
    if profile is None:
        raw_profile = str(environ.get("USERPROFILE") or "").strip()
        profile = Path(raw_profile) if raw_profile else Path.home()
    moomoo_python = profile / "moomoo-api-test/.venv/Scripts/python.exe"
    if moomoo_python.is_file():
        return moomoo_python

    repository_python = root / ".venv/Scripts/python.exe"
    if repository_python.is_file():
        return repository_python
    raise LauncherError("Python 3.11 environment missing: create .venv before starting the platform")


def build_backend_environment(environ: Mapping[str, str]) -> dict[str, str]:
    result = {str(key): str(value) for key, value in environ.items()}
    defaults = {
        "IMP_LIVE_OBSERVATIONAL": "1",
        "IMP_MOOMOO_LIVE": "1",
        "IMP_FINVIZ_LIVE": "1",
        "IMP_PAPER_EXECUTION": "1",
        "IMP_LIVE_INTERNAL_SIMULATION": "1",
        "IMP_PERSIST_STATE": "1",
        "PYTHONUNBUFFERED": "1",
    }
    for key, value in defaults.items():
        result.setdefault(key, value)
    return result


def command_identity_matches(command_line: str | None, identity: Sequence[str]) -> bool:
    if not command_line:
        return False
    normalized = command_line.casefold()
    return all(str(token).casefold() in normalized for token in identity)


class PlatformController:
    def __init__(
        self,
        *,
        root: Path = ROOT,
        system: SystemOperations | None = None,
        environ: Mapping[str, str] | None = None,
        readiness_attempts: int = 30,
        readiness_interval_seconds: float = 0.5,
    ) -> None:
        self.root = root.resolve()
        self.system = system or WindowsSystem()
        self.environ = dict(os.environ if environ is None else environ)
        self.readiness_attempts = max(1, int(readiness_attempts))
        self.readiness_interval_seconds = max(0.0, float(readiness_interval_seconds))
        self.state_path = self.root / STATE_RELATIVE_PATH

    def _read_state(self) -> list[ServiceRecord]:
        if not self.state_path.is_file():
            return []
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return []
        if not isinstance(payload, dict) or payload.get("version") != 1:
            return []
        services = payload.get("services")
        if not isinstance(services, list):
            return []
        return [record for item in services if (record := ServiceRecord.from_dict(item)) is not None]

    def _write_state(self, services: Sequence[ServiceRecord]) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        body = {"version": 1, "services": [asdict(service) for service in services]}
        fd, temporary_name = tempfile.mkstemp(prefix="platform-launcher-", suffix=".tmp", dir=self.state_path.parent)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(body, handle, sort_keys=True, separators=(",", ":"))
                handle.write("\n")
            os.replace(temporary, self.state_path)
        finally:
            temporary.unlink(missing_ok=True)

    def _clear_state(self) -> None:
        self.state_path.unlink(missing_ok=True)

    def _is_owned(self, service: ServiceRecord) -> bool:
        return command_identity_matches(self.system.command_line(service.pid), service.identity)

    def _both_ready(self) -> bool:
        return self.system.url_ready(API_URL) and self.system.url_ready(UI_URL)

    def _wait_until_ready(self) -> bool:
        for attempt in range(self.readiness_attempts):
            if self._both_ready():
                return True
            if attempt + 1 < self.readiness_attempts:
                self.system.sleep(self.readiness_interval_seconds)
        return False

    def _validate_prerequisites(self) -> tuple[Path, str]:
        backend_entrypoint = self.root / "tools/ui1/run_ui_api.py"
        if not backend_entrypoint.is_file():
            raise LauncherError("Backend entry point missing: tools/ui1/run_ui_api.py")
        if not (self.root / "ui/node_modules").is_dir():
            raise LauncherError("UI dependencies missing: run 'npm install' inside the ui directory")
        npm = self.system.which("npm.cmd") or self.system.which("npm")
        if not npm:
            raise LauncherError("npm is not available on PATH; install Node.js before starting")
        backend_python = select_backend_python(self.root, self.environ)
        return backend_python, npm

    def _rollback(self, services: Sequence[ServiceRecord]) -> None:
        for service in reversed(services):
            self.system.terminate_tree(service.pid)
        self._clear_state()

    def start(self, *, open_browser: bool) -> int:
        existing = self._read_state()
        if existing and len(existing) == 2 and all(self._is_owned(service) for service in existing) and self._both_ready():
            print("Platform is already running.")
            if open_browser:
                self.system.open_browser(DISCOVER_URL)
            return 0
        if existing:
            self.stop()

        for name, host, port in (("API", API_HOST, API_PORT), ("UI", UI_HOST, UI_PORT)):
            if self.system.port_is_open(host, port):
                print(f"ERROR: {name} port {port} is already in use by a process not owned by this launcher.")
                return 1

        try:
            backend_python, npm = self._validate_prerequisites()
        except LauncherError as exc:
            print(f"ERROR: {exc}")
            return 1

        backend_log = self.root / ".local/platform-backend.log"
        ui_log = self.root / ".local/platform-ui.log"
        environment = build_backend_environment(self.environ)
        services: list[ServiceRecord] = []
        try:
            backend_pid = self.system.spawn(
                [
                    str(backend_python),
                    str(self.root / "tools/ui1/run_ui_api.py"),
                    "--serve",
                    "--host",
                    API_HOST,
                    "--port",
                    str(API_PORT),
                ],
                cwd=self.root,
                env=environment,
                log_path=backend_log,
            )
            services.append(
                ServiceRecord(
                    name="api",
                    pid=backend_pid,
                    identity=["run_ui_api.py", "--serve", str(API_PORT)],
                    log_path=str(backend_log.relative_to(self.root).as_posix()),
                )
            )
            self._write_state(services)

            ui_pid = self.system.spawn(
                [npm, "run", "dev", "--", "--host", UI_HOST, "--port", str(UI_PORT)],
                cwd=self.root / "ui",
                env=self.environ,
                log_path=ui_log,
            )
            services.append(
                ServiceRecord(
                    name="ui",
                    pid=ui_pid,
                    identity=["npm", "run", "dev", str(UI_PORT)],
                    log_path=str(ui_log.relative_to(self.root).as_posix()),
                )
            )
            self._write_state(services)
        except (OSError, LauncherError) as exc:
            self._rollback(services)
            print(f"ERROR: platform process start failed: {exc}")
            return 1

        if not self._wait_until_ready():
            self._rollback(services)
            print("ERROR: platform did not become ready; both launcher-owned processes were stopped.")
            print(f"Backend log: {backend_log}")
            print(f"UI log:      {ui_log}")
            return 1

        print(f"Platform ready: {DISCOVER_URL}")
        print(f"Backend log: {backend_log}")
        print(f"UI log:      {ui_log}")
        if open_browser:
            self.system.open_browser(DISCOVER_URL)
        return 0

    def stop(self) -> int:
        services = self._read_state()
        if not services:
            self._clear_state()
            print("Platform is already stopped (no launcher state).")
            return 0
        for service in reversed(services):
            if self._is_owned(service):
                if self.system.terminate_tree(service.pid):
                    print(f"Stopped {service.name} process tree (PID {service.pid}).")
                else:
                    print(f"WARNING: could not stop {service.name} PID {service.pid}; inspect {service.log_path}.")
            else:
                print(f"Skipped PID {service.pid}: current command no longer matches launcher-owned {service.name}.")
        self._clear_state()
        return 0

    def status(self) -> int:
        services = self._read_state()
        owned = {service.name: self._is_owned(service) for service in services}
        api_ready = self.system.url_ready(API_URL)
        ui_ready = self.system.url_ready(UI_URL)
        print("LOCAL PLATFORM STATUS")
        print(f"API process owned       {'YES' if owned.get('api') else 'NO'}")
        print(f"UI process owned        {'YES' if owned.get('ui') else 'NO'}")
        print(f"API loopback ready      {'YES' if api_ready else 'NO'}")
        print(f"UI loopback ready       {'YES' if ui_ready else 'NO'}")
        if all((owned.get("api"), owned.get("ui"), api_ready, ui_ready)):
            print(f"READY                  {DISCOVER_URL}")
            return 0
        print("NOT RUNNING OR PARTIAL")
        return 1

    def open(self) -> int:
        if not self.system.url_ready(UI_URL):
            print("ERROR: UI is not ready. Run START_PLATFORM.cmd first.")
            return 1
        self.system.open_browser(DISCOVER_URL)
        print(f"Opened {DISCOVER_URL}")
        return 0

    def finviz_status(self) -> int:
        try:
            backend_python = select_backend_python(self.root, self.environ)
        except LauncherError as exc:
            print(f"ERROR: {exc}")
            return 1
        return subprocess.call([str(backend_python), str(self.root / "tools/finviz/auth.py"), "status"], cwd=self.root)

    def menu(self) -> int:
        while True:
            print()
            print("INTEGRATED MARKET PLATFORM")
            print("1. Start everything and open Mixed Live")
            print("2. Open Mixed Live in browser")
            print("3. Show local status")
            print("4. Show Finviz authentication status")
            print("5. Stop everything and exit")
            print("6. Exit menu (leave platform running)")
            choice = input("Choose 1-6: ").strip()
            if choice == "1":
                self.start(open_browser=True)
            elif choice == "2":
                self.open()
            elif choice == "3":
                self.status()
            elif choice == "4":
                self.finviz_status()
            elif choice == "5":
                return self.stop()
            elif choice == "6":
                return 0
            else:
                print("Enter a number from 1 through 6.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Start, open, inspect, or stop the local market platform")
    subcommands = parser.add_subparsers(dest="command", required=True)
    start = subcommands.add_parser("start", help="Start API and UI")
    start.add_argument("--open", action="store_true", dest="open_browser", help="Open Mixed Live after readiness")
    subcommands.add_parser("stop", help="Stop launcher-owned API and UI process trees")
    subcommands.add_parser("status", help="Show process ownership and local readiness")
    subcommands.add_parser("open", help="Open Mixed Live if the UI is ready")
    subcommands.add_parser("finviz-status", help="Show sanitized Finviz credential status")
    subcommands.add_parser("menu", help="Show interactive local control menu")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    controller = PlatformController()
    if args.command == "start":
        return controller.start(open_browser=bool(args.open_browser))
    if args.command == "stop":
        return controller.stop()
    if args.command == "status":
        return controller.status()
    if args.command == "open":
        return controller.open()
    if args.command == "finviz-status":
        return controller.finviz_status()
    if args.command == "menu":
        return controller.menu()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
