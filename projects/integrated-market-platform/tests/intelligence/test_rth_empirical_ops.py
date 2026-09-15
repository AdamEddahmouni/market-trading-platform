"""RTH empirical ops command center — software-only coordination tests."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.paper_forward_bridge.ftep_integrity import (  # noqa: E402
    FTEP_V1_002_EXPECTED_FINGERPRINT,
)
from market_platform_foundation.operations.rth_empirical_ops import (  # noqa: E402
    ACCEPTANCE_LABEL_READY,
    ARTIFACT_KIND_PREFLIGHT,
    run_rth_empirical_observational_dry_run,
    run_rth_empirical_ops_preflight,
)
from market_platform_foundation.paper.calibration.bar_ohlcv_prospective_proof import (  # noqa: E402
    READINESS_RTH_REQUIRED,
)

T_RTH_CLOSED_NS = 1_789_322_400_000_000_000

_PREFLIGHT_REQUIRED_KEYS = frozenset(
    {
        "artifact_kind",
        "schema_version",
        "acceptance_label",
        "runtime_git_sha",
        "canonical_imp_state_dir",
        "ftep_integrity",
        "governed_session_count",
        "empirical_lock_count",
        "rth_status",
        "opend_reachability",
        "moomoo_auth",
        "moomoo_entitlements",
        "finviz_credentials",
        "finviz_observational_gate",
        "prospective_catalyst_gate",
        "item7_collector_readiness",
        "item9_tool_readiness",
        "paper_comparator",
        "secrets_included",
    }
)


def _finviz_preflight_ok(*, rth_open: bool) -> dict:
    return {
        "disposition": "READY" if rth_open else "SOFTWARE_READY_RTH_REQUIRED",
        "blockers": [],
        "finviz": {"finviz_login_json_paths": ["/secret/path/login.json"]},
    }


def _status_ok(rth_open: bool) -> dict:
    return {
        "us_equity_rth_open": rth_open,
        "governed_session_count": 2,
        "empirical_lock_count": 0,
        "manifest_fingerprint": FTEP_V1_002_EXPECTED_FINGERPRINT,
        "signal_only_authorized": True,
        "campaign_readiness_disposition": "READY",
    }


def _opts(**kwargs: object) -> object:
    defaults = {
        "campaign_slug": "FTEP-V1-002",
        "now_ns": T_RTH_CLOSED_NS,
        "training_cutoff_ns": None,
        "instrument_id": "AAPL",
        "write_run_artifact": False,
    }
    defaults.update(kwargs)
    return type("O", (), defaults)()


class RthEmpiricalOpsTests(unittest.TestCase):
    _ENV_KEYS = ("IMP_STATE_DIR", "IMP_PERSIST_STATE", "IMP_FINVIZ_LIVE", "IMP_FTEP_PROSPECTIVE_CATALYST_INGRESS")

    def setUp(self) -> None:
        self._saved = {k: os.environ.get(k) for k in self._ENV_KEYS}

    def tearDown(self) -> None:
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_preflight_json_schema_keys_and_redaction(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_dir = Path(tmp) / "state"
            state_dir.mkdir()
            (state_dir / "imp-state.sqlite3").write_text("", encoding="utf-8")
            os.environ["IMP_STATE_DIR"] = str(state_dir)
            with (
                patch(
                    "market_platform_foundation.operations.rth_empirical_ops.run_ftep_finviz_prospective_preflight",
                    return_value=_finviz_preflight_ok(rth_open=False),
                ),
                patch(
                    "market_platform_foundation.operations.rth_empirical_ops.collect_ftep_integrity_checks",
                    return_value={"disposition": "PASS"},
                ),
                patch(
                    "market_platform_foundation.operations.rth_empirical_ops.collect_ftep_campaign_status",
                    return_value=_status_ok(rth_open=False),
                ),
                patch(
                    "market_platform_foundation.operations.rth_empirical_ops._finviz_credential_presence",
                    return_value={
                        "finviz_login": "PRESENT",
                        "finviz_token_file": "ABSENT",
                        "finviz_token_configured": "VALID",
                    },
                ),
                patch(
                    "market_platform_foundation.operations.rth_empirical_ops.run_governed_corpus_collection_status",
                    return_value=(
                        type(
                            "Report",
                            (),
                            {
                                "to_dict": lambda self: {
                                    "status": "ITEM7_REAL_CORPUS_COLLECTION_SOFTWARE_READY",
                                    "acceptance_label": "ITEM7_REAL_CORPUS_COLLECTION_SOFTWARE_READY",
                                    "market_rth_open": False,
                                    "blockers": (),
                                },
                            },
                        )(),
                        (),
                        object(),
                        object(),
                    ),
                ),
                patch(
                    "market_platform_foundation.operations.rth_empirical_ops._moomoo_auth_entitlements",
                    return_value=({"quote_login": "UNAVAILABLE", "sdk": "ABSENT"}, {"us_equity_l1": "UNAVAILABLE"}),
                ),
            ):
                report = run_rth_empirical_ops_preflight(ROOT, options=_opts(), env={})
            self.assertEqual(report["artifact_kind"], ARTIFACT_KIND_PREFLIGHT)
            self.assertTrue(_PREFLIGHT_REQUIRED_KEYS <= set(report))
            self.assertFalse(report["secrets_included"])
            delegated = json.dumps(report["delegated_preflight"])
            self.assertNotIn("/secret/path/login.json", delegated)
            self.assertEqual(report["acceptance_label"], ACCEPTANCE_LABEL_READY)
            self.assertEqual(report["disposition"], READINESS_RTH_REQUIRED)

    def test_run_observational_closed_market_rth_required(self) -> None:
        with patch(
            "market_platform_foundation.operations.rth_empirical_ops.collect_ftep_catalyst_watch",
            return_value={
                "artifact_kind": "ftep_catalyst_watch_report",
                "dry_run": True,
                "watch_mode": "FIXTURE_SMOKE",
                "disposition": "PASS",
            },
        ), patch(
            "market_platform_foundation.operations.rth_empirical_ops.run_governed_corpus_collection_status",
            return_value=(
                type("R", (), {"status": "S", "acceptance_label": "A", "market_rth_open": False})(),
                (),
                object(),
                object(),
            ),
        ):
            payload = run_rth_empirical_observational_dry_run(ROOT, options=_opts())
        self.assertEqual(payload["reason_code"], READINESS_RTH_REQUIRED)
        self.assertFalse(payload["orders_placed"])
        self.assertFalse(payload["empirical_lock_created"])
        self.assertTrue(str(payload["operator_run_id"]).startswith("RTHOPS-"))

    def test_dry_run_does_not_mutate_frozen_manifest_fingerprint(self) -> None:
        from market_platform_foundation.intelligence.paper_forward_bridge.activation import (
            load_activation_manifest,
        )

        before = load_activation_manifest("FTEP-V1-002").manifest_fingerprint
        with patch(
            "market_platform_foundation.operations.rth_empirical_ops.collect_ftep_catalyst_watch",
            return_value={
                "artifact_kind": "ftep_catalyst_watch_report",
                "dry_run": True,
                "watch_mode": "FIXTURE_SMOKE",
                "disposition": "PASS",
            },
        ), patch(
            "market_platform_foundation.operations.rth_empirical_ops.run_governed_corpus_collection_status",
            return_value=(
                type("R", (), {"status": "S", "acceptance_label": "A", "market_rth_open": False})(),
                (),
                object(),
                object(),
            ),
        ):
            run_rth_empirical_observational_dry_run(ROOT, options=_opts())
        after = load_activation_manifest("FTEP-V1-002").manifest_fingerprint
        self.assertEqual(before, after)
        self.assertEqual(after, FTEP_V1_002_EXPECTED_FINGERPRINT)


if __name__ == "__main__":
    unittest.main()
