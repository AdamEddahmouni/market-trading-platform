"""G15 product-acceptance harness — deterministic API + UI startup for browser E2E."""

from __future__ import annotations

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
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
COLLECTION_ROOT = ROOT.parent
DEFAULT_API_HOST = "127.0.0.1"
DEFAULT_API_PORT = 8766
DEFAULT_UI_HOST = "127.0.0.1"
DEFAULT_UI_PORT = 5173


def _allocate_ephemeral_port(host: str = "127.0.0.1") -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def _port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.35):
            return True
    except OSError:
        return False


def _url_ready(url: str, timeout: float = 1.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return 200 <= response.status < 500
    except (urllib.error.URLError, TimeoutError, ValueError):
        return False


def _python_executable(root: Path) -> Path:
    venv_python = root / ".venv" / "Scripts" / "python.exe"
    if venv_python.is_file():
        return venv_python
    if sys.version_info >= (3, 11):
        return Path(sys.executable)
    raise RuntimeError("Python 3.11 venv required for product acceptance harness")


def build_e2e_backend_environment(
    *,
    state_dir: Path,
    environ: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Fixture-only Paper backend — no live broker or external provider gates."""
    result = {str(key): str(value) for key, value in (environ or os.environ).items()}
    defaults = {
        "IMP_PAPER_EXECUTION": "1",
        "IMP_LIVE_INTERNAL_SIMULATION": "1",
        "IMP_PERSIST_STATE": "1",
        "IMP_AUTH_ENFORCEMENT_MODE": "LOOPBACK_TRUST",
        "IMP_STATE_DIR": str(state_dir),
        "PYTHONUNBUFFERED": "1",
        "PYTHONPATH": str(ROOT / "src"),
    }
    for key, value in defaults.items():
        result[key] = value
    for live_gate in (
        "IMP_LIVE_OBSERVATIONAL",
        "IMP_MOOMOO_LIVE",
        "IMP_FINVIZ_LIVE",
        "IMP_LIVE_EXECUTION",
    ):
        result.pop(live_gate, None)
    return result


def _http_json(method: str, url: str, body: dict[str, object] | None = None) -> dict[str, object]:
    payload = None
    headers = {"Content-Type": "application/json"}
    if body is not None:
        payload = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url, data=payload, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def prepare_paper_fixture(api_base: str) -> dict[str, object]:
    """Open Paper session and scrub replay to a fillable cursor."""
    _http_json("POST", f"{api_base}/paper/sessions", {"execution_mode": "INTERNAL_SIMULATION"})
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "src"))
    from market_platform_foundation.paper.execution import preview_interactive_order
    from market_platform_foundation.ui_api.store import ReplayStore

    store = ReplayStore(collection_root=COLLECTION_ROOT)
    store.load()
    fillable_index = 0
    for index in range(len(store.bars) - 2, -1, -1):
        store.set_cursor_index(index)
        preview = preview_interactive_order(
            ledger=store.paper_ledger,
            bars=store.bars_for_execution(),
            symbol=store.symbol,
            instrument_id=store.instrument_id,
            side="BUY",
            quantity=1,
            observation_time=store.prediction_cutoff(),
            client_order_id="e2e-cursor-probe",
            idempotency_key="e2e-cursor-probe",
        )
        if preview.get("fill_preview") is not None and preview.get("risk_status") == "PASS":
            fillable_index = index
            break
    return _http_json("POST", f"{api_base}/replay/scrub", {"cursor_index": fillable_index})


@dataclass
class HarnessServices:
    api_host: str
    api_port: int
    ui_host: str
    ui_port: int
    state_dir: Path
    api_log: Path
    ui_log: Path
    api_pid: int
    ui_pid: int

    @property
    def api_base(self) -> str:
        return f"http://{self.api_host}:{self.api_port}"

    @property
    def ui_base(self) -> str:
        return f"http://{self.ui_host}:{self.ui_port}"


class ProductAcceptanceHarness:
    def __init__(
        self,
        *,
        root: Path = ROOT,
        api_host: str = DEFAULT_API_HOST,
        api_port: int = DEFAULT_API_PORT,
        ui_host: str = DEFAULT_UI_HOST,
        ui_port: int = DEFAULT_UI_PORT,
    ) -> None:
        self.root = root.resolve()
        self.api_host = api_host
        self.api_port = api_port
        self.ui_host = ui_host
        self.ui_port = ui_port
        self._state_dir: Path | None = None
        self._api_proc: subprocess.Popen[bytes] | None = None
        self._ui_proc: subprocess.Popen[bytes] | None = None
        self._api_log: Path | None = None
        self._ui_log: Path | None = None

    def start(self, *, prepare_fixture: bool = True) -> HarnessServices:
        if _port_open(self.api_host, self.api_port):
            self.api_port = _allocate_ephemeral_port(self.api_host)
        if _port_open(self.ui_host, self.ui_port):
            self.ui_port = _allocate_ephemeral_port(self.ui_host)

        self._state_dir = Path(tempfile.mkdtemp(prefix="imp-e2e-state-"))
        log_dir = self.root / ".local" / "e2e"
        log_dir.mkdir(parents=True, exist_ok=True)
        self._api_log = log_dir / "api.log"
        self._ui_log = log_dir / "ui.log"

        python = _python_executable(self.root)
        npm = shutil.which("npm.cmd") or shutil.which("npm")
        if not npm:
            raise RuntimeError("npm is required for product acceptance harness")

        api_env = build_e2e_backend_environment(state_dir=self._state_dir)
        with self._api_log.open("w", encoding="utf-8") as api_log_handle:
            self._api_proc = subprocess.Popen(
                [
                    str(python),
                    str(self.root / "tools/ui1/run_ui_api.py"),
                    "--serve",
                    "--host",
                    self.api_host,
                    "--port",
                    str(self.api_port),
                ],
                cwd=str(self.root),
                env=api_env,
                stdout=api_log_handle,
                stderr=subprocess.STDOUT,
            )

        api_url = f"http://{self.api_host}:{self.api_port}/context"
        if not self._wait_until_ready(api_url):
            self.stop()
            raise RuntimeError(f"API did not become ready; see {self._api_log}")

        ui_env = dict(os.environ)
        ui_env["IMP_E2E_API_PORT"] = str(self.api_port)
        ui_env["IMP_E2E_UI_PORT"] = str(self.ui_port)
        with self._ui_log.open("w", encoding="utf-8") as ui_log_handle:
            self._ui_proc = subprocess.Popen(
                [npm, "run", "dev", "--", "--host", self.ui_host, "--port", str(self.ui_port)],
                cwd=str(self.root / "ui"),
                env=ui_env,
                stdout=ui_log_handle,
                stderr=subprocess.STDOUT,
            )

        ui_url = f"http://{self.ui_host}:{self.ui_port}/"
        if not self._wait_until_ready(ui_url):
            self.stop()
            raise RuntimeError(f"UI did not become ready; see {self._ui_log}")

        if prepare_fixture:
            prepare_paper_fixture(f"http://{self.api_host}:{self.api_port}")

        manifest = {
            "api_base": f"http://{self.api_host}:{self.api_port}",
            "ui_base": f"http://{self.ui_host}:{self.ui_port}",
            "api_port": self.api_port,
            "ui_port": self.ui_port,
            "state_dir": str(self._state_dir),
            "api_log": str(self._api_log),
            "ui_log": str(self._ui_log),
        }
        manifest_path = log_dir / "harness.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        return HarnessServices(
            api_host=self.api_host,
            api_port=self.api_port,
            ui_host=self.ui_host,
            ui_port=self.ui_port,
            state_dir=self._state_dir,
            api_log=self._api_log,
            ui_log=self._ui_log,
            api_pid=self._api_proc.pid if self._api_proc else -1,
            ui_pid=self._ui_proc.pid if self._ui_proc else -1,
        )

    def _wait_until_ready(self, url: str, attempts: int = 40, interval: float = 0.5) -> bool:
        for _ in range(attempts):
            if _url_ready(url):
                return True
            time.sleep(interval)
        return False

    def stop(self) -> None:
        for proc in (self._ui_proc, self._api_proc):
            if proc is None or proc.poll() is not None:
                continue
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
        self._ui_proc = None
        self._api_proc = None
        if self._state_dir and self._state_dir.exists():
            shutil.rmtree(self._state_dir, ignore_errors=True)
            self._state_dir = None


def run_playwright(
    *,
    ui_base: str,
    spec: str | None = None,
    extra_args: Sequence[str] = (),
) -> int:
    e2e_dir = ROOT / "e2e"
    npm = shutil.which("npm.cmd") or shutil.which("npm")
    if not npm:
        raise RuntimeError("npm is required to run Playwright acceptance tests")
    env = dict(os.environ)
    env["IMP_E2E_UI_BASE"] = ui_base
    command = [npm, "test"]
    if spec:
        command.extend(["--", spec])
    command.extend(extra_args)
    completed = subprocess.run(
        command,
        cwd=str(e2e_dir),
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    log_dir = ROOT / ".local" / "e2e"
    log_dir.mkdir(parents=True, exist_ok=True)
    playwright_log = log_dir / "playwright.log"
    playwright_log.write_text(
        (completed.stdout or "") + (completed.stderr or ""),
        encoding="utf-8",
    )
    if completed.returncode != 0:
        if completed.stdout:
            sys.stderr.write(completed.stdout)
        if completed.stderr:
            sys.stderr.write(completed.stderr)
    return int(completed.returncode)
