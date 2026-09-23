"""Campaign environment readiness preflight (fail-visible before ARM).

SOFTWARE_CONTROLLED / FIXTURE_REPLAY only for tests. Does not grant execution
authority. Secrets are never printed — credential checks are presence-only.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[2]

API_HOST = "127.0.0.1"
API_PORT = 8766
UI_HOST = "127.0.0.1"
UI_PORT = 5173
OPEND_HOST = "127.0.0.1"
OPEND_PORT = 11111

SCHEMA_VERSION = "campaign-environment-preflight/1.0.0"
EVIDENCE_CLASS = "SOFTWARE_CONTROLLED_EVIDENCE"


@dataclass
class CheckResult:
    name: str
    status: str  # PASS | FAIL | WARN | SKIP
    required_for_arm: bool
    detail: str
    category: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PreflightReport:
    schema_version: str = SCHEMA_VERSION
    evidence_class: str = EVIDENCE_CLASS
    ready_to_arm: bool = False
    execution_authority: str = "BLOCKED"
    allows_network_submit: bool = False
    live_submit_forbidden: bool = True
    checks: list[CheckResult] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "evidence_class": self.evidence_class,
            "ready_to_arm": self.ready_to_arm,
            "execution_authority": self.execution_authority,
            "allows_network_submit": self.allows_network_submit,
            "live_submit_forbidden": self.live_submit_forbidden,
            "checks": [c.to_dict() for c in self.checks],
            "blockers": list(self.blockers),
            "warnings": list(self.warnings),
            "required_observation_roles": ["supervisor", "poller", "api"],
            "optional_operator_display_roles": ["ui"],
        }


def _port_open(host: str, port: int, timeout: float = 0.35) -> bool:
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True
    except OSError:
        return False


def _git_rev_parse(cwd: Path, *args: str) -> str | None:
    git = shutil.which("git.exe") or shutil.which("git")
    if not git:
        return None
    try:
        result = subprocess.run(
            [git, *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    text = (result.stdout or "").strip()
    return text or None


def _credential_present(environ: Mapping[str, str], keys: Sequence[str]) -> bool:
    return any(str(environ.get(key) or "").strip() for key in keys)


def evaluate_campaign_environment_preflight(
    *,
    root: Path | None = None,
    state_dir: Path | str | None = None,
    environ: Mapping[str, str] | None = None,
    require_ui_deps: bool = True,
    require_api_entrypoint: bool = True,
    check_opend: bool = True,
    campaign_id: str | None = None,
    observation_window_id: str | None = None,
) -> PreflightReport:
    """Evaluate environment readiness before ARM OBSERVATION.

    UI dependency absence is fail-visible (blocker when ``require_ui_deps``) so
    operators cannot arm into a campaign that cannot start :5173. Observation
    ingestion still treats UI as an optional *runtime role*; this check is about
    dependency readiness of the checkout, not a long-lived UI process.
    """

    imp_root = (root or ROOT).resolve()
    env = environ if environ is not None else os.environ
    report = PreflightReport()

    def add(
        name: str,
        status: str,
        *,
        required_for_arm: bool,
        detail: str,
        category: str,
    ) -> None:
        report.checks.append(
            CheckResult(
                name=name,
                status=status,
                required_for_arm=required_for_arm,
                detail=detail,
                category=category,
            )
        )
        if status == "FAIL" and required_for_arm:
            report.blockers.append(name)
        elif status in {"FAIL", "WARN"} and not required_for_arm:
            report.warnings.append(name)

    # --- git SHA / tree hash ---
    git_sha = _git_rev_parse(imp_root, "rev-parse", "HEAD")
    if git_sha:
        add("git_sha", "PASS", required_for_arm=False, detail=git_sha[:12], category="git")
    else:
        add(
            "git_sha",
            "WARN",
            required_for_arm=False,
            detail="git rev-parse HEAD unavailable",
            category="git",
        )
    tree_hash = _git_rev_parse(imp_root, "rev-parse", "HEAD^{tree}")
    if tree_hash:
        add(
            "tree_hash",
            "PASS",
            required_for_arm=False,
            detail=tree_hash[:12],
            category="git",
        )
    else:
        add(
            "tree_hash",
            "WARN",
            required_for_arm=False,
            detail="git tree hash unavailable",
            category="git",
        )

    # --- Python environment ---
    venv_nt = imp_root / ".venv" / "Scripts" / "python.exe"
    venv_posix = imp_root / ".venv" / "bin" / "python"
    if venv_nt.is_file() or venv_posix.is_file():
        add(
            "python_environment",
            "PASS",
            required_for_arm=True,
            detail="repository .venv present",
            category="python",
        )
    elif Path(sys.executable).is_file():
        add(
            "python_environment",
            "WARN",
            required_for_arm=False,
            detail="no .venv; using current interpreter",
            category="python",
        )
    else:
        add(
            "python_environment",
            "FAIL",
            required_for_arm=True,
            detail="Python environment missing",
            category="python",
        )

    # --- API entrypoint ---
    api_entrypoint = imp_root / "tools" / "ui1" / "run_ui_api.py"
    if require_api_entrypoint:
        if api_entrypoint.is_file():
            add(
                "api_entrypoint",
                "PASS",
                required_for_arm=True,
                detail="tools/ui1/run_ui_api.py present",
                category="api",
            )
        else:
            add(
                "api_entrypoint",
                "FAIL",
                required_for_arm=True,
                detail="API entrypoint missing",
                category="api",
            )

    # --- Node / UI deps ---
    node = shutil.which("node.exe") or shutil.which("node")
    npm = shutil.which("npm.cmd") or shutil.which("npm")
    node_modules = imp_root / "ui" / "node_modules"
    if node:
        add("node_executable", "PASS", required_for_arm=False, detail=node, category="ui")
    else:
        add(
            "node_executable",
            "FAIL" if require_ui_deps else "WARN",
            required_for_arm=require_ui_deps,
            detail="node not on PATH",
            category="ui",
        )
    if npm:
        add("npm_executable", "PASS", required_for_arm=False, detail=npm, category="ui")
    else:
        add(
            "npm_executable",
            "FAIL" if require_ui_deps else "WARN",
            required_for_arm=require_ui_deps,
            detail="npm not on PATH",
            category="ui",
        )
    if node_modules.is_dir():
        add(
            "ui_node_modules",
            "PASS",
            required_for_arm=require_ui_deps,
            detail="ui/node_modules present",
            category="ui",
        )
    else:
        add(
            "ui_node_modules",
            "FAIL" if require_ui_deps else "WARN",
            required_for_arm=require_ui_deps,
            detail="ui/node_modules absent; operator UI :5173 cannot start",
            category="ui",
        )

    # --- Ports (informational; in-use is WARN so arm can still proceed to recover) ---
    if _port_open(API_HOST, API_PORT):
        add(
            "api_port",
            "WARN",
            required_for_arm=False,
            detail=f"{API_HOST}:{API_PORT} already bound",
            category="ports",
        )
    else:
        add(
            "api_port",
            "PASS",
            required_for_arm=False,
            detail=f"{API_HOST}:{API_PORT} free",
            category="ports",
        )
    if _port_open(UI_HOST, UI_PORT):
        add(
            "ui_port",
            "WARN",
            required_for_arm=False,
            detail=f"{UI_HOST}:{UI_PORT} already bound",
            category="ports",
        )
    else:
        add(
            "ui_port",
            "PASS",
            required_for_arm=False,
            detail=f"{UI_HOST}:{UI_PORT} free",
            category="ports",
        )

    # --- State directory ---
    raw_state = str(state_dir or env.get("IMP_STATE_DIR") or "").strip()
    if not raw_state:
        add(
            "state_directory",
            "FAIL",
            required_for_arm=True,
            detail="IMP_STATE_DIR / state_dir required",
            category="state",
        )
    else:
        path = Path(raw_state).expanduser()
        try:
            path.mkdir(parents=True, exist_ok=True)
            probe = path / ".imp-preflight-write-probe"
            probe.write_text("ok\n", encoding="utf-8")
            probe.unlink(missing_ok=True)
            add(
                "state_directory",
                "PASS",
                required_for_arm=True,
                detail="writable",
                category="state",
            )
        except OSError as exc:
            add(
                "state_directory",
                "FAIL",
                required_for_arm=True,
                detail=f"not writable: {exc.__class__.__name__}",
                category="state",
            )

    # --- Provider capability / credentials presence (no values) ---
    finviz_present = _credential_present(
        env,
        ("FINVIZ_ELITE_AUTH", "FINVIZ_AUTH", "IMP_FINVIZ_ELITE_AUTH"),
    )
    add(
        "credentials_presence_finviz",
        "PASS" if finviz_present else "WARN",
        required_for_arm=False,
        detail="present" if finviz_present else "absent",
        category="credentials",
    )
    provider_flag = str(env.get("IMP_FINVIZ_LIVE") or "").strip()
    add(
        "provider_capability_finviz_flag",
        "PASS" if provider_flag in {"1", "true", "TRUE", "yes"} else "WARN",
        required_for_arm=False,
        detail=f"IMP_FINVIZ_LIVE={provider_flag or 'unset'}",
        category="provider",
    )

    # --- OpenD reachability (soft) ---
    if check_opend:
        if _port_open(OPEND_HOST, OPEND_PORT):
            add(
                "opend_reachability",
                "PASS",
                required_for_arm=False,
                detail=f"{OPEND_HOST}:{OPEND_PORT} accepting connections",
                category="opend",
            )
        else:
            add(
                "opend_reachability",
                "WARN",
                required_for_arm=False,
                detail=f"{OPEND_HOST}:{OPEND_PORT} not reachable",
                category="opend",
            )

    # --- Campaign manifest / observation window (declared intent) ---
    if campaign_id:
        add(
            "campaign_manifest_id",
            "PASS",
            required_for_arm=True,
            detail=str(campaign_id),
            category="campaign",
        )
    else:
        add(
            "campaign_manifest_id",
            "WARN",
            required_for_arm=False,
            detail="campaign_id not supplied to preflight",
            category="campaign",
        )
    if observation_window_id:
        add(
            "observation_window",
            "PASS",
            required_for_arm=True,
            detail=str(observation_window_id),
            category="campaign",
        )
    else:
        add(
            "observation_window",
            "WARN",
            required_for_arm=False,
            detail="observation_window_id not supplied to preflight",
            category="campaign",
        )

    # --- Role / authority contracts ---
    add(
        "required_roles_contract",
        "PASS",
        required_for_arm=False,
        detail="supervisor,poller,api required; ui optional operator display",
        category="roles",
    )
    add(
        "execution_authority",
        "PASS",
        required_for_arm=True,
        detail="BLOCKED (observation arm never grants live submit)",
        category="authority",
    )

    report.ready_to_arm = len(report.blockers) == 0
    report.blockers = list(dict.fromkeys(report.blockers))
    report.warnings = list(dict.fromkeys(report.warnings))
    return report


def preflight_to_json(report: PreflightReport) -> str:
    return json.dumps(report.to_dict(), indent=2, sort_keys=True)


__all__ = [
    "CheckResult",
    "EVIDENCE_CLASS",
    "PreflightReport",
    "SCHEMA_VERSION",
    "evaluate_campaign_environment_preflight",
    "preflight_to_json",
]
