"""Tests for provider capability registry, field-level provider selection,
and credential non-disclosure.
"""

from __future__ import annotations

import pytest

from apps.research_screener.provider_capabilities import (
    Capability,
    CapabilityStatus,
    FieldSelectionReason,
    FieldSource,
    ProviderCapabilities,
    ProviderCapabilityRegistry,
    field_source_dict,
)


class TestCapabilityRegistry:
    def test_register_and_retrieve(self):
        registry = ProviderCapabilityRegistry()
        ibkr = ProviderCapabilities(provider="IBKR", configured=True, connected=True)
        ibkr.set_available(Capability.DISCOVERY, detail="Scanner available")
        registry.register(ibkr)
        assert registry.get("IBKR") is ibkr
        assert registry.get("IBKR").is_available(Capability.DISCOVERY)

    def test_unconfigured_provider(self):
        pc = ProviderCapabilities(provider="NewsAPI", configured=False)
        assert not pc.is_available(Capability.NEWS)
        assert pc.status(Capability.NEWS) == CapabilityStatus.UNTESTED

    def test_find_available_capabilities(self):
        registry = ProviderCapabilityRegistry()
        ibkr = ProviderCapabilities(provider="IBKR", configured=True)
        ibkr.set_available(Capability.DISCOVERY, Capability.HISTORICAL_BARS)
        ibkr.set_not_supported(Capability.NEWS)
        registry.register(ibkr)

        sec = ProviderCapabilities(provider="SEC_EDGAR", configured=True)
        sec.set_available(Capability.FILINGS)
        registry.register(sec)

        assert set(registry.find_available(Capability.DISCOVERY)) == {"IBKR"}
        assert set(registry.find_available(Capability.FILINGS)) == {"SEC_EDGAR"}
        assert registry.find_available(Capability.NEWS) == []
        assert registry.find_available(Capability.REALTIME_QUOTE) == []

    def test_best_provider_with_preferred_ordering(self):
        registry = ProviderCapabilityRegistry()
        a = ProviderCapabilities(provider="A", configured=True)
        a.set_available(Capability.VOLUME)
        b = ProviderCapabilities(provider="B", configured=True)
        b.set_available(Capability.VOLUME)
        registry.register(a)
        registry.register(b)

        assert registry.best_provider(Capability.VOLUME, preferred=["B", "A"]) == "B"
        assert registry.best_provider(Capability.VOLUME, preferred=["A", "B"]) == "A"

    def test_best_provider_returns_none_when_none_available(self):
        registry = ProviderCapabilityRegistry()
        assert registry.best_provider(Capability.FLOAT) is None

    def test_permission_unavailable(self):
        pc = ProviderCapabilities(provider="IBKR", configured=True)
        pc.set_permission_unavailable(Capability.REALTIME_QUOTE, detail="No market data subscription")
        assert pc.status(Capability.REALTIME_QUOTE) == CapabilityStatus.PERMISSION_UNAVAILABLE
        assert not pc.is_available(Capability.REALTIME_QUOTE)

    def test_error_propagation(self):
        pc = ProviderCapabilities(provider="IBKR", configured=True)
        pc.set_error(Capability.DISCOVERY, "Scanner timeout")
        assert pc.status(Capability.DISCOVERY) == CapabilityStatus.ERROR

    def test_serialization(self):
        pc = ProviderCapabilities(provider="IBKR", configured=True, connected=True,
                                   missing_config_keys=[])
        pc.set_available(Capability.DISCOVERY)
        d = pc.as_dict()
        assert d["provider"] == "IBKR"
        assert d["configured"] is True
        assert d["connected"] is True
        assert str(Capability.DISCOVERY) in d["capabilities"]

    def test_registry_serialization(self):
        registry = ProviderCapabilityRegistry()
        ibkr = ProviderCapabilities(provider="IBKR", configured=True)
        registry.register(ibkr)
        d = registry.as_dict()
        assert "providers" in d
        assert "IBKR" in d["providers"]
        assert "generated_at" in d

    def test_missing_config_keys_preserved(self):
        pc = ProviderCapabilities(provider="Finnhub", configured=False,
                                   missing_config_keys=["FINNHUB_API_KEY"])
        assert pc.missing_config_keys == ["FINNHUB_API_KEY"]
        d = pc.as_dict()
        assert "FINNHUB_API_KEY" in d["missing_config_keys"]

    def test_capability_entry_default_untested(self):
        from apps.research_screener.provider_capabilities import CapabilityEntry
        entry = CapabilityEntry(capability=Capability.FLOAT)
        assert entry.status == CapabilityStatus.UNTESTED
        assert entry.detail == ""


class TestFieldSource:
    def test_field_source_dict(self):
        source = FieldSource(
            field="last", provider="IBKR", value=150.25,
            event_time="2026-07-25T14:30:00Z", received_time="2026-07-25T14:30:01Z",
            freshness="CURRENT", evidence_mode="DELAYED",
            selection_reason=FieldSelectionReason.PRIMARY_SOURCE,
            status="KNOWN",
        )
        d = field_source_dict(source)
        assert d["field"] == "last"
        assert d["provider"] == "IBKR"
        assert d["value"] == 150.25
        assert d["selection_reason"] == "PRIMARY_SOURCE"
        assert d["status"] == "KNOWN"

    def test_field_source_with_missing(self):
        source = FieldSource(
            field="float", provider="IBKR", value=None,
            event_time=None, received_time=None,
            freshness="NOT_APPLICABLE", evidence_mode="UNAVAILABLE",
            selection_reason=FieldSelectionReason.ONLY_AVAILABLE,
            status="NOT_CONFIGURED",
            missing_reason="No float provider is configured.",
        )
        d = field_source_dict(source)
        assert d["value"] is None
        assert d["missing_reason"] == "No float provider is configured."


class TestCredentialNonDisclosure:
    def test_registry_never_exposes_keys(self):
        pc = ProviderCapabilities(provider="NewsAPI", configured=False,
                                   missing_config_keys=["NEWSAPI_KEY"])
        d = pc.as_dict()
        # Only the key NAME should be visible
        assert "NEWSAPI_KEY" in str(d["missing_config_keys"])
        # No actual key value should appear
        assert "sk-" not in str(d)
        assert "Bearer" not in str(d)

    def test_capability_dict_never_contains_credential(self):
        pc = ProviderCapabilities(provider="Test", configured=False)
        d = pc.as_dict()
        for key in d:
            assert "key" not in key.lower() or key == "missing_config_keys"
            assert "token" not in key.lower()
            assert "secret" not in key.lower()
            assert "password" not in key.lower()


class TestCapabilityEnum:
    def test_all_capabilities_have_string_values(self):
        for cap in Capability:
            assert isinstance(str(cap), str)
            assert len(str(cap)) > 0

    def test_status_enum_values(self):
        for status in CapabilityStatus:
            assert isinstance(str(status), str)


class TestSECEdgarClient:
    def test_client_creation(self):
        from apps.research_screener.sec_edgar import EdgardClient
        client = EdgardClient()
        assert client is not None

    def test_sec_filing_creation(self):
        from apps.research_screener.sec_edgar import SecFiling
        filing = SecFiling(
            form_type="8-K", accession_number="0001234567-26-000001",
            filed_at="2026-07-25", period_of_report=None,
            primary_document="abc123.htm", issuer_cik="1234567",
        )
        d = filing.as_dict()
        assert d["form_type"] == "8-K"
        assert d["source"] == "SEC_EDGAR"
        assert d["issuer_cik"] == "1234567"

    def test_sec_result_serialization(self):
        from apps.research_screener.sec_edgar import SecFiling, SecResult
        result = SecResult(
            symbol="AAPL", cik="320193", company_name="Apple Inc.",
            filings=[
                SecFiling(form_type="8-K", accession_number="abc", filed_at="2026-07-25",
                          period_of_report=None, primary_document="x.htm", issuer_cik="320193"),
            ],
            retrieved_at="2026-07-25T14:00:00Z",
        )
        d = result.as_dict()
        assert d["symbol"] == "AAPL"
        assert d["cik"] == "320193"
        assert len(d["filings"]) == 1
        assert d["provider"] == "SEC_EDGAR"

    def test_sec_error_result(self):
        from apps.research_screener.sec_edgar import SecResult
        result = SecResult(symbol="INVALID", error="No CIK found")
        assert result.error is not None
        assert len(result.filings) == 0


class TestIBKRGenericTicks:
    def test_generic_tick_list_only_requests_legal_generic_ticks(self):
        from apps.research_screener.ibkr_session import GENERIC_TICK_LIST
        ticks = GENERIC_TICK_LIST.split(",")
        assert "236" in ticks  # shortability
        assert "49" not in ticks  # callback tick type, not a request-list value
        assert "258" not in ticks  # permission-scoped fundamentals can reject base quote
        assert "411" not in ticks  # permission-scoped fundamentals can reject base quote

    def test_quote_ticks_has_fundamentals_field(self):
        from apps.research_screener.ibkr_session import QuoteTicks
        qt = QuoteTicks(symbol="TEST", con_id=123)
        assert hasattr(qt, "fundamentals")
        assert isinstance(qt.fundamentals, dict)

    def test_generic_tick_49_mapped_to_halted(self):
        from apps.research_screener.ibkr_session import _GENERIC_TICKS
        assert _GENERIC_TICKS.get(49) == "halted"

    def test_generic_tick_236_still_mapped(self):
        from apps.research_screener.ibkr_session import _GENERIC_TICKS
        assert _GENERIC_TICKS.get(46) == "shortable_indicator"

    def test_capability_panel_does_not_claim_unobserved_halt_tick(self):
        from apps.research_screener import session_state
        from apps.research_screener.server import ScreenerHandler

        session_state.reset_session()
        try:
            registry = ScreenerHandler._provider_capabilities()
            halt = registry["providers"]["IBKR"]["capabilities"]["HALTS"]
            assert halt["status"] == str(CapabilityStatus.PERMISSION_UNAVAILABLE)
        finally:
            session_state.reset_session()


class TestParseSharesOutstanding:
    def test_parse_numeric_suffix_millions(self):
        from apps.research_screener.session_state import _parse_numeric_suffix
        assert _parse_numeric_suffix("50M") == 50_000_000
        assert _parse_numeric_suffix("1.5M") == 1_500_000

    def test_parse_numeric_suffix_billions(self):
        from apps.research_screener.session_state import _parse_numeric_suffix
        assert _parse_numeric_suffix("2B") == 2_000_000_000

    def test_parse_numeric_suffix_thousands(self):
        from apps.research_screener.session_state import _parse_numeric_suffix
        assert _parse_numeric_suffix("500K") == 500_000

    def test_parse_numeric_suffix_plain(self):
        from apps.research_screener.session_state import _parse_numeric_suffix
        assert _parse_numeric_suffix("12345") == 12345

    def test_parse_numeric_suffix_invalid(self):
        from apps.research_screener.session_state import _parse_numeric_suffix
        assert _parse_numeric_suffix("N/A") is None
        assert _parse_numeric_suffix("") is None
        assert _parse_numeric_suffix("ABC") is None

    def test_parse_shares_outstanding_valid(self):
        from apps.research_screener.session_state import _parse_shares_outstanding
        assert _parse_shares_outstanding("MKTCAP=1.5B;SHARESOUT=50M;PE=15") == 50_000_000
        assert _parse_shares_outstanding("SHARES=100M") == 100_000_000

    def test_parse_shares_outstanding_empty(self):
        from apps.research_screener.session_state import _parse_shares_outstanding
        assert _parse_shares_outstanding("") is None
        assert _parse_shares_outstanding(None) is None
