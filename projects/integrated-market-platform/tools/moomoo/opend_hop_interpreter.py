"""One-interpreter Path A hop extras — vendor SDK in the IMP venv.

The hop needs IMP runtime (sklearn) **and** vendor ``moomoo-api`` with
``OpenQuoteContext``. Mixing IMP ``.venv`` with another venv's
``site-packages`` via ``PYTHONPATH`` is not required after
``python tools/imp.py env install-opend``. ``tools/moomoo`` is never the
vendor SDK. Missing SDK stays fail-closed; this module never synthesizes ticks
and never enables Live.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from typing import Any

_TOOLS_MOOMOO_DIR = Path(__file__).resolve().parent
REQUIREMENTS_OPEND = _TOOLS_MOOMOO_DIR / "requirements-opend.txt"
VENDOR_SDK_DISTRIBUTION = "moomoo-api"
VENDOR_SDK_PIN = "10.10.7008"
HOP_RUNTIME_MODULE = "sklearn"

HOP_SKLEARN_MISSING = "HOP_SKLEARN_MISSING"
MOOMOO_SDK_MISSING = "MOOMOO_SDK_MISSING"
HOP_MIXED_FOREIGN_VENV = "HOP_MIXED_FOREIGN_VENV"
PIP_MISSING = "PIP_MISSING"


def opend_extra_requirements_path() -> Path:
    return REQUIREMENTS_OPEND


def vendor_sdk_pin() -> str:
    return f"{VENDOR_SDK_DISTRIBUTION}=={VENDOR_SDK_PIN}"


def _module_importable(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError, ModuleNotFoundError):
        return False


def _module_lives_in_this_interpreter(module: Any) -> bool:
    filename = getattr(module, "__file__", None)
    if not filename:
        return False
    try:
        path = Path(filename).resolve()
        prefix = Path(sys.prefix).resolve()
    except OSError:
        return False
    return prefix == path or prefix in path.parents


def _foreign_moomoo_api_test_on_path() -> bool:
    for entry in sys.path:
        if not entry:
            continue
        normalized = str(entry).replace("\\", "/").casefold()
        if "moomoo-api-test" in normalized:
            return True
    return False


def _load_transport():
    path = Path(__file__).with_name("opend_quote_transport.py")
    spec = importlib.util.spec_from_file_location("imp_opend_quote_transport_hop", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("opend quote transport is missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def diagnose_hop_interpreter() -> dict[str, Any]:
    """Secret-free hop interpreter status. Never a tick and never Live."""

    sklearn_ok = _module_importable(HOP_RUNTIME_MODULE)
    transport = _load_transport()
    sdk = transport.load_vendor_sdk()
    vendor_ok = sdk is not None and transport.is_vendor_sdk(sdk)
    in_this_interpreter = bool(vendor_ok and _module_lives_in_this_interpreter(sdk))
    mixed = _foreign_moomoo_api_test_on_path() or (vendor_ok and not in_this_interpreter)
    if not vendor_ok:
        reason = MOOMOO_SDK_MISSING
    elif not sklearn_ok:
        reason = HOP_SKLEARN_MISSING
    elif mixed:
        reason = HOP_MIXED_FOREIGN_VENV
    else:
        reason = None
    ready = bool(sklearn_ok and vendor_ok and in_this_interpreter and not mixed)
    return {
        "mixed_foreign_venv": mixed,
        "ready": ready,
        "reason_code": reason,
        "same_interpreter": not mixed,
        "secrets_included": False,
        "sklearn": sklearn_ok,
        "vendor_distribution": VENDOR_SDK_DISTRIBUTION,
        "vendor_pin": VENDOR_SDK_PIN,
        "vendor_sdk": vendor_ok,
        "vendor_sdk_in_this_interpreter": in_this_interpreter,
        "vendor_sdk_is_opend_quote_context": vendor_ok,
    }


def _pip_importable(python: Path, runner: Any) -> bool:
    probe = runner(
        [str(python), "-c", "import pip"],
        check=False,
        capture_output=True,
        text=True,
    )
    return int(getattr(probe, "returncode", 1) or 0) == 0


def install_opend_extra(*, python: Path, runner: Any | None = None) -> dict[str, Any]:
    """Install the optional vendor SDK into ``python`` (the IMP interpreter).

    Does not enable Live, does not start OpenD, and does not mock ticks.
    """

    requirements = opend_extra_requirements_path()
    if not requirements.is_file():
        return {
            "secrets_included": False,
            "status": "BLOCKED",
            "error": "opend extra requirements file is missing",
            "vendor_pin": VENDOR_SDK_PIN,
        }
    run = runner if runner is not None else subprocess.run
    if not _pip_importable(python, run):
        return {
            "python": str(python),
            "requirements": str(requirements),
            "secrets_included": False,
            "status": "BLOCKED",
            "reason_code": PIP_MISSING,
            "error": (
                "interpreter has no pip module (common after uv venv); "
                "install pip then retry: uv pip install pip "
                "(or python -m ensurepip --upgrade)"
            ),
            "vendor_distribution": VENDOR_SDK_DISTRIBUTION,
            "vendor_pin": VENDOR_SDK_PIN,
        }
    command = [str(python), "-m", "pip", "install", "-r", str(requirements)]
    completed = run(command, check=False, capture_output=True, text=True)
    status = "READY" if int(getattr(completed, "returncode", 1) or 0) == 0 else "BLOCKED"
    payload: dict[str, Any] = {
        "python": str(python),
        "requirements": str(requirements),
        "secrets_included": False,
        "status": status,
        "vendor_distribution": VENDOR_SDK_DISTRIBUTION,
        "vendor_pin": VENDOR_SDK_PIN,
    }
    if status != "READY":
        payload["error"] = "opend extra install failed"
    return payload


__all__ = [
    "HOP_MIXED_FOREIGN_VENV",
    "HOP_SKLEARN_MISSING",
    "MOOMOO_SDK_MISSING",
    "PIP_MISSING",
    "REQUIREMENTS_OPEND",
    "VENDOR_SDK_DISTRIBUTION",
    "VENDOR_SDK_PIN",
    "diagnose_hop_interpreter",
    "install_opend_extra",
    "opend_extra_requirements_path",
    "vendor_sdk_pin",
]
