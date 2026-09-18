"""Item 9 next-RTH preflight — read-only; never starts prospective --poll."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.paper.calibration.item9_next_rth_preflight import (  # noqa: E402
    DISPOSITION_ACTIVE_COLLECTOR_EXISTS,
    DISPOSITION_NOT_RTH,
    DISPOSITION_OUTPUT_PATH_INVALID,
    DISPOSITION_PROVIDER_UNAVAILABLE,
    DISPOSITION_READY_TO_COLLECT,
    DISPOSITION_WRONG_RUNTIME,
    FROZEN_COLLECTOR_AUTHORITY_SHA,
    Item9NextRthPreflightOptions,
    detect_active_item9_prospective_collector,
    main,
    run_item9_next_rth_preflight,
)
from market_platform_foundation.providers.equity_quote_selection import OpenDReadiness  # noqa: E402

T_RTH_CLOSED_NS = 1_700_000_000_000_000_000
T_RTH_OPEN_NS = 1_789_394_400_000_000_000


def _opend_ok() -> OpenDReadiness:
    return OpenDReadiness(host="127.0.0.1", port=11111, loopback=True, reachable=True)


def _opend_down() -> OpenDReadiness:
    return OpenDReadiness(host="127.0.0.1", port=11111, loopback=True, reachable=False)


class Item9NextRthPreflightTests(unittest.TestCase):
    def test_detect_active_collector_ignores_preflight(self) -> None:
        lines = [
            "python tools/item9_next_rth_preflight.py next-rth-preflight --json",
            "python tools/moomoo/opend_bar_1m_prospective_proof.py prospective --poll",
        ]
        active, matches = detect_active_item9_prospective_collector(command_lines=tuple(lines))
        self.assertTrue(active)
        self.assertEqual(len(matches), 1)

    def test_not_rth_off_hours_software_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            imp_root = Path(tmp)
            receipt_dir = imp_root / "receipts"
            with (
                mock.patch(
                    "market_platform_foundation.paper.calibration.item9_next_rth_preflight."
                    "resolve_runtime_git_sha",
                    return_value=FROZEN_COLLECTOR_AUTHORITY_SHA,
                ),
                mock.patch(
                    "market_platform_foundation.paper.calibration.item9_next_rth_preflight."
                    "opend_readiness",
                    return_value=_opend_ok(),
                ),
                mock.patch(
                    "market_platform_foundation.paper.calibration.item9_next_rth_preflight."
                    "resolve_frozen_collector_imp_root",
                    return_value=imp_root,
                ),
                mock.patch(
                    "market_platform_foundation.paper.calibration.item9_next_rth_preflight."
                    "read_git_head",
                    return_value=FROZEN_COLLECTOR_AUTHORITY_SHA,
                ),
            ):
                report = run_item9_next_rth_preflight(
                    imp_root,
                    options=Item9NextRthPreflightOptions(
                        receipt_dir=receipt_dir,
                        now_ns=T_RTH_CLOSED_NS,
                    ),
                )
        self.assertEqual(report["disposition"], DISPOSITION_NOT_RTH)
        self.assertTrue(report["does_not_start_collector"])
        self.assertFalse(report["readiness"]["rth_active"])
        self.assertEqual(report["active_collector"]["process_probe_status"], "NOT_RUN")

    def test_wrong_runtime_when_current_sha_not_frozen(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            imp_root = Path(tmp)
            report = run_item9_next_rth_preflight(
                imp_root,
                options=Item9NextRthPreflightOptions(now_ns=T_RTH_CLOSED_NS),
                active_collector_probe=lambda: (False, []),
            )
        self.assertEqual(report["disposition"], DISPOSITION_WRONG_RUNTIME)

    def test_output_path_refuses_historical_development_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            imp_root = Path(tmp)
            bad_dir = imp_root / "artifacts" / "historical-rth-development" / "receipts"
            report = run_item9_next_rth_preflight(
                imp_root,
                options=Item9NextRthPreflightOptions(receipt_dir=bad_dir, now_ns=T_RTH_CLOSED_NS),
                active_collector_probe=lambda: (False, []),
            )
        self.assertEqual(report["disposition"], DISPOSITION_OUTPUT_PATH_INVALID)

    def test_provider_unreachable_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            imp_root = Path(tmp)
            receipt_dir = imp_root / "receipts"
            with (
                mock.patch(
                    "market_platform_foundation.paper.calibration.item9_next_rth_preflight."
                    "resolve_runtime_git_sha",
                    return_value=FROZEN_COLLECTOR_AUTHORITY_SHA,
                ),
                mock.patch(
                    "market_platform_foundation.paper.calibration.item9_next_rth_preflight."
                    "opend_readiness",
                    return_value=_opend_down(),
                ),
                mock.patch(
                    "market_platform_foundation.paper.calibration.item9_next_rth_preflight."
                    "resolve_frozen_collector_imp_root",
                    return_value=imp_root,
                ),
                mock.patch(
                    "market_platform_foundation.paper.calibration.item9_next_rth_preflight."
                    "read_git_head",
                    return_value=FROZEN_COLLECTOR_AUTHORITY_SHA,
                ),
            ):
                report = run_item9_next_rth_preflight(
                    imp_root,
                    options=Item9NextRthPreflightOptions(
                        receipt_dir=receipt_dir,
                        now_ns=T_RTH_OPEN_NS,
                    ),
                    active_collector_probe=lambda: (False, []),
                )
        self.assertEqual(report["disposition"], DISPOSITION_PROVIDER_UNAVAILABLE)

    def test_active_collector_blocks_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            imp_root = Path(tmp)
            receipt_dir = imp_root / "receipts"
            with (
                mock.patch(
                    "market_platform_foundation.paper.calibration.item9_next_rth_preflight."
                    "resolve_runtime_git_sha",
                    return_value=FROZEN_COLLECTOR_AUTHORITY_SHA,
                ),
                mock.patch(
                    "market_platform_foundation.paper.calibration.item9_next_rth_preflight."
                    "opend_readiness",
                    return_value=_opend_ok(),
                ),
                mock.patch(
                    "market_platform_foundation.paper.calibration.item9_next_rth_preflight."
                    "resolve_frozen_collector_imp_root",
                    return_value=imp_root,
                ),
                mock.patch(
                    "market_platform_foundation.paper.calibration.item9_next_rth_preflight."
                    "read_git_head",
                    return_value=FROZEN_COLLECTOR_AUTHORITY_SHA,
                ),
            ):
                report = run_item9_next_rth_preflight(
                    imp_root,
                    options=Item9NextRthPreflightOptions(
                        receipt_dir=receipt_dir,
                        now_ns=T_RTH_OPEN_NS,
                    ),
                    active_collector_probe=lambda: (True, ["prospective --poll"]),
                )
        self.assertEqual(report["disposition"], DISPOSITION_ACTIVE_COLLECTOR_EXISTS)

    def test_ready_to_collect_during_rth_with_frozen_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            imp_root = Path(tmp)
            receipt_dir = imp_root / "receipts"
            with (
                mock.patch(
                    "market_platform_foundation.paper.calibration.item9_next_rth_preflight."
                    "resolve_runtime_git_sha",
                    return_value=FROZEN_COLLECTOR_AUTHORITY_SHA,
                ),
                mock.patch(
                    "market_platform_foundation.paper.calibration.item9_next_rth_preflight."
                    "opend_readiness",
                    return_value=_opend_ok(),
                ),
                mock.patch(
                    "market_platform_foundation.paper.calibration.item9_next_rth_preflight."
                    "resolve_frozen_collector_imp_root",
                    return_value=imp_root,
                ),
                mock.patch(
                    "market_platform_foundation.paper.calibration.item9_next_rth_preflight."
                    "read_git_head",
                    return_value=FROZEN_COLLECTOR_AUTHORITY_SHA,
                ),
            ):
                report = run_item9_next_rth_preflight(
                    imp_root,
                    options=Item9NextRthPreflightOptions(
                        receipt_dir=receipt_dir,
                        now_ns=T_RTH_OPEN_NS,
                    ),
                    active_collector_probe=lambda: (False, []),
                )
        self.assertEqual(report["disposition"], DISPOSITION_READY_TO_COLLECT)
        self.assertIn("corpus-status", report["post_run_corpus_status_command"])

    def test_cli_not_rth_exit_zero_without_starting_collector(self) -> None:
        with mock.patch(
            "market_platform_foundation.paper.calibration.item9_next_rth_preflight."
            "run_item9_next_rth_preflight",
            return_value={
                "disposition": DISPOSITION_NOT_RTH,
                "blockers": [],
                "reason_codes": [],
                "does_not_start_collector": True,
            },
        ):
            code = main(["next-rth-preflight", "--json", "--now-ns", str(T_RTH_CLOSED_NS)])
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
