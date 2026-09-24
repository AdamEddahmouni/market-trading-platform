"""Preflight and live Finviz ingress must agree on credential availability.

Evidence class: SOFTWARE_CONTROLLED. No provider network request. No campaign
namespace ``RTH-OBS-NEWS-20260924``.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from market_platform_foundation.intelligence.paper_forward_bridge.ftep_prospective_catalyst_ingress import (  # noqa: E402
    describe_finviz_ingress_credential_availability,
    resolve_finviz_ingress_token,
)
from market_platform_foundation.finviz.credential_manager import (  # noqa: E402
    reset_finviz_credential_manager,
)
from market_platform_foundation.finviz.token_names import FINVIZ_TOKEN_NAMES  # noqa: E402
from market_platform_foundation.providers.equity_quote_discovery import (  # noqa: E402
    names_present,
)
from tools.platform.campaign_environment_preflight import (  # noqa: E402
    evaluate_campaign_environment_preflight,
)

DUMMY_TOKEN = "dummy-finviz-token-9f3c2a"
OBSOLETE_NAMES = ("FINVIZ_ELITE_AUTH", "FINVIZ_AUTH", "IMP_FINVIZ_ELITE_AUTH")
CAMPAIGN_ID = "FINVIZ-PREFLIGHT-REHEARSAL"
WINDOW_ID = "FINVIZ-PREFLIGHT-REHEARSAL-A"


def _isolated_env(**extra: str) -> dict[str, str]:
    env = {name: "" for name in (*FINVIZ_TOKEN_NAMES, *OBSOLETE_NAMES)}
    env["IMP_FINVIZ_SECRET_DIR"] = ""
    env["IMP_FINVIZ_LIVE"] = ""
    env["IMP_FTEP_PROSPECTIVE_CATALYST_INGRESS"] = ""
    env.update(extra)
    return env


def _check(report, name: str):
    matches = [item for item in report.checks if item.name == name]
    assert matches, name
    return matches[0]


class FinvizPreflightCredentialIdentityTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.secret_dir = self.root / "secrets"
        self.secret_dir.mkdir()
        self.state_dir = self.root / "state"
        self.state_dir.mkdir()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _preflight(self, env: dict[str, str], *, required: bool):
        return evaluate_campaign_environment_preflight(
            root=ROOT,
            state_dir=self.state_dir,
            environ=env,
            require_ui_deps=False,
            check_opend=False,
            campaign_id=CAMPAIGN_ID,
            observation_window_id=WINDOW_ID,
            require_finviz_live_ingress=required,
        )

    def _assert_agrees(self, env: dict[str, str], report) -> None:
        availability = describe_finviz_ingress_credential_availability(ROOT, env=env)
        token, _, source = resolve_finviz_ingress_token(ROOT, env=env)
        credential = _check(report, "credentials_presence_finviz")
        if availability.available:
            self.assertIsNotNone(token)
            self.assertEqual(source, availability.source)
            self.assertEqual(credential.status, "PASS")
            self.assertNotIn(DUMMY_TOKEN, credential.detail)
        else:
            self.assertIsNone(token)
            self.assertNotEqual(credential.status, "PASS")
            self.assertEqual(credential.detail, availability.reason)

    def _assert_redacted(self, report) -> None:
        blob = json.dumps(report.to_dict(), sort_keys=True)
        self.assertNotIn(DUMMY_TOKEN, blob)
        rendered = str(report)
        self.assertNotIn(DUMMY_TOKEN, rendered)

    def test_no_credential_blocks_required_live_ingress(self) -> None:
        env = _isolated_env(
            IMP_FINVIZ_SECRET_DIR=str(self.secret_dir),
            IMP_FINVIZ_LIVE="1",
            IMP_FTEP_PROSPECTIVE_CATALYST_INGRESS="1",
        )
        report = self._preflight(env, required=True)
        self.assertFalse(report.ready_to_arm)
        self.assertIn("credentials_presence_finviz", report.blockers)
        credential = _check(report, "credentials_presence_finviz")
        self.assertEqual(credential.status, "FAIL")
        self.assertEqual(credential.detail, "FINVIZ_TOKEN_ABSENT")
        self._assert_agrees(env, report)
        self._assert_redacted(report)

    def test_canonical_environment_credential_is_visible_to_both(self) -> None:
        env = _isolated_env(
            IMP_FINVIZ_SECRET_DIR=str(self.secret_dir),
            IMP_FINVIZ_LIVE="1",
            IMP_FTEP_PROSPECTIVE_CATALYST_INGRESS="1",
            FINVIZ_API_KEY=DUMMY_TOKEN,
        )
        report = self._preflight(env, required=True)
        self.assertNotIn("credentials_presence_finviz", report.blockers)
        credential = _check(report, "credentials_presence_finviz")
        self.assertEqual(credential.status, "PASS")
        self.assertEqual(credential.detail, "source=ENVIRONMENT")
        self._assert_agrees(env, report)
        self._assert_redacted(report)
        self.assertEqual(report.evidence_class, "SOFTWARE_CONTROLLED_EVIDENCE")
        self.assertNotIn("EMPIRICALLY_PROVEN", json.dumps(report.to_dict()))

    def test_supported_aliases_agree(self) -> None:
        aliases = [name for name in FINVIZ_TOKEN_NAMES if name != "FINVIZ_API_KEY"]
        self.assertGreaterEqual(len(aliases), 1)
        for name in aliases:
            with self.subTest(name=name):
                env = _isolated_env(
                    IMP_FINVIZ_SECRET_DIR=str(self.secret_dir),
                    IMP_FINVIZ_LIVE="1",
                    IMP_FTEP_PROSPECTIVE_CATALYST_INGRESS="1",
                )
                env[name] = DUMMY_TOKEN
                report = self._preflight(env, required=True)
                credential = _check(report, "credentials_presence_finviz")
                self.assertEqual(credential.status, "PASS")
                self._assert_agrees(env, report)
                self._assert_redacted(report)

    def test_obsolete_preflight_names_do_not_pass(self) -> None:
        for name in OBSOLETE_NAMES:
            with self.subTest(name=name):
                env = _isolated_env(
                    IMP_FINVIZ_SECRET_DIR=str(self.secret_dir),
                    IMP_FINVIZ_LIVE="1",
                    IMP_FTEP_PROSPECTIVE_CATALYST_INGRESS="1",
                )
                env[name] = DUMMY_TOKEN
                report = self._preflight(env, required=True)
                self.assertFalse(report.ready_to_arm)
                credential = _check(report, "credentials_presence_finviz")
                self.assertEqual(credential.status, "FAIL")
                self.assertEqual(credential.detail, "FINVIZ_TOKEN_ABSENT")
                self._assert_agrees(env, report)
                self._assert_redacted(report)

    def test_secret_dir_file_is_recognized_without_exposure(self) -> None:
        (self.secret_dir / "finviz-token.txt").write_text(DUMMY_TOKEN + "\n", encoding="utf-8")
        env = _isolated_env(
            IMP_FINVIZ_SECRET_DIR=str(self.secret_dir),
            IMP_FINVIZ_LIVE="1",
            IMP_FTEP_PROSPECTIVE_CATALYST_INGRESS="1",
        )
        report = self._preflight(env, required=True)
        credential = _check(report, "credentials_presence_finviz")
        self.assertEqual(credential.status, "PASS")
        self.assertEqual(credential.detail, "source=SECRET_DIR")
        self._assert_agrees(env, report)
        self._assert_redacted(report)

    def test_missing_configured_secret_dir_is_not_a_credential_hit(self) -> None:
        missing = self.root / "missing-secrets"
        env = _isolated_env(
            IMP_FINVIZ_SECRET_DIR=str(missing),
            IMP_FINVIZ_LIVE="1",
            IMP_FTEP_PROSPECTIVE_CATALYST_INGRESS="1",
        )
        report = self._preflight(env, required=True)
        credential = _check(report, "credentials_presence_finviz")
        self.assertEqual(credential.status, "FAIL")
        self.assertEqual(credential.detail, "FINVIZ_SECRET_DIR_MISSING")
        self._assert_agrees(env, report)

    def test_finviz_not_required_does_not_block_arm(self) -> None:
        env = _isolated_env(IMP_FINVIZ_SECRET_DIR=str(self.secret_dir))
        report = self._preflight(env, required=False)
        self.assertNotIn("credentials_presence_finviz", report.blockers)
        self.assertNotIn("provider_capability_finviz_flag", report.blockers)
        self.assertNotIn("prospective_catalyst_ingress_gate", report.blockers)
        credential = _check(report, "credentials_presence_finviz")
        self.assertEqual(credential.status, "WARN")
        self.assertTrue(report.ready_to_arm)

    def test_disabled_gates_are_distinct_from_missing_credential(self) -> None:
        env = _isolated_env(
            IMP_FINVIZ_SECRET_DIR=str(self.secret_dir),
            FINVIZ_API_KEY=DUMMY_TOKEN,
        )
        report = self._preflight(env, required=True)
        self.assertFalse(report.ready_to_arm)
        credential = _check(report, "credentials_presence_finviz")
        self.assertEqual(credential.status, "PASS")
        live = _check(report, "provider_capability_finviz_flag")
        ingress = _check(report, "prospective_catalyst_ingress_gate")
        self.assertEqual(live.status, "FAIL")
        self.assertEqual(live.detail, "FINVIZ_LIVE_DISABLED")
        self.assertEqual(ingress.status, "FAIL")
        self.assertEqual(ingress.detail, "INGRESS_NOT_ENABLED")
        self.assertIn("provider_capability_finviz_flag", report.blockers)
        self.assertIn("prospective_catalyst_ingress_gate", report.blockers)
        self.assertNotIn("credentials_presence_finviz", report.blockers)
        self._assert_redacted(report)

    def test_live_gate_off_is_not_reported_as_ingress_gate(self) -> None:
        env = _isolated_env(
            IMP_FINVIZ_SECRET_DIR=str(self.secret_dir),
            FINVIZ_API_KEY=DUMMY_TOKEN,
            IMP_FTEP_PROSPECTIVE_CATALYST_INGRESS="1",
        )
        report = self._preflight(env, required=True)
        self.assertEqual(_check(report, "provider_capability_finviz_flag").detail, "FINVIZ_LIVE_DISABLED")
        self.assertEqual(_check(report, "prospective_catalyst_ingress_gate").status, "PASS")
        self.assertNotIn("credentials_presence_finviz", report.blockers)

    def test_credential_resolution_does_not_open_a_network_connection(self) -> None:
        env = _isolated_env(
            IMP_FINVIZ_SECRET_DIR=str(self.secret_dir),
            FINVIZ_API_KEY=DUMMY_TOKEN,
        )
        with patch("socket.create_connection", side_effect=AssertionError("network")):
            describe_finviz_ingress_credential_availability(ROOT, env=env)
            resolve_finviz_ingress_token(ROOT, env=env)
        with patch("urllib.request.urlopen", side_effect=AssertionError("provider-network")):
            report = self._preflight(env, required=True)
        self.assertEqual(_check(report, "credentials_presence_finviz").status, "PASS")
        self._assert_redacted(report)

    def test_env_alias_precedence_is_canonical_list_order(self) -> None:
        earlier = "dummy-earlier-token-aaa111"
        later = "dummy-later-token-bbb222"
        env = _isolated_env(
            IMP_FINVIZ_SECRET_DIR=str(self.secret_dir),
            FINVIZ_API_KEY=earlier,
            IMP_FINVIZ_TOKEN=later,
        )
        token, _, source = resolve_finviz_ingress_token(ROOT, env=env)
        self.assertEqual(source, "ENVIRONMENT")
        self.assertEqual(token, earlier)
        self.assertNotEqual(token, later)
        availability = describe_finviz_ingress_credential_availability(ROOT, env=env)
        self.assertEqual(availability.source, "ENVIRONMENT")
        self.assertNotIn(earlier, availability.reason or "")
        self.assertNotIn(later, availability.reason or "")

    def test_environment_token_wins_over_secret_file(self) -> None:
        env_token = "dummy-env-token-ccc333"
        file_token = "dummy-file-token-ddd444"
        (self.secret_dir / "finviz-token.txt").write_text(file_token, encoding="utf-8")
        env = _isolated_env(
            IMP_FINVIZ_SECRET_DIR=str(self.secret_dir),
            FINVIZ_ELITE_TOKEN=env_token,
        )
        token, _, source = resolve_finviz_ingress_token(ROOT, env=env)
        self.assertEqual(source, "ENVIRONMENT")
        self.assertEqual(token, env_token)

    def test_empty_and_whitespace_secret_files_are_absent(self) -> None:
        for contents in ("", "   \n\t"):
            with self.subTest(contents=repr(contents)):
                (self.secret_dir / "finviz-token.txt").write_text(contents, encoding="utf-8")
                env = _isolated_env(
                    IMP_FINVIZ_SECRET_DIR=str(self.secret_dir),
                    IMP_FINVIZ_LIVE="1",
                    IMP_FTEP_PROSPECTIVE_CATALYST_INGRESS="1",
                )
                report = self._preflight(env, required=True)
                self.assertEqual(_check(report, "credentials_presence_finviz").detail, "FINVIZ_TOKEN_ABSENT")
                self._assert_agrees(env, report)

    def test_unreadable_secret_file_is_absent(self) -> None:
        path = self.secret_dir / "finviz-token.txt"
        path.write_text(DUMMY_TOKEN, encoding="utf-8")
        env = _isolated_env(IMP_FINVIZ_SECRET_DIR=str(self.secret_dir))
        with patch.object(Path, "read_text", side_effect=OSError("unreadable")):
            token, _, source = resolve_finviz_ingress_token(ROOT, env=env)
            availability = describe_finviz_ingress_credential_availability(ROOT, env=env)
        self.assertIsNone(token)
        self.assertEqual(source, "NONE")
        self.assertFalse(availability.available)
        self.assertEqual(availability.reason, "FINVIZ_TOKEN_ABSENT")
        self.assertNotIn(DUMMY_TOKEN, availability.reason or "")

    def test_quote_discovery_uses_canonical_names_including_imp_finviz_token(self) -> None:
        self.assertIn("IMP_FINVIZ_TOKEN", FINVIZ_TOKEN_NAMES)
        from market_platform_foundation.providers import equity_quote_discovery as discovery

        self.assertIs(discovery.FINVIZ_TOKEN_NAMES, FINVIZ_TOKEN_NAMES)
        cleared = {name: "" for name in (*FINVIZ_TOKEN_NAMES, *OBSOLETE_NAMES)}
        with patch.dict("os.environ", {**cleared, "IMP_FINVIZ_TOKEN": DUMMY_TOKEN}, clear=False):
            present = names_present(FINVIZ_TOKEN_NAMES)
        self.assertEqual(present, ("IMP_FINVIZ_TOKEN",))

    def test_screener_manager_reads_the_same_env_alias(self) -> None:
        from market_platform_foundation.finviz.credential_manager import _env_override_token

        cleared = {name: "" for name in (*FINVIZ_TOKEN_NAMES, *OBSOLETE_NAMES)}
        reset_finviz_credential_manager()
        try:
            with patch.dict("os.environ", {**cleared, "IMP_FINVIZ_TOKEN": DUMMY_TOKEN}, clear=False):
                found = _env_override_token()
            self.assertEqual(found, DUMMY_TOKEN)
            with patch.dict("os.environ", {**cleared, "FINVIZ_ELITE_AUTH": DUMMY_TOKEN}, clear=False):
                self.assertIsNone(_env_override_token())
        finally:
            reset_finviz_credential_manager()

    def test_child_process_sees_inherited_canonical_env_without_printing_it(self) -> None:
        import os
        import subprocess

        env = os.environ.copy()
        for name in (*FINVIZ_TOKEN_NAMES, *OBSOLETE_NAMES):
            env.pop(name, None)
        env["FINVIZ_API_KEY"] = DUMMY_TOKEN
        env["IMP_FINVIZ_SECRET_DIR"] = str(self.secret_dir)
        env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
        code = (
            "from pathlib import Path\n"
            "from market_platform_foundation.intelligence.paper_forward_bridge"
            ".ftep_prospective_catalyst_ingress import resolve_finviz_ingress_token\n"
            f"token, _secret, source = resolve_finviz_ingress_token(Path({str(ROOT)!r}))\n"
            "assert token\n"
            "print(source)\n"
        )
        completed = subprocess.run(
            [sys.executable, "-c", code],
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout.strip(), "ENVIRONMENT")
        self.assertNotIn(DUMMY_TOKEN, completed.stdout)
        self.assertNotIn(DUMMY_TOKEN, completed.stderr)


if __name__ == "__main__":
    unittest.main()
