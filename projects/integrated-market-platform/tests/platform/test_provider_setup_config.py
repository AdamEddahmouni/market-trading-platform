"""Provider setup registry: SEC contact identity, keyed providers, precedence, gates, and secret safety."""

from __future__ import annotations

import json
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from market_platform_foundation.platform.security.leak_audit import assert_no_secrets_in_payload
from market_platform_foundation.ui_api import operator_config, operator_projections
from market_platform_foundation.ui_api.operator_config import (
    PROVIDERS_BY_ID,
    ConfigError,
    ProviderConfigStore,
    managed_names,
    sec_contact_identity,
)
from market_platform_foundation.ui_api.request_auth import loopback_request_origin

IDENTITY = "Acme Research Ops Desk ops-desk@acme-research.test"
SECRET = "fh-live-7f3a9c2e51d4"
REPLACEMENT = "fh-live-00aa11bb22cc"


def _provider(payload: dict, provider: str) -> dict:
    return next(item for item in payload["providers"] if item["provider"] == provider)


def _field(payload: dict, provider: str, name: str) -> dict:
    return next(item for item in _provider(payload, provider)["fields"] if item["key"] == name)


class StoreCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.private = self.root / "providers.env"
        self.env_file = self.root / ".env"
        self.environ: dict[str, str] = {}

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def store(self, **kwargs) -> ProviderConfigStore:
        return ProviderConfigStore(private_path=self.private, env_file_path=self.env_file, environ=self.environ, **kwargs)


class SecIdentityTests(StoreCase):
    def test_sec_identity_is_stored_enables_sec_reads_and_applies_without_restart(self) -> None:
        store = self.store()
        result = store.write("sec", {"SEC_USER_AGENT": IDENTITY})

        self.assertEqual(result["saved"], ["SEC_USER_AGENT"])
        self.assertEqual(result["gates_enabled"], ["IMP_EDGAR_LIVE", "IMP_SEC_FTD_LIVE"])
        self.assertEqual(result["applies"], "NEXT_REQUEST")
        self.assertIn(f"SEC_USER_AGENT={IDENTITY}", self.private.read_text(encoding="utf-8"))
        # The running API sees it at once: SEC consumers read the process environment per request.
        self.assertEqual(self.environ["SEC_USER_AGENT"], IDENTITY)
        self.assertEqual(self.environ["IMP_EDGAR_LIVE"], "1")
        from market_platform_foundation.news.sec_filings_news import live_state

        self.assertEqual(live_state(self.environ.get), ("CURRENT", None))

    def test_sec_status_reports_configured_with_only_the_email_domain(self) -> None:
        store = self.store()
        store.write("sec", {"SEC_USER_AGENT": IDENTITY})
        payload = store.payload()

        field = _field(payload, "sec", "SEC_USER_AGENT")
        self.assertTrue(field["configured"])
        self.assertFalse(field["sensitive"])
        self.assertEqual(field["source"], "PRIVATE_FILE")
        self.assertEqual(field["hint"], "contact at @acme-research.test")
        rendered = json.dumps(payload)
        self.assertNotIn("ops-desk", rendered)
        self.assertNotIn("Acme Research Ops Desk", rendered)
        self.assertEqual(_provider(payload, "sec")["state"], "CONFIGURED")

    def test_sec_identity_validation_rejects_malformed_values(self) -> None:
        cases = {
            "": "VALUE_REQUIRED",
            "ops-desk@acme-research.test": "SEC_USER_AGENT_MUST_IDENTIFY_CONTACT",
            "Acme Research": "SEC_USER_AGENT_MUST_IDENTIFY_CONTACT",
            "Acme ops@acme": "SEC_USER_AGENT_MUST_IDENTIFY_CONTACT",
            "python-requests/2.31 ops@acme.test": "SEC_USER_AGENT_GENERIC_FORBIDDEN",
            "Acme\tDesk ops@acme.test": "VALUE_HAS_CONTROL_CHARACTERS",
            "Acmé Desk ops@acme.test": "SEC_USER_AGENT_NOT_ASCII",
            "12 ops@acme.test": "SEC_USER_AGENT_NEEDS_NAME",
            "Acme " + "x" * 200 + " ops@acme.test": "VALUE_TOO_LONG",
            '"Acme Desk ops@acme.test"': "VALUE_QUOTED",
        }
        for value, code in cases.items():
            with self.subTest(value=value[:30]):
                with self.assertRaises(ConfigError) as ctx:
                    sec_contact_identity(value)
                self.assertEqual(ctx.exception.code, code)
        self.assertEqual(sec_contact_identity("  Acme   Desk ops@acme.test "), "Acme Desk ops@acme.test")

    def test_rejected_write_changes_nothing(self) -> None:
        self.private.write_text("OTHER=keep\n", encoding="utf-8")
        with self.assertRaises(ConfigError):
            self.store().write("sec", {"SEC_USER_AGENT": "no contact here"})
        self.assertEqual(self.private.read_text(encoding="utf-8"), "OTHER=keep\n")
        self.assertNotIn("SEC_USER_AGENT", self.environ)


class SecretCredentialTests(StoreCase):
    def test_secret_is_stored_never_returned_and_unrelated_lines_survive(self) -> None:
        self.private.write_text("# operator notes\nUNRELATED_SETTING=keep\nIMP_CUSTOM=1\n", encoding="utf-8")
        store = self.store()
        result = store.write("finnhub", {"FINNHUB_API_KEY": SECRET})
        payload = store.payload()

        text = self.private.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("# operator notes\nUNRELATED_SETTING=keep\nIMP_CUSTOM=1\n"))
        self.assertIn(f"FINNHUB_API_KEY={SECRET}", text)
        self.assertIn("IMP_FINNHUB_LIVE=1", text)
        self.assertNotIn(SECRET, json.dumps(result))
        self.assertNotIn(SECRET, json.dumps(payload))
        field = _field(payload, "finnhub", "FINNHUB_API_KEY")
        self.assertEqual((field["configured"], field["sensitive"], field["removable"]), (True, True, True))
        self.assertIsNone(field["hint"])
        assert_no_secrets_in_payload(payload, context="provider_setup")
        assert_no_secrets_in_payload(result, context="provider_setup_result")

    def test_replace_updates_one_line(self) -> None:
        store = self.store()
        store.write("finnhub", {"FINNHUB_API_KEY": SECRET})
        store.write("finnhub", {"FINNHUB_API_KEY": REPLACEMENT})

        text = self.private.read_text(encoding="utf-8")
        self.assertEqual(text.count("FINNHUB_API_KEY="), 1)
        self.assertIn(REPLACEMENT, text)
        self.assertNotIn(SECRET, text)
        self.assertEqual(self.environ["FINNHUB_API_KEY"], REPLACEMENT)

    def test_blank_value_keeps_the_stored_secret(self) -> None:
        store = self.store()
        store.write("finra", {"FINRA_CLIENT_ID": "client-1", "FINRA_CLIENT_SECRET": SECRET})
        store.write("finra", {"FINRA_CLIENT_ID": "client-2", "FINRA_CLIENT_SECRET": ""})

        text = self.private.read_text(encoding="utf-8")
        self.assertIn("FINRA_CLIENT_ID=client-2", text)
        self.assertIn(f"FINRA_CLIENT_SECRET={SECRET}", text)
        with self.assertRaises(ConfigError) as ctx:
            store.write("finra", {"FINRA_CLIENT_SECRET": "   "})
        self.assertEqual(ctx.exception.code, "NO_CHANGES")

    def test_partial_credentials_do_not_enable_the_provider(self) -> None:
        store = self.store()
        result = store.write("finra", {"FINRA_CLIENT_ID": "client-1"})

        self.assertEqual(result["gates_enabled"], [])
        self.assertNotIn("IMP_FINRA_LIVE", self.private.read_text(encoding="utf-8"))
        self.assertEqual(_provider(store.payload(), "finra")["state"], "PARTIAL")

    def test_clear_removes_the_value_and_its_private_gate_only(self) -> None:
        self.private.write_text("UNRELATED_SETTING=keep\n", encoding="utf-8")
        store = self.store()
        store.write("newsapi", {"NEWSAPI_API_KEY": SECRET})
        store.write("finnhub", {"FINNHUB_API_KEY": REPLACEMENT})
        result = store.write("newsapi", {}, ["NEWSAPI_API_KEY"])

        text = self.private.read_text(encoding="utf-8")
        self.assertEqual(result["cleared"], ["NEWSAPI_API_KEY"])
        self.assertEqual(result["gates_removed"], ["IMP_NEWSAPI_LIVE"])
        self.assertNotIn("NEWSAPI", text)
        self.assertIn("UNRELATED_SETTING=keep", text)
        self.assertIn(f"FINNHUB_API_KEY={REPLACEMENT}", text)
        self.assertNotIn("NEWSAPI_API_KEY", self.environ)
        self.assertEqual(_provider(store.payload(), "newsapi")["state"], "NEEDS_SETUP")

    def test_clear_falls_back_to_the_repository_env_file(self) -> None:
        self.env_file.write_text("FRED_API_KEY=from-env-file\n", encoding="utf-8")
        store = self.store()
        store.write("fred", {"FRED_API_KEY": SECRET})
        self.assertEqual(self.environ["FRED_API_KEY"], SECRET)
        store.write("fred", {}, ["FRED_API_KEY"])

        self.assertEqual(self.environ["FRED_API_KEY"], "from-env-file")
        field = _field(store.payload(), "fred", "FRED_API_KEY")
        self.assertEqual((field["source"], field["removable"]), ("ENV_FILE", False))

    def test_arbitrary_names_and_unregistered_providers_are_rejected(self) -> None:
        store = self.store()
        attempts = [
            ("sec", {"PATH": "C:/evil"}, None),
            ("sec", {"FINNHUB_API_KEY": SECRET}, None),     # another provider's field
            ("sec", {"IMP_EDGAR_LIVE": "1"}, None),         # gates are policy, not fields
            ("finnhub", {}, ["IMP_PAPER_EXECUTION"]),
            ("ibkr", {"IBKR_PASSWORD": SECRET}, None),       # native login: nothing to write
            ("opend", {"ANY": "x"}, None),
            ("../providers", {"X": "y"}, None),
        ]
        for provider, values, clear in attempts:
            with self.subTest(provider=provider, values=list(values), clear=clear):
                with self.assertRaises(ConfigError) as ctx:
                    store.write(provider, values, clear)
                self.assertIn(ctx.exception.code, {"PROVIDER_FIELD_NOT_ALLOWED", "PROVIDER_NOT_SUPPORTED"})
                self.assertNotIn(SECRET, str(ctx.exception))
        self.assertFalse(self.private.exists())

    def test_invalid_secret_error_names_the_setting_not_the_value(self) -> None:
        with self.assertRaises(ConfigError) as ctx:
            self.store().write("finnhub", {"FINNHUB_API_KEY": "has space inside"})
        self.assertEqual(str(ctx.exception), "VALUE_HAS_WHITESPACE:FINNHUB_API_KEY")
        # The textual secret rules match NAME=value / NAME: value; errors must lead with the code.
        assert_no_secrets_in_payload({"message": str(ctx.exception)}, context="error")

    def test_paid_ai_keys_never_reach_the_process_environment(self) -> None:
        # A key in os.environ would silently switch the Assistant to paid Anthropic
        # (assistant.inference_factory); AI synthesis reads the private file itself.
        self.private.write_text(f"ANTHROPIC_API_KEY={SECRET}\n", encoding="utf-8")
        store = self.store()
        store.bootstrap()
        store.write("openai", {"OPENAI_API_KEY": REPLACEMENT})
        store.write("gemini", {"GEMINI_API_KEY": REPLACEMENT})

        for name in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY"):
            self.assertNotIn(name, self.environ)
        payload = store.payload()
        self.assertEqual(_field(payload, "anthropic", "ANTHROPIC_API_KEY")["source"], "PRIVATE_FILE")
        self.assertEqual(_provider(payload, "openai")["state"], "CONFIGURED")
        self.assertEqual([setting.name for setting in PROVIDERS_BY_ID["anthropic"].settings], ["ANTHROPIC_API_KEY"])

    def test_no_registered_gate_is_an_execution_or_billing_gate(self) -> None:
        forbidden = ("EXECUTION", "PAPER", "ORDER", "BROKER", "TRADE", "BILLING")
        for entry in PROVIDERS_BY_ID.values():
            for gate in entry.live_gates:
                self.assertTrue(gate.startswith("IMP_") and gate.endswith("_LIVE"), gate)
                self.assertFalse(any(word in gate for word in forbidden), gate)
        self.assertEqual(PROVIDERS_BY_ID["tradier"].live_gates, ())
        for entry in PROVIDERS_BY_ID.values():
            if entry.access == "PAID_API":
                self.assertEqual(entry.live_gates, (), entry.provider)
        self.assertNotIn("IMP_TRADIER_PAPER", managed_names())
        self.assertNotIn("IMP_BROKER_PAPER_EXECUTION", managed_names())


class SwitchTests(StoreCase):
    """Keyless public sources: one observational gate, switched from Setup (PR D)."""

    def test_switch_on_and_off_writes_one_line_and_keeps_every_other_line(self) -> None:
        self.private.write_text(f"# operator notes\nFINNHUB_API_KEY={SECRET}\nUNREGISTERED_THING=1\n", encoding="utf-8")
        store = self.store()
        result = store.switch("treasury", True)
        self.assertEqual((result["switch"], result["gates_enabled"], result["gates_removed"]), ("ON", ["IMP_TREASURY_LIVE"], []))
        self.assertEqual(result["applies"], "NEXT_REQUEST")
        self.assertEqual(self.environ["IMP_TREASURY_LIVE"], "1")
        text = self.private.read_text(encoding="utf-8")
        self.assertIn("IMP_TREASURY_LIVE=1", text)
        for kept in ("# operator notes", f"FINNHUB_API_KEY={SECRET}", "UNREGISTERED_THING=1"):
            self.assertIn(kept, text)
        payload = store.payload()
        self.assertEqual(_provider(payload, "treasury")["state"], "ON")
        self.assertEqual(_provider(payload, "treasury")["switch"],
                         {"name": "IMP_TREASURY_LIVE", "on": True, "source": "PRIVATE_FILE", "editable": True})
        # The response carries names only.
        self.assertNotIn(SECRET, json.dumps(result))

        result = store.switch("treasury", False)
        self.assertEqual((result["switch"], result["gates_enabled"], result["gates_removed"]), ("OFF", [], ["IMP_TREASURY_LIVE"]))
        self.assertNotIn("IMP_TREASURY_LIVE", self.private.read_text(encoding="utf-8"))
        self.assertNotIn("IMP_TREASURY_LIVE", self.environ)
        self.assertEqual(_provider(store.payload(), "treasury")["state"], "OFF")
        self.assertIn(f"FINNHUB_API_KEY={SECRET}", self.private.read_text(encoding="utf-8"))

    def test_switching_to_the_current_state_changes_nothing(self) -> None:
        store = self.store()
        self.assertEqual(store.switch("kraken", False)["gates_removed"], [])
        self.assertFalse(self.private.exists())
        store.switch("kraken", True)
        self.assertEqual(store.switch("kraken", True)["gates_enabled"], [])

    def test_off_overrides_a_repository_env_file_that_switches_it_on(self) -> None:
        self.env_file.write_text("IMP_CRYPTO_LIVE=1\n", encoding="utf-8")
        store = self.store()
        self.assertEqual(_provider(store.payload(), "kraken")["state"], "ON")
        store.switch("kraken", False)
        self.assertIn("IMP_CRYPTO_LIVE=0", self.private.read_text(encoding="utf-8"))
        self.assertEqual(_provider(store.payload(), "kraken")["state"], "OFF")

    def test_a_gate_the_environment_sets_is_refused_and_reported_read_only(self) -> None:
        self.environ["IMP_NEWS_RSS_LIVE"] = "1"
        store = self.store()
        switch = _provider(store.payload(), "rss")["switch"]
        self.assertEqual((switch["on"], switch["source"], switch["editable"]), (True, "ENVIRONMENT", False))
        for on in (True, False):
            with self.assertRaises(ConfigError) as ctx:
                store.switch("rss", on)
            self.assertEqual((ctx.exception.code, ctx.exception.setting), ("SETTING_OVERRIDDEN_BY_ENVIRONMENT", "IMP_NEWS_RSS_LIVE"))
        self.assertFalse(self.private.exists())
        self.assertEqual(self.environ["IMP_NEWS_RSS_LIVE"], "1")

    def test_unknown_and_non_switchable_providers_are_refused(self) -> None:
        store = self.store()
        # Finviz live is a path-A preflight blocker; Senate eFD needs the terms attestation; keyed providers switch
        # on by saving their key; brokers are never switchable.
        for provider in ("finviz", "senate_efd", "sec", "newsapi", "tradier", "ibkr", "opend", "anthropic", "nope", ""):
            with self.subTest(provider=provider), self.assertRaises(ConfigError) as ctx:
                store.switch(provider, True)
            self.assertEqual(ctx.exception.code, "PROVIDER_NOT_SWITCHABLE")
        self.assertFalse(self.private.exists())

    def test_only_keyless_observational_read_gates_are_switchable(self) -> None:
        switchable = {entry.provider: entry.live_gates for entry in PROVIDERS_BY_ID.values() if entry.switchable}
        self.assertEqual(switchable, {
            "rss": ("IMP_NEWS_RSS_LIVE",), "public_records": ("IMP_PUBLIC_RECORDS_LIVE",), "treasury": ("IMP_TREASURY_LIVE",),
            "kraken": ("IMP_CRYPTO_LIVE",), "openfigi": ("IMP_OPENFIGI_LIVE",)})
        for entry in PROVIDERS_BY_ID.values():
            if entry.switchable:
                self.assertIn(entry.access, ("FREE",), entry.provider)
                self.assertFalse(any(setting.required for setting in entry.settings), entry.provider)
        for gate in ("IMP_FINVIZ_LIVE", "IMP_SENATE_EFD_LIVE", "IMP_LIVE_EXECUTION", "IMP_BROKER_PAPER_EXECUTION",
                     "IMP_PAPER_EXECUTION", "IMP_BROKER_LIVE_EXECUTION", "IMP_PAPER_AUTOMATION_ENABLED"):
            self.assertNotIn(gate, managed_names(), gate)

    def test_openfigi_key_and_switch_are_independent(self) -> None:
        store = self.store()
        result = store.write("openfigi", {"OPENFIGI_API_KEY": SECRET})
        # Its key is optional, so saving it switches nothing: the lookup switch is its own choice.
        self.assertEqual(result["gates_enabled"], [])
        self.assertEqual(_provider(store.payload(), "openfigi")["state"], "CONFIGURED")
        self.assertFalse(_provider(store.payload(), "openfigi")["switch"]["on"])
        store.switch("openfigi", True)
        self.assertTrue(_provider(store.payload(), "openfigi")["switch"]["on"])

    def test_route_rejects_a_switch_with_values_and_an_unknown_switch(self) -> None:
        with mock.patch.object(operator_projections, "default_store", return_value=self.store()):
            for body, code in (({"provider": "rss", "switch": "ON", "values": {"X": "y"}}, "SWITCH_WITH_VALUES_CONFLICT"),
                               ({"provider": "rss", "switch": "ON", "clear": ["X"]}, "SWITCH_WITH_VALUES_CONFLICT"),
                               ({"provider": "rss", "switch": True}, "INVALID_SWITCH"),
                               ({"provider": "finviz", "switch": "ON"}, "PROVIDER_NOT_SWITCHABLE")):
                with self.subTest(body=body), self.assertRaisesRegex(ValueError, code):
                    operator_projections.save_provider_config(body)
            response = operator_projections.save_provider_config({"provider": "rss", "switch": "ON"})
        self.assertEqual((response["result"]["switch"], response["result"]["gates_enabled"]), ("ON", ["IMP_NEWS_RSS_LIVE"]))
        self.assertEqual(_provider(response, "rss")["state"], "ON")
        self.assertEqual(self.private.read_text(encoding="utf-8"), "IMP_NEWS_RSS_LIVE=1\n")


class PrecedenceTests(StoreCase):
    def test_environment_setting_is_reported_read_only_and_never_shadowed(self) -> None:
        self.environ["SEC_USER_AGENT"] = "Ops Env env@acme.test"
        store = self.store()
        field = _field(store.payload(), "sec", "SEC_USER_AGENT")
        self.assertEqual((field["source"], field["editable"], field["removable"]), ("ENVIRONMENT", False, False))

        with self.assertRaises(ConfigError) as ctx:
            store.write("sec", {"SEC_USER_AGENT": IDENTITY})
        self.assertEqual(ctx.exception.code, "SETTING_OVERRIDDEN_BY_ENVIRONMENT")
        self.assertFalse(self.private.exists())
        self.assertEqual(self.environ["SEC_USER_AGENT"], "Ops Env env@acme.test")

    def test_provider_own_store_is_reported_configured_without_a_value(self) -> None:
        # Finviz validates and keeps its token in its own store; Setup must not call a working provider "not set".
        store = self.store(provider_stores={"FINVIZ_API_KEY": lambda: True})
        payload = store.payload()
        field = _field(payload, "finviz", "FINVIZ_API_KEY")
        self.assertEqual((field["configured"], field["source"], field["editable"], field["removable"]),
                         (True, "PROVIDER_STORE", True, False))
        self.assertEqual(_provider(payload, "finviz")["state"], "CONFIGURED")
        assert_no_secrets_in_payload(payload)
        self.assertEqual(_provider(self.store().payload(), "finviz")["state"], "NEEDS_SETUP")

    def test_bootstrap_applies_private_values_without_overriding_the_environment(self) -> None:
        self.private.write_text(
            f"SEC_USER_AGENT={IDENTITY}\nFINNHUB_API_KEY={SECRET}\nUNREGISTERED_THING=1\nIMP_EDGAR_LIVE=1\n",
            encoding="utf-8",
        )
        self.environ["FINNHUB_API_KEY"] = "from-real-env"
        store = self.store()
        store.bootstrap()

        self.assertEqual(self.environ["SEC_USER_AGENT"], IDENTITY)
        self.assertEqual(self.environ["IMP_EDGAR_LIVE"], "1")
        self.assertEqual(self.environ["FINNHUB_API_KEY"], "from-real-env")
        self.assertNotIn("UNREGISTERED_THING", self.environ)
        payload = store.payload()
        self.assertEqual(_field(payload, "sec", "SEC_USER_AGENT")["source"], "PRIVATE_FILE")
        self.assertEqual(_field(payload, "finnhub", "FINNHUB_API_KEY")["source"], "ENVIRONMENT")
        # A value IMP copied in is still UI-managed, not an environment override.
        store.write("sec", {"SEC_USER_AGENT": "Other Desk other@acme.test"})
        self.assertEqual(self.environ["SEC_USER_AGENT"], "Other Desk other@acme.test")

    def test_environment_gate_is_reported_and_left_alone(self) -> None:
        self.environ["IMP_EDGAR_LIVE"] = "0"
        store = self.store()
        store.write("sec", {"SEC_USER_AGENT": IDENTITY})

        self.assertEqual(self.environ["IMP_EDGAR_LIVE"], "0")
        gate = next(item for item in _provider(store.payload(), "sec")["live_gates"] if item["name"] == "IMP_EDGAR_LIVE")
        self.assertEqual((gate["enabled"], gate["source"]), (False, "ENVIRONMENT"))


class RegistryShapeTests(unittest.TestCase):
    def test_every_provider_says_what_it_unlocks_and_how_it_is_set_up(self) -> None:
        payload = operator_config.build_config_payload(path=Path(tempfile.gettempdir()) / "imp-missing-providers.env")
        self.assertEqual(payload["schema_version"], "operator-config/1.1")
        self.assertFalse(payload["secrets_included"])
        for provider in payload["providers"]:
            self.assertTrue(provider["unlocks"], provider["provider"])
            self.assertEqual(provider["verification"], "ON_FIRST_USE")
            if provider["configurable"]:
                self.assertTrue(provider["fields"], provider["provider"])
            elif provider["switchable"]:
                # A keyless source: no fields, one switch (off without a private file).
                self.assertEqual((provider["fields"], provider["state"], provider["switch"]["on"]), ([], "OFF", False))
            else:
                self.assertEqual(provider["state"], "EXTERNAL")
                self.assertTrue(provider["external_setup"])
        for provider in ("opend", "ibkr", "senate_efd"):
            self.assertFalse(_provider(payload, provider)["configurable"])
        self.assertEqual(_provider(payload, "sec")["unlocks"][:3],
                         ["SEC filings in News", "SEC press releases", "13F institutional ownership"])
        assert_no_secrets_in_payload(payload, context="provider_setup")

    def test_brokerage_passwords_and_two_factor_seeds_are_not_accepted(self) -> None:
        for name in ("IBKR_PASSWORD", "IBKR_TOTP_SECRET", "IBKR_USERNAME", "FINVIZ_PASSWORD", "APCA_API_SECRET_KEY"):
            self.assertNotIn(name, managed_names())


class RefreshTests(unittest.TestCase):
    def test_sec_change_rebuilds_transports_and_clears_cached_not_configured(self) -> None:
        from market_platform_foundation.news.rss_feeds import RssNewsSource
        from market_platform_foundation.news.sec_filings_news import SecFilingNews

        built: list[str] = []
        env = {"IMP_EDGAR_LIVE": "1", "SEC_USER_AGENT": "First Desk first@acme.test"}
        sec = SecFilingNews(transport_factory=lambda: built.append(env["SEC_USER_AGENT"]) or object(), env=env.get)
        sec._get_transport()
        env["SEC_USER_AGENT"] = IDENTITY
        sec.reset_transport()
        sec._get_transport()
        self.assertEqual(built, ["First Desk first@acme.test", IDENTITY])

        rss = RssNewsSource(env={}.get)
        rss._cache["x"] = object()
        rss.clear_cache()
        self.assertEqual(rss._cache, {})

    def test_save_refreshes_only_services_that_already_exist(self) -> None:
        from market_platform_foundation.ui_api import screener_news, screener_participants

        news = mock.Mock()
        with tempfile.TemporaryDirectory() as tmp:
            store = ProviderConfigStore(private_path=Path(tmp) / "providers.env", environ={}, external=frozenset())
            with mock.patch.object(operator_projections, "default_store", return_value=store), \
                    mock.patch.object(screener_news, "_SERVICE", news), \
                    mock.patch.object(screener_participants, "_SERVICE", None):
                response = operator_projections.save_provider_config(
                    {"provider": "sec", "values": {"SEC_USER_AGENT": IDENTITY}})
        news.credentials_changed.assert_called_once_with()
        self.assertEqual(response["result"]["saved"], ["SEC_USER_AGENT"])
        self.assertNotIn(IDENTITY, json.dumps(response))
        assert_no_secrets_in_payload(response, context="provider_setup_response")


class CliParityTests(unittest.TestCase):
    def test_cli_default_flow_stores_sec_identity_with_the_same_gates(self) -> None:
        from tools.news.auth import configured_values

        self.assertEqual(configured_values("", "", sec_user_agent=IDENTITY),
                         {"SEC_USER_AGENT": IDENTITY, "IMP_EDGAR_LIVE": "1", "IMP_SEC_FTD_LIVE": "1"})

    def test_cli_provider_flow_uses_registry_validation_and_hides_secrets(self) -> None:
        from tools.news import auth

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "providers.env"
            asked_secret: list[str] = []
            with mock.patch("builtins.print") as printed:
                code = auth.configure_provider("finra", path=path, ask=lambda prompt: "client-1",
                                               ask_secret=lambda prompt: asked_secret.append(prompt) or SECRET)
            self.assertEqual(code, 0)
            self.assertEqual(len(asked_secret), 1)  # only the client secret is a hidden prompt
            text = path.read_text(encoding="utf-8")
            self.assertIn("FINRA_CLIENT_ID=client-1", text)
            self.assertIn("IMP_FINRA_LIVE=1", text)
            self.assertNotIn(SECRET, " ".join(str(call) for call in printed.call_args_list))
            with mock.patch("builtins.print"):
                self.assertEqual(auth.configure_provider("sec", path=path, ask=lambda prompt: "no contact",
                                                         ask_secret=lambda prompt: ""), 2)
            self.assertNotIn("SEC_USER_AGENT", path.read_text(encoding="utf-8"))


class OriginGuardTests(unittest.TestCase):
    def test_the_imp_ui_and_non_browser_clients_are_allowed(self) -> None:
        for headers in ({}, {"Origin": "http://127.0.0.1:5173", "Sec-Fetch-Site": "same-origin"},
                        {"origin": "http://localhost:5173"}):
            self.assertTrue(loopback_request_origin(headers), headers)

    def test_other_sites_are_refused(self) -> None:
        # AUD-001: an exact UI allowlist; another page served from loopback is not the IMP UI.
        for headers in ({"Origin": "https://evil.example"}, {"Origin": "null"},
                        {"Origin": "http://[::1]:5173"}, {"Origin": "http://imp.localhost:5173"},
                        {"Origin": "http://127.0.0.1:8080"},
                        {"Origin": "http://127.0.0.1.evil.example"}, {"Sec-Fetch-Site": "cross-site"},
                        {"Origin": "http://localhost:5173", "Sec-Fetch-Site": "cross-site"}):
            self.assertFalse(loopback_request_origin(headers), headers)


class HttpRouteTests(unittest.TestCase):
    """The real handler: write, read back, and the response guard, over HTTP."""

    @classmethod
    def setUpClass(cls) -> None:
        from market_platform_foundation.ui_api.server import UiApiHandler

        cls._tmp = tempfile.TemporaryDirectory()
        cls.store = ProviderConfigStore(private_path=Path(cls._tmp.name) / "providers.env", environ={},
                                        external=frozenset())
        cls._patch = mock.patch.object(operator_projections, "default_store", return_value=cls.store)
        cls._patch.start()
        UiApiHandler.store = mock.Mock()
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), UiApiHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls._patch.stop()
        cls._tmp.cleanup()

    def request(self, method: str, path: str, body: dict | None = None, headers: dict | None = None) -> tuple[int, str]:
        connection = HTTPConnection("127.0.0.1", self.server.server_address[1], timeout=10)
        payload = json.dumps(body).encode("utf-8") if body is not None else None
        connection.request(method, path, body=payload, headers={"Content-Type": "application/json", **(headers or {})})
        response = connection.getresponse()
        text = response.read().decode("utf-8")
        connection.close()
        return response.status, text

    def test_post_saves_and_neither_post_nor_get_echoes_the_secret(self) -> None:
        status, text = self.request("POST", "/operator/config/provider",
                                    {"provider": "newsapi", "values": {"NEWSAPI_API_KEY": SECRET}},
                                    {"Origin": "http://127.0.0.1:5173"})
        self.assertEqual(status, 200, text)
        self.assertNotIn(SECRET, text)
        self.assertEqual(json.loads(text)["result"]["saved"], ["NEWSAPI_API_KEY"])
        status, text = self.request("GET", "/operator/config")
        self.assertEqual(status, 200, text)
        self.assertNotIn(SECRET, text)
        self.assertTrue(_field(json.loads(text), "newsapi", "NEWSAPI_API_KEY")["configured"])

    def test_cross_site_post_is_refused_before_anything_is_written(self) -> None:
        status, text = self.request("POST", "/operator/config/provider",
                                    {"provider": "gemini", "values": {"GEMINI_API_KEY": SECRET}},
                                    {"Origin": "https://evil.example"})
        self.assertEqual(status, 403, text)
        # AUD-001: the server-wide origin policy now refuses it before the route's own check is reached.
        self.assertEqual((json.loads(text)["reason_code"], json.loads(text)["error_category"]),
                         ("ORIGIN_NOT_ALLOWED", "AUTH_ERROR"))
        self.assertNotIn("GEMINI_API_KEY", self.store.private_path.read_text(encoding="utf-8")
                         if self.store.private_path.exists() else "")

    def test_cross_site_switch_is_refused_before_anything_is_written(self) -> None:
        status, text = self.request("POST", "/operator/config/provider", {"provider": "kraken", "switch": "ON"},
                                    {"Origin": "https://evil.example"})
        self.assertEqual(status, 403, text)
        self.assertEqual(json.loads(text)["reason_code"], "ORIGIN_NOT_ALLOWED")
        self.assertNotIn("IMP_CRYPTO_LIVE", self.store.private_path.read_text(encoding="utf-8")
                         if self.store.private_path.exists() else "")
        status, text = self.request("POST", "/operator/config/provider", {"provider": "kraken", "switch": "ON"},
                                    {"Origin": "http://localhost:5173"})
        self.assertEqual(status, 200, text)
        self.assertEqual(json.loads(text)["result"]["switch"], "ON")
        status, text = self.request("POST", "/operator/config/provider", {"provider": "kraken", "switch": "OFF"},
                                    {"Origin": "http://localhost:5173"})
        self.assertEqual((status, json.loads(text)["result"]["gates_removed"]), (200, ["IMP_CRYPTO_LIVE"]))

    def test_validation_and_override_errors_are_readable_and_value_free(self) -> None:
        status, text = self.request("POST", "/operator/config/provider",
                                    {"provider": "sec", "values": {"SEC_USER_AGENT": "missing contact"}})
        self.assertEqual(status, 400, text)
        self.assertEqual(json.loads(text)["error_category"], "VALIDATION_ERROR")
        self.assertIn("SEC_USER_AGENT_MUST_IDENTIFY_CONTACT", text)
        self.assertNotIn("missing contact", text)
        self.assertNotIn("UI_SECRET_LEAK_BLOCKED", text)
        status, text = self.request("POST", "/operator/config/provider",
                                    {"provider": "sec", "values": {"GENERIC_ENV": "x"}})
        self.assertEqual(status, 400, text)
        self.assertIn("PROVIDER_FIELD_NOT_ALLOWED", text)


if __name__ == "__main__":
    unittest.main()
