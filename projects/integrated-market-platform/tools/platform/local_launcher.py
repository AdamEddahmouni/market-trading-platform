"""Safe Windows lifecycle controller for the local Integrated Market Platform."""

from __future__ import annotations

import argparse
import json
import os
import re
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
from pathlib import Path, PurePath
from typing import Callable, Mapping, Protocol, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
API_HOST = "127.0.0.1"
API_PORT = 8766
UI_HOST = "127.0.0.1"
UI_PORT = 5173
CONTROL_HOST = "127.0.0.1"
CONTROL_PORT = 8767
API_URL = f"http://{API_HOST}:{API_PORT}/context"
UI_URL = f"http://{UI_HOST}:{UI_PORT}/"
CONTROL_URL = f"http://{CONTROL_HOST}:{CONTROL_PORT}/control/status"
OPERATOR_URL = UI_URL
STATE_RELATIVE_PATH = Path(".local/platform-launcher.json")
BACKEND_RUNTIME_IMPORT = "import sklearn"
PLATFORM_PORTS = ((API_HOST, API_PORT), (UI_HOST, UI_PORT), (CONTROL_HOST, CONTROL_PORT))
PORT_RELEASE_ATTEMPTS = 40
PORT_RELEASE_INTERVAL_SECONDS = 0.25


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

    def creation_time(self, pid: int) -> str | None: ...

    def terminate_tree(self, pid: int, *, creation_time: str | None = None) -> bool: ...

    def url_ready(self, url: str, timeout_seconds: float = 1.0) -> bool: ...

    def open_browser(self, url: str) -> bool: ...

    def sleep(self, seconds: float) -> None: ...

    def process_alive(self, pid: int) -> bool: ...


@dataclass(frozen=True)
class ServiceRecord:
    name: str
    pid: int
    identity: list[str]
    log_path: str
    creation_time: str | None = None

    @classmethod
    def from_dict(cls, value: object) -> "ServiceRecord | None":
        if not isinstance(value, dict):
            return None
        try:
            name = str(value["name"])
            pid = int(value["pid"])
            raw_identity = value.get("identity", [])
            identity = (
                raw_identity
                if isinstance(raw_identity, list) and all(isinstance(token, str) and token for token in raw_identity)
                else []
            )
            log_path = str(value["log_path"])
        except (KeyError, TypeError, ValueError):
            return None
        if not name or pid <= 0:
            return None
        birth = value.get("creation_time")
        if not isinstance(birth, str) or not birth.isdigit():
            birth = None
        return cls(name=name, pid=pid, identity=identity, log_path=log_path, creation_time=birth)


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
            from tools.platform.detached_process import windows_detached_creationflags

            # Default = tested flags only (CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW).
            # Breakaway is opt-in elsewhere and remains unproven for job/terminal kill.
            creation_flags = windows_detached_creationflags(allow_breakaway=False)
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

    def creation_time(self, pid: int) -> str | None:
        if os.name != "nt":
            return None
        script = (
            "$ErrorActionPreference='Stop'; $p=$null; try { "
            f"$p=[Diagnostics.Process]::GetProcessById({int(pid)}); "
            "$handle=$p.Handle; if (-not $p.HasExited) { $p.StartTime.ToUniversalTime().Ticks } "
            "} catch { exit 1 } finally { if ($p) { $p.Dispose() } }"
        )
        try:
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                check=False, capture_output=True, text=True, timeout=8,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        birth = result.stdout.strip()
        return birth if result.returncode == 0 and birth.isdigit() else None

    def terminate_tree(self, pid: int, *, creation_time: str | None = None) -> bool:
        if os.name != "nt" or not creation_time or not creation_time.isdigit():
            return False
        # Hold the process handle until taskkill completes: Windows cannot recycle
        # the PID while its process object is referenced by this handle.
        script = (
            "$ErrorActionPreference='Stop'; $p=$null; try { "
            f"$p=[Diagnostics.Process]::GetProcessById({int(pid)}); $handle=$p.Handle; "
            f"if ($p.HasExited -or $p.StartTime.ToUniversalTime().Ticks.ToString() -ne '{creation_time}') {{ exit 1 }}; "
            f"& taskkill.exe /PID {int(pid)} /T /F | Out-Null; exit $LASTEXITCODE "
            "} catch { exit 1 } finally { if ($p) { $p.Dispose() } }"
        )
        try:
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                check=False, capture_output=True, text=True, timeout=15,
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

    def process_alive(self, pid: int) -> bool:
        from tools.platform.service_health import process_alive as platform_process_alive

        return platform_process_alive(pid)


def select_backend_python(root: Path, environ: Mapping[str, str], user_profile: Path | None = None) -> Path:
    del user_profile  # retained for call-site compatibility; never auto-select moomoo-api-test
    override = str(environ.get("IMP_PLATFORM_BACKEND_PYTHON") or "").strip()
    if override:
        candidate = Path(override).expanduser()
        if not candidate.is_file():
            raise LauncherError("IMP_PLATFORM_BACKEND_PYTHON does not point to an existing file")
        return candidate

    repository_python = root / ".venv/Scripts/python.exe"
    if repository_python.is_file():
        return repository_python
    posix_python = root / ".venv/bin/python"
    if posix_python.is_file():
        return posix_python
    raise LauncherError("Python 3.11 environment missing: create .venv before starting the platform")


def backend_python_has_runtime(python: Path) -> bool:
    try:
        result = subprocess.run(
            [str(python), "-c", BACKEND_RUNTIME_IMPORT],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


PROVIDER_SOURCE_GATES = (
    "IMP_NEWS_RSS_LIVE",
    "IMP_EDGAR_LIVE",
    "IMP_PUBLIC_RECORDS_LIVE",
    "IMP_SENATE_EFD_LIVE",
    "IMP_TREASURY_LIVE",
    "IMP_CRYPTO_LIVE",
    "IMP_NEWSAPI_LIVE",
    "IMP_FINNHUB_LIVE",
    "IMP_FINRA_LIVE",
    "IMP_SEC_FTD_LIVE",
    "IMP_NYSE_REGSHO_LIVE",
    "IMP_NASDAQ_REGSHO_LIVE",
    "IMP_CBOE_REGSHO_LIVE",
    "IMP_CBOE_OPTIONS_LIVE",
    "IMP_OPENFIGI_LIVE",
    "IMP_FRED_LIVE",
    "IMP_EIA_LIVE",
    "IMP_WEATHER_LIVE",
)


def build_backend_environment(
    environ: Mapping[str, str],
    *,
    profile: str = "default",
    root: Path | None = None,
) -> dict[str, str]:
    profile_name = str(profile or "default").strip().lower().replace("-", "_")
    if profile_name in {"controlled_replay", "controlledreplay", "replay"}:
        from tools.controlled_replay.env import build_controlled_replay_environment

        return build_controlled_replay_environment(environ, root=root or ROOT)

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
    # Every observational data source is on at launch. A gate only permits reads; a
    # source that also needs a key or saved pages still reports NOT_CONFIGURED without them.
    defaults.update({gate: "1" for gate in PROVIDER_SOURCE_GATES})
    for key, value in defaults.items():
        result.setdefault(key, value)
    return result


SHORTCUT_NAME = "Market Platform.lnk"


def desktop_folder() -> Path:
    """The signed-in user's desktop, following OneDrive or a moved Desktop folder."""
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", "[Environment]::GetFolderPath('Desktop')"],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
        folder = result.stdout.strip()
        if folder:
            return Path(folder)
    except (OSError, subprocess.TimeoutExpired):
        pass
    return Path(os.environ.get("USERPROFILE") or Path.home()) / "Desktop"


def _powershell_literal(value: object) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def shortcut_script(*, shortcut: PurePath, target: PurePath, working_directory: PurePath) -> str:
    """PowerShell that writes the .lnk.

    The console opens normally, not minimized: it closes by itself once the platform is
    ready, and on failure it stays open with the error and waits for a key.
    """
    return "; ".join(
        (
            "$shell = New-Object -ComObject WScript.Shell",
            f"$link = $shell.CreateShortcut({_powershell_literal(shortcut)})",
            f"$link.TargetPath = {_powershell_literal(target)}",
            f"$link.WorkingDirectory = {_powershell_literal(working_directory)}",
            "$link.Description = 'Start the Integrated Market Platform and open it in the browser'",
            f"$link.IconLocation = {_powershell_literal(str(Path(os.environ.get('SystemRoot') or 'C:/Windows') / 'System32/imageres.dll') + ',109')}",
            "$link.Save()",
        )
    )


def command_identity_matches(command_line: str | None, identity: Sequence[str]) -> bool:
    if not command_line:
        return False
    normalized = command_line.replace("/", "\\").casefold()
    return bool(identity) and all(
        re.search(r'(?:^|[\s"])' + re.escape(str(token).replace("/", "\\").casefold()) + r'(?=$|[\s"])', normalized)
        for token in identity
    )


class PlatformController:
    def __init__(
        self,
        *,
        root: Path = ROOT,
        system: SystemOperations | None = None,
        environ: Mapping[str, str] | None = None,
        readiness_attempts: int = 30,
        readiness_interval_seconds: float = 0.5,
        python_runtime_probe: Callable[[Path], bool] | None = None,
        profile: str = "default",
    ) -> None:
        self.root = root.resolve()
        self.system = system or WindowsSystem()
        self.environ = dict(os.environ if environ is None else environ)
        self.profile = str(profile or "default")
        self.readiness_attempts = max(1, int(readiness_attempts))
        self.readiness_interval_seconds = max(0.0, float(readiness_interval_seconds))
        self.state_path = self.root / STATE_RELATIVE_PATH
        self._python_runtime_probe = backend_python_has_runtime if python_runtime_probe is None else python_runtime_probe

    def _process_alive(self, pid: int) -> bool:
        return self.system.process_alive(pid)

    def _read_state(self) -> list[ServiceRecord]:
        if not self.state_path.is_file():
            return []
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return []
        if not isinstance(payload, dict) or payload.get("version") not in {1, 2}:
            return []
        services = payload.get("services")
        if not isinstance(services, list):
            return []
        if payload["version"] == 1:
            services = [dict(item, creation_time=None) if isinstance(item, dict) else item for item in services]
        return [record for item in services if (record := ServiceRecord.from_dict(item)) is not None]

    def _write_state(self, services: Sequence[ServiceRecord]) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        body = {"version": 2, "services": [asdict(service) for service in services]}
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
        required_path = {
            "api": self.root / "tools/ui1/run_ui_api.py",
            "control": self.root / "tools/platform/control_service.py",
            "ui": self.root / "ui",
        }.get(service.name)
        if (
            not required_path or str(required_path) not in service.identity
            or not service.identity or not Path(service.identity[0]).is_absolute()
            or (service.name == "ui" and "--prefix" not in service.identity)
            or not service.creation_time or not self._process_alive(service.pid)
        ):
            return False
        return (
            self.system.creation_time(service.pid) == service.creation_time
            and command_identity_matches(self.system.command_line(service.pid), service.identity)
        )

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
            raise LauncherError(
                "UI dependencies missing: run SETUP_PLATFORM.cmd, or 'npm ci' inside the ui directory of this checkout"
            )
        npm = self.system.which("npm.cmd") or self.system.which("npm")
        if not npm:
            raise LauncherError("npm is not available on PATH; install Node.js before starting")
        backend_python = select_backend_python(self.root, self.environ)
        probe = self._python_runtime_probe
        if not probe(backend_python):
            raise LauncherError(
                "Selected Python is missing required runtime packages (sklearn). "
                "Use the repository .venv from SETUP_PLATFORM.cmd, not moomoo-api-test."
            )
        return backend_python, npm

    def _stop_services(self, services: Sequence[ServiceRecord]) -> int:
        retained: set[int] = set()
        for service in reversed(services):
            if not self._process_alive(service.pid):
                continue
            if not self._is_owned(service):
                retained.add(service.pid)
                print(f"Skipped PID {service.pid}: process ownership could not be verified for {service.name}.")
            elif self.system.terminate_tree(service.pid, creation_time=service.creation_time):
                print(f"Stopped {service.name} process tree (PID {service.pid}).")
            else:
                retained.add(service.pid)
                print(f"WARNING: could not stop {service.name} PID {service.pid}; inspect {service.log_path}.")
        if retained:
            self._write_state([service for service in services if service.pid in retained])
            return 1
        self._clear_state()
        return 0

    def _rollback(self, services: Sequence[ServiceRecord]) -> None:
        self._stop_services(services)

    def _record_spawn(
        self, services: list[ServiceRecord], *, name: str, pid: int, command: Sequence[str], log_path: Path
    ) -> None:
        service = ServiceRecord(
            name=name, pid=pid, identity=list(command),
            log_path=log_path.relative_to(self.root).as_posix(),
            creation_time=self.system.creation_time(pid),
        )
        services.append(service)
        self._write_state(services)
        if not self._is_owned(service):
            raise LauncherError("Started process ownership could not be verified; automatic cleanup was withheld.")

    def start(self, *, open_browser: bool) -> int:
        existing = self._read_state()
        required_services = {service.name for service in existing}
        if (
            existing
            and {"api", "ui"}.issubset(required_services)
            and all(self._is_owned(service) for service in existing)
            and "control" in required_services
            and self._both_ready()
        ):
            print("Platform is already running.")
            if open_browser:
                self.system.open_browser(OPERATOR_URL)
            return 0
        if existing and self.stop():
            return 1

        for name, host, port in (("API", API_HOST, API_PORT), ("UI", UI_HOST, UI_PORT), ("CONTROL", CONTROL_HOST, CONTROL_PORT)):
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
        environment = build_backend_environment(self.environ, profile=self.profile, root=self.root)
        services: list[ServiceRecord] = []
        try:
            backend_command = [str(backend_python), str(self.root / "tools/ui1/run_ui_api.py"),
                               "--serve", "--host", API_HOST, "--port", str(API_PORT)]
            backend_pid = self.system.spawn(backend_command, cwd=self.root, env=environment, log_path=backend_log)
            self._record_spawn(services, name="api", pid=backend_pid, command=backend_command, log_path=backend_log)

            ui_command = [npm, "--prefix", str(self.root / "ui"), "run", "dev", "--", "--host", UI_HOST,
                          "--port", str(UI_PORT)]
            ui_pid = self.system.spawn(ui_command, cwd=self.root / "ui", env=self.environ, log_path=ui_log)
            self._record_spawn(services, name="ui", pid=ui_pid, command=ui_command, log_path=ui_log)

            control_command = [str(backend_python), str(self.root / "tools/platform/control_service.py"),
                               "serve", "--host", CONTROL_HOST, "--port", str(CONTROL_PORT)]
            control_log = self.root / ".local/platform-control.log"
            control_pid = self.system.spawn(control_command, cwd=self.root, env=environment, log_path=control_log)
            self._record_spawn(services, name="control", pid=control_pid, command=control_command, log_path=control_log)
        except (OSError, LauncherError) as exc:
            self._rollback(services)
            print(f"ERROR: platform process start failed: {exc}")
            return 1

        if not self._wait_until_ready():
            self._rollback(services)
            print("ERROR: platform did not become ready; verified processes were stopped and unresolved ownership was retained.")
            print(f"Backend log: {backend_log}")
            print(f"UI log:      {ui_log}")
            return 1

        print(f"Platform ready: {OPERATOR_URL}")
        print(f"Backend log: {backend_log}")
        print(f"UI log:      {ui_log}")
        if open_browser:
            self.system.open_browser(OPERATOR_URL)
        return 0

    def restart(self, *, open_browser: bool = False) -> int:
        """Stop launcher-owned services and start a fresh platform stack."""
        if self.stop():
            return 1
        # taskkill returns before Windows releases the listening sockets; starting at once
        # reported "port already in use by a process not owned by this launcher".
        for _ in range(PORT_RELEASE_ATTEMPTS):
            if not any(self.system.port_is_open(host, port) for host, port in PLATFORM_PORTS):
                break
            self.system.sleep(PORT_RELEASE_INTERVAL_SECONDS)
        return self.start(open_browser=open_browser)

    def stop(self) -> int:
        services = self._read_state()
        if not services:
            self._clear_state()
            print("Platform is already stopped (no launcher state).")
            return 0
        return self._stop_services(services)

    def status(self) -> int:
        from tools.platform.service_health import aggregate_platform_health, evaluate_service_health

        services = self._read_state()
        health_by_name = {}
        print("LOCAL PLATFORM STATUS")
        for service in services:
            host, port = {
                "api": (API_HOST, API_PORT),
                "ui": (UI_HOST, UI_PORT),
                "control": (CONTROL_HOST, CONTROL_PORT),
            }.get(service.name, (API_HOST, API_PORT))
            http_url = {
                "api": API_URL,
                "ui": UI_URL,
                "control": None,
            }.get(service.name)
            health = evaluate_service_health(
                pid=service.pid,
                host=host,
                port=port,
                http_url=http_url,
                identity=service.identity,
                command_line=self.system.command_line,
                identity_matches=lambda command, identity: self._is_owned(service),
                port_is_open=self.system.port_is_open,
                process_alive_fn=self._process_alive,
                http_probe=self.system.url_ready,
            )
            health_by_name[service.name] = health
            print(f"{service.name.upper()} pid               {service.pid}")
            print(f"{service.name.upper()} process alive   {'YES' if health.process_alive else 'NO'}")
            print(f"{service.name.upper()} identity owned  {'YES' if health.identity_owned else 'NO'}")
            print(f"{service.name.upper()} port bound        {'YES' if health.port_bound else 'NO'}")
            if health.http_alive is not None:
                print(f"{service.name.upper()} HTTP alive        {'YES' if health.http_alive else 'NO'}")
        aggregate = aggregate_platform_health(health_by_name) if services else "STOPPED"
        if aggregate == "READY":
            print(f"READY                  {OPERATOR_URL}")
            return 0
        print(f"NOT RUNNING OR PARTIAL ({aggregate})")
        return 1

    def open(self) -> int:
        if not self.system.url_ready(UI_URL):
            print("ERROR: UI is not ready. Run START_PLATFORM.cmd first.")
            return 1
        self.system.open_browser(OPERATOR_URL)
        print(f"Opened {OPERATOR_URL}")
        return 0

    def finviz_status(self) -> int:
        try:
            backend_python = select_backend_python(self.root, self.environ)
        except LauncherError as exc:
            print(f"ERROR: {exc}")
            return 1
        return subprocess.call([str(backend_python), str(self.root / "tools/finviz/auth.py"), "status"], cwd=self.root)

    def setup(self) -> int:
        from tools.platform.bootstrap import setup_project

        try:
            report = setup_project(self.root)
        except (OSError, RuntimeError) as exc:
            print(f"ERROR: setup failed: {exc}")
            return 1
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["status"] == "READY" else 1

    def check_update(self) -> int:
        from tools.platform.control_service import check_update

        report = check_update(self.root)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["status"] in {"CURRENT", "AVAILABLE"} else 1

    def apply_update(self) -> int:
        from tools.platform.control_service import check_update

        report = check_update(self.root)
        if report.get("status") != "AVAILABLE":
            print(json.dumps({"status": "BLOCKED", "update": report}, indent=2, sort_keys=True))
            return 1
        git = self.system.which("git.exe") or self.system.which("git")
        npm = self.system.which("npm.cmd") or self.system.which("npm")
        if not git or not npm:
            print("ERROR: Git and npm are required to apply an update.")
            return 1
        if self.stop():
            return 1
        pulled = subprocess.run([git, "pull", "--ff-only"], cwd=self.root, capture_output=True, text=True, check=False)
        if pulled.returncode:
            print("ERROR: fast-forward update failed; no reset or overwrite was attempted.")
            return 1
        synced = subprocess.run([npm, "ci"], cwd=self.root / "ui", capture_output=True, text=True, check=False)
        if synced.returncode:
            print("ERROR: application updated, but UI dependency sync failed. Run SETUP_PLATFORM.cmd.")
            return 1
        return self.start(open_browser=True)

    def install_shortcut(self, desktop: Path | None = None) -> int:
        """Put a "Market Platform" shortcut on the desktop that runs START_PLATFORM.cmd.

        Starting when the platform already runs only opens the browser, so the one icon
        both starts and reopens it. Stop is in the app's top bar, or STOP_PLATFORM.cmd.
        """
        if os.name != "nt":
            print("ERROR: desktop shortcuts are created on Windows only.")
            return 1
        target = self.root / "START_PLATFORM.cmd"
        if not target.is_file():
            print(f"ERROR: {target} is missing.")
            return 1
        folder = desktop or desktop_folder()
        shortcut = folder / SHORTCUT_NAME
        script = shortcut_script(shortcut=shortcut, target=target, working_directory=self.root)
        try:
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            print(f"ERROR: shortcut could not be created: {exc}")
            return 1
        if result.returncode != 0 or not shortcut.is_file():
            print("ERROR: shortcut could not be created.")
            return 1
        print(f"Desktop shortcut ready: {shortcut}")
        return 0

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
    start = subcommands.add_parser("start", help="Start API, UI, and local control service")
    start.add_argument("--open", action="store_true", dest="open_browser", help="Open Mixed Live after readiness")
    start.add_argument(
        "--profile",
        default="default",
        choices=("default", "controlled-replay", "controlled_replay"),
        help="Launch profile (controlled-replay = FIXTURE_REPLAY, no Live gates)",
    )
    subcommands.add_parser("stop", help="Stop launcher-owned API, UI, and control process trees")
    restart = subcommands.add_parser("restart", help="Stop and start API, UI, and control (state persisted when enabled)")
    restart.add_argument("--open", action="store_true", dest="open_browser", help="Open Mixed Live after readiness")
    restart.add_argument(
        "--profile",
        default="default",
        choices=("default", "controlled-replay", "controlled_replay"),
        help="Launch profile",
    )
    subcommands.add_parser("status", help="Show process ownership and local readiness")
    subcommands.add_parser("open", help="Open Mixed Live if the UI is ready")
    subcommands.add_parser("finviz-status", help="Show sanitized Finviz credential status")
    subcommands.add_parser("menu", help="Show interactive local control menu")
    subcommands.add_parser("setup", help="Create or repair project-local dependencies")
    subcommands.add_parser("install-shortcut", help="Create a desktop shortcut that starts and opens the platform")
    subcommands.add_parser("check-update", help="Check for a safe fast-forward application update")
    subcommands.add_parser("apply-update", help="Apply a confirmed safe fast-forward update")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    profile = str(getattr(args, "profile", "default") or "default")
    controller = PlatformController(profile=profile)
    result: int
    if args.command == "start":
        result = controller.start(open_browser=bool(args.open_browser))
    elif args.command == "stop":
        result = controller.stop()
    elif args.command == "restart":
        result = controller.restart(open_browser=bool(args.open_browser))
    elif args.command == "status":
        result = controller.status()
    elif args.command == "open":
        result = controller.open()
    elif args.command == "finviz-status":
        result = controller.finviz_status()
    elif args.command == "menu":
        result = controller.menu()
    elif args.command == "setup":
        result = controller.setup()
    elif args.command == "install-shortcut":
        result = controller.install_shortcut()
    elif args.command == "check-update":
        result = controller.check_update()
    elif args.command == "apply-update":
        result = controller.apply_update()
    else:
        result = 2
    operation_id = str(os.environ.get("IMP_OPERATOR_OPERATION_ID") or "").strip()
    if operation_id:
        try:
            from tools.platform.control_service import update_operation

            update_operation(
                controller.root,
                operation_id,
                status="SUCCEEDED" if result == 0 else "FAILED",
                detail=None if result == 0 else "Lifecycle action failed; inspect the sanitized local log.",
            )
        except (OSError, RuntimeError):
            pass
    return result


if __name__ == "__main__":
    raise SystemExit(main())
