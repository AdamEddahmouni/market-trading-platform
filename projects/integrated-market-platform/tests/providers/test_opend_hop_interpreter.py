"""One-interpreter OpenD hop extra — vendor SDK in the IMP venv.

Never mocks ticks. Missing vendor ``OpenQuoteContext`` stays fail-closed.
``tools/moomoo`` is not the SDK. Live stays off.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from tools.moomoo.opend_hop_interpreter import (
    HOP_MIXED_FOREIGN_VENV,
    MOOMOO_SDK_MISSING,
    PIP_MISSING,
    REQUIREMENTS_OPEND,
    VENDOR_SDK_DISTRIBUTION,
    VENDOR_SDK_PIN,
    diagnose_hop_interpreter,
    install_opend_extra,
    vendor_sdk_pin,
)
from tools.moomoo.opend_quote_transport import MOOMOO_SDK_MISSING as TRANSPORT_SDK_MISSING
from tools.moomoo.opend_quote_transport import fetch_snapshot, sdk_available


class OpenDHopInterpreterTests(unittest.TestCase):
    def test_opend_extra_pins_vendor_sdk_not_tools_package(self) -> None:
        text = REQUIREMENTS_OPEND.read_text(encoding="utf-8")
        self.assertTrue(REQUIREMENTS_OPEND.is_file())
        self.assertIn(f"{VENDOR_SDK_DISTRIBUTION}=={VENDOR_SDK_PIN}", text)
        self.assertEqual(vendor_sdk_pin(), f"{VENDOR_SDK_DISTRIBUTION}=={VENDOR_SDK_PIN}")
        self.assertNotIn("tools/moomoo", text.split("moomoo-api", 1)[0])

    def test_cloud_and_default_bootstrap_do_not_install_vendor_sdk(self) -> None:
        cloud = (_ROOT / ".cursor" / "install-cloud-deps.sh").read_text(encoding="utf-8")
        bootstrap = (_ROOT / "tools" / "platform" / "bootstrap.py").read_text(encoding="utf-8")
        self.assertNotIn("moomoo-api", cloud)
        self.assertNotIn("moomoo-api", bootstrap)

    def test_diagnose_without_vendor_sdk_is_fail_closed_not_a_tick(self) -> None:
        report = diagnose_hop_interpreter()
        self.assertFalse(report["secrets_included"])
        self.assertFalse(report["vendor_sdk_is_opend_quote_context"] and not report["vendor_sdk"])
        if not sdk_available():
            self.assertFalse(report["vendor_sdk"])
            self.assertFalse(report["vendor_sdk_is_opend_quote_context"])
            self.assertFalse(report["ready"])
            self.assertEqual(report["reason_code"], MOOMOO_SDK_MISSING)
            payload = fetch_snapshot("AAPL", host="127.0.0.1", port=11111)
            self.assertEqual(payload["reason_code"], TRANSPORT_SDK_MISSING)
            self.assertIsNone(payload["row"])

    def test_tools_moomoo_shadow_is_not_vendor_sdk(self) -> None:
        from types import ModuleType

        from tools.moomoo import opend_quote_transport as transport

        self.assertFalse((_ROOT / "tools" / "moomoo" / "__init__.py").is_file())
        self.assertFalse(transport.is_vendor_sdk(ModuleType("shadow_moomoo")))
        with patch.object(transport, "load_vendor_sdk", return_value=None):
            self.assertFalse(transport.sdk_available())

    def test_foreign_moomoo_api_test_path_is_mixed_not_required(self) -> None:
        fake = r"C:\Users\adame\moomoo-api-test\.venv\Lib\site-packages"
        with patch.object(sys, "path", [fake, *list(sys.path)]):
            report = diagnose_hop_interpreter()
        self.assertTrue(report["mixed_foreign_venv"])
        self.assertFalse(report["same_interpreter"])
        self.assertFalse(report["ready"])
        if report["vendor_sdk"]:
            self.assertEqual(report["reason_code"], HOP_MIXED_FOREIGN_VENV)
        else:
            self.assertEqual(report["reason_code"], MOOMOO_SDK_MISSING)
        self.assertFalse(report["secrets_included"])
        self.assertNotIn("Users", str(report))
        self.assertNotIn(fake, str(report))

    def test_install_opend_extra_targets_one_interpreter_and_pin_file(self) -> None:
        python = Path("/imp/.venv/bin/python")
        captured: dict[str, object] = {}

        def fake_run(command, check=False, capture_output=False, text=False):  # noqa: ARG001
            captured["command"] = list(command)
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        report = install_opend_extra(python=python, runner=fake_run)
        command = captured["command"]
        self.assertEqual(command[0], str(python))
        self.assertEqual(command[1:5], ["-m", "pip", "install", "-r"])
        self.assertEqual(Path(command[5]), REQUIREMENTS_OPEND)
        self.assertEqual(report["status"], "READY")
        self.assertEqual(report["vendor_pin"], VENDOR_SDK_PIN)
        self.assertFalse(report["secrets_included"])
        self.assertNotIn("IMP_MOOMOO_LIVE", report)

    def test_install_opend_extra_fail_closed_on_pip_error(self) -> None:
        def fake_run(command, check=False, capture_output=False, text=False):  # noqa: ARG001
            if len(command) >= 3 and command[-1] == "import pip":
                return SimpleNamespace(returncode=0, stdout="", stderr="")
            return SimpleNamespace(returncode=1, stdout="", stderr="denied")

        report = install_opend_extra(python=Path("python"), runner=fake_run)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["error"], "opend extra install failed")
        self.assertFalse(report["secrets_included"])

    def test_install_opend_extra_blocked_when_pip_module_missing(self) -> None:
        pip_probe_ran = False
        install_attempted = False

        def fake_run(command, check=False, capture_output=False, text=False):  # noqa: ARG001
            nonlocal pip_probe_ran, install_attempted
            if command[-2:] == ["-c", "import pip"]:
                pip_probe_ran = True
                return SimpleNamespace(returncode=1, stdout="", stderr="No module named pip")
            install_attempted = True
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        python = Path("/imp/.venv/bin/python")
        report = install_opend_extra(python=python, runner=fake_run)
        self.assertTrue(pip_probe_ran)
        self.assertFalse(install_attempted)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["reason_code"], PIP_MISSING)
        self.assertIn("uv pip install pip", report["error"])
        self.assertEqual(report["python"], str(python))
        self.assertFalse(report["secrets_included"])


class OpenDHopCliInterpreterTests(unittest.TestCase):
    def test_hop_cli_emits_secret_free_interpreter_status(self) -> None:
        from io import StringIO
        import json
        import os

        from tools.path_a_prospective_run import main as path_a_cli_main

        stdout = StringIO()
        with patch.dict(os.environ, {"IMP_MOOMOO_HOST": "127.0.0.1", "IMP_MOOMOO_PORT": "1"}):
            with patch("tools.moomoo.opend_hop_interpreter._load_transport") as load_transport:
                transport = load_transport.return_value
                transport.load_vendor_sdk.return_value = None
                transport.is_vendor_sdk.return_value = False
                with patch("sys.stdout", stdout):
                    code = path_a_cli_main(["--symbol", "AAPL", "--mode", "paper"])
        self.assertEqual(code, 0)
        dumped = stdout.getvalue()
        payload = json.loads(dumped)
        hop = payload["hop_interpreter"]
        self.assertFalse(hop["secrets_included"])
        self.assertEqual(hop["vendor_distribution"], VENDOR_SDK_DISTRIBUTION)
        self.assertEqual(hop["vendor_pin"], VENDOR_SDK_PIN)
        self.assertEqual(hop["vendor_sdk"], hop["vendor_sdk_is_opend_quote_context"])
        self.assertFalse(hop["vendor_sdk"])
        self.assertEqual(hop["reason_code"], MOOMOO_SDK_MISSING)
        self.assertNotIn("password", dumped.casefold())
        self.assertNotIn("moomoo-api-test", dumped)
        self.assertNotIn("EMPIRICAL_ACTIVE", dumped)
        self.assertNotIn("APPDATA", dumped)


if __name__ == "__main__":
    unittest.main()
