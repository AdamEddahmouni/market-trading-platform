"""Path A Monday RTH preflight — software only, no hop, no mint."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.strategy.path_a_rth_preflight import (  # noqa: E402
    PathARthPreflightOptions,
    run_path_a_rth_preflight,
)
from tools.moomoo.opend_hop_interpreter import PIP_MISSING  # noqa: E402

# Monday 2026-09-14 14:00 UTC — US cash RTH (10:00 ET).
T_RTH_OPEN_NS = 1_789_394_400_000_000_000
# Sunday 2026-09-13 18:00 UTC — closed.
T_RTH_CLOSED_NS = 1_789_322_400_000_000_000


def _ready_hop() -> dict:
    return {
        "mixed_foreign_venv": False,
        "ready": True,
        "reason_code": None,
        "same_interpreter": True,
        "secrets_included": False,
        "sklearn": True,
        "vendor_distribution": "moomoo-api",
        "vendor_pin": "10.10.7008",
        "vendor_sdk": True,
        "vendor_sdk_in_this_interpreter": True,
        "vendor_sdk_is_opend_quote_context": True,
    }


class PathARthPreflightTests(unittest.TestCase):
    def test_market_closed_when_rth_closed_and_software_ready(self) -> None:
        report = run_path_a_rth_preflight(
            options=PathARthPreflightOptions(now_ns=T_RTH_CLOSED_NS, probe_local_opend=False),
            python=Path("/imp/.venv/bin/python"),
            pip_runner=lambda *a, **k: SimpleNamespace(returncode=0, stdout="", stderr=""),
            hop_interpreter=lambda: _ready_hop(),
            opend_diagnose=lambda **_: {"status": "READY", "ready_for_live_observational": True},
        )
        self.assertEqual(report["disposition"], "MARKET_CLOSED")
        self.assertTrue(report["us_equity_rth_open"] is False)
        self.assertIn("US_EQUITY_RTH_CLOSED", report["reason_codes"])
        self.assertFalse(report["secrets_included"])

    def test_pip_missing_is_missing_not_market_closed(self) -> None:
        report = run_path_a_rth_preflight(
            options=PathARthPreflightOptions(now_ns=T_RTH_OPEN_NS, probe_local_opend=False),
            python=Path("/imp/.venv/bin/python"),
            pip_runner=lambda *a, **k: SimpleNamespace(returncode=1, stdout="", stderr="no pip"),
            hop_interpreter=lambda: _ready_hop(),
            opend_diagnose=lambda **_: {"status": "READY", "ready_for_live_observational": True},
        )
        self.assertEqual(report["disposition"], "MISSING")
        self.assertIn(PIP_MISSING, report["reason_codes"])
        self.assertEqual(report["checks"]["pip"]["reason_code"], PIP_MISSING)

    def test_invalid_moomoo_config_keys_are_missing(self) -> None:
        env = {"IMP_MOOMOO_PORT": "not-a-port"}
        report = run_path_a_rth_preflight(
            options=PathARthPreflightOptions(now_ns=T_RTH_OPEN_NS, probe_local_opend=False),
            python=Path("/imp/.venv/bin/python"),
            pip_runner=lambda *a, **k: SimpleNamespace(returncode=0, stdout="", stderr=""),
            hop_interpreter=lambda: _ready_hop(),
            opend_diagnose=lambda **_: {"status": "READY", "ready_for_live_observational": True},
            environ=env,
        )
        self.assertEqual(report["disposition"], "MISSING")
        self.assertTrue(any(code.startswith("CONFIG_KEY_INVALID:") for code in report["reason_codes"]))

    def test_live_gate_blocks_disposition(self) -> None:
        report = run_path_a_rth_preflight(
            options=PathARthPreflightOptions(now_ns=T_RTH_OPEN_NS, probe_local_opend=False),
            python=Path("/imp/.venv/bin/python"),
            pip_runner=lambda *a, **k: SimpleNamespace(returncode=0, stdout="", stderr=""),
            hop_interpreter=lambda: _ready_hop(),
            opend_diagnose=lambda **_: {"status": "READY", "ready_for_live_observational": True},
            environ={"IMP_MOOMOO_LIVE": "1"},
        )
        self.assertEqual(report["disposition"], "BLOCKED")
        self.assertIn("IMP_MOOMOO_LIVE", report["reason_codes"])

    def test_operator_forecast_path_missing_is_missing(self) -> None:
        missing = Path("/no/such/forecast.json")
        report = run_path_a_rth_preflight(
            options=PathARthPreflightOptions(
                now_ns=T_RTH_OPEN_NS,
                probe_local_opend=False,
                forecast_path=str(missing),
            ),
            python=Path("/imp/.venv/bin/python"),
            pip_runner=lambda *a, **k: SimpleNamespace(returncode=0, stdout="", stderr=""),
            hop_interpreter=lambda: _ready_hop(),
            opend_diagnose=lambda **_: {"status": "READY", "ready_for_live_observational": True},
        )
        self.assertEqual(report["disposition"], "MISSING")
        self.assertIn("FORECAST_PATH_MISSING", report["reason_codes"])

    def test_yahoo_never_l1_and_finviz_overlay_only(self) -> None:
        report = run_path_a_rth_preflight(
            options=PathARthPreflightOptions(now_ns=T_RTH_OPEN_NS, probe_local_opend=False),
            python=Path("/imp/.venv/bin/python"),
            pip_runner=lambda *a, **k: SimpleNamespace(returncode=0, stdout="", stderr=""),
            hop_interpreter=lambda: _ready_hop(),
            opend_diagnose=lambda **_: {"status": "READY", "ready_for_live_observational": True},
        )
        yahoo = report["checks"]["yahoo_never_l1"]
        self.assertTrue(yahoo["ok"])
        self.assertFalse(yahoo["yahoo_is_primary"])
        self.assertTrue(yahoo["yahoo_is_overlay_only"])
        finviz = report["checks"]["finviz_overlay_only"]
        self.assertTrue(finviz["overlay_only"])

    def test_cli_emits_json_without_secrets(self) -> None:
        from tools.path_a_rth_preflight import main as cli_main

        stdout = StringIO()
        with patch(
            "market_platform_foundation.strategy.path_a_rth_preflight.run_path_a_rth_preflight",
            return_value={
                "disposition": "MARKET_CLOSED",
                "secrets_included": False,
                "reason_codes": [],
                "checks": {},
            },
        ):
            with patch("sys.stdout", stdout):
                code = cli_main(["--now-ns", str(T_RTH_CLOSED_NS)])
        self.assertEqual(code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["disposition"], "MARKET_CLOSED")

    def test_stale_moomoo_probe_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            probe_path = Path(tmp) / "capability-report.json"
            old_ns = T_RTH_OPEN_NS - (90000 * 1_000_000_000)
            probe_path.write_text(
                json.dumps({"observed_at_ns": old_ns}),
                encoding="utf-8",
            )
            with patch(
                "market_platform_foundation.strategy.path_a_rth_preflight.probe_report_path",
                return_value=probe_path,
            ):
                with patch(
                    "market_platform_foundation.strategy.path_a_rth_preflight.probe_staleness_seconds",
                    return_value=86400,
                ):
                    report = run_path_a_rth_preflight(
                        options=PathARthPreflightOptions(now_ns=T_RTH_OPEN_NS, probe_local_opend=False),
                        python=Path("/imp/.venv/bin/python"),
                        pip_runner=lambda *a, **k: SimpleNamespace(returncode=0, stdout="", stderr=""),
                        hop_interpreter=lambda: _ready_hop(),
                        opend_diagnose=lambda **_: {
                            "status": "READY",
                            "ready_for_live_observational": True,
                        },
                    )
        self.assertEqual(report["disposition"], "STALE")
        self.assertIn("MOOMOO_PROBE_STALE", report["reason_codes"])


if __name__ == "__main__":
    unittest.main()
