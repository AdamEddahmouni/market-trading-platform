"""Fixture-first SEC EDGAR disclosure adapter (PORT_ADAPT)."""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from ...canonical import canonical_bytes, sha256_bytes
from ...contracts.identity import normalized_event_id
from ...normalization.equity_bars import iso_to_epoch_ns
from ..contracts import ProviderResult, SymbolMapping
from ...donor_patterns.edgar_whale import is_13f_form, resolve_holding_instrument_id
from ..envelope import (
    build_disclosure_envelope,
    build_provider_metadata,
    filing_to_disclosure_event,
)
from ...donor_patterns.edgar_whale import is_13f_form

DEFAULT_FIXTURE = (
    Path(__file__).resolve().parents[4]
    / "tests"
    / "fixtures"
    / "providers"
    / "edgar"
    / "biya_disclosures.json"
)
MIN_INTERVAL_S = 0.15
LIVE_TIMEOUT_S = 15.0
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{}.json"


class FixtureEdgarDisclosureProvider:
    """Offline-first EDGAR adapter using captured submission fixtures."""

    provider_id = "sec.edgar.fixture"
    capability = "disclosure"
    entitlement = "PUBLIC_EDGAR_FIXTURE"

    def __init__(self, *, fixture_path: Path | None = None, ingest_run_id: str | None = None) -> None:
        self.fixture_path = fixture_path or DEFAULT_FIXTURE
        self.ingest_run_id = ingest_run_id or sha256_bytes(
            canonical_bytes({"fixture_path": str(self.fixture_path), "provider": self.provider_id})
        )
        self._fixture = self._load_fixture()

    def _load_fixture(self) -> dict[str, Any]:
        payload = json.loads(
            self.fixture_path.read_text(encoding="utf-8"),
            object_pairs_hook=_pairs_no_duplicates,
        )
        if not isinstance(payload, dict):
            raise ValueError("EDGAR_FIXTURE_INVALID")
        return payload

    def fetch_disclosures(
        self,
        symbol: str,
        *,
        as_of_time_ns: int | None = None,
    ) -> ProviderResult:
        fixture_symbol = str(self._fixture.get("symbol", "")).upper()
        if symbol.upper() != fixture_symbol:
            return ProviderResult(
                status="unavailable",
                reason_code="EDGAR_SYMBOL_NOT_IN_FIXTURE",
                provider_id=self.provider_id,
                capability=self.capability,
            )
        events = self.build_envelopes(as_of_time_ns=as_of_time_ns)
        if not events:
            return ProviderResult(
                status="unavailable",
                reason_code="EDGAR_NO_ELIGIBLE_FILINGS",
                provider_id=self.provider_id,
                capability=self.capability,
            )
        return ProviderResult(
            status="available",
            events=tuple(events),
            provider_id=self.provider_id,
            capability=self.capability,
        )

    def build_envelopes(self, *, as_of_time_ns: int | None = None) -> list[dict[str, Any]]:
        symbol = str(self._fixture["symbol"]).upper()
        instrument_id = symbol
        mapping = SymbolMapping(provider_symbol=symbol, instrument_id=instrument_id)
        filings = self._fixture.get("filings", [])
        if not isinstance(filings, list):
            return []
        envelopes: list[dict[str, Any]] = []
        for filing in filings:
            if not isinstance(filing, dict):
                continue
            accepted_at = str(filing.get("accepted_at", ""))
            if not accepted_at:
                continue
            available_time_ns = iso_to_epoch_ns(accepted_at)
            if as_of_time_ns is not None and available_time_ns > as_of_time_ns:
                continue
            accession = str(filing.get("accession_number", ""))
            revision = str(filing.get("source_revision_id", "1"))
            form_type = str(filing.get("form_type", ""))
            quarter_end = filing.get("quarter_end")
            holdings = filing.get("holdings")
            holdings_list = holdings if isinstance(holdings, list) else None
            if is_13f_form(form_type) and holdings_list:
                for holding in holdings_list:
                    if not isinstance(holding, dict):
                        continue
                    holding_instrument = resolve_holding_instrument_id(
                        holding,
                        default_symbol=symbol,
                    )
                    cusip = str(holding.get("cusip", "")).strip()
                    if not cusip:
                        continue
                    holding_mapping = SymbolMapping(
                        provider_symbol=holding_instrument,
                        instrument_id=holding_instrument,
                    )
                    disclosure = filing_to_disclosure_event(
                        form_type=form_type,
                        filer=str(filing.get("filer", "")),
                        issuer=str(filing.get("issuer", symbol)),
                        accepted_at=accepted_at,
                        source_url=str(filing.get("source_url", "")),
                        accession_number=accession,
                        is_amendment=bool(filing.get("is_amendment")),
                        source_revision_id=revision,
                        quarter_end=str(quarter_end) if quarter_end is not None else None,
                        holdings=[holding],
                    )
                    source_record_id = f"{accession}:{cusip}"
                    normalized_id = normalized_event_id(
                        provider_id=self.provider_id,
                        venue_id="SEC",
                        publisher_id="SEC_EDGAR",
                        channel_id=holding_instrument,
                        source_instance_id=str(self._fixture.get("fixture_id", "FIXTURE-EDGAR")),
                        source_record_id=source_record_id,
                        source_revision_id=revision,
                        event_family="DISCLOSURE_EVENT",
                    )
                    provider_metadata = build_provider_metadata(
                        provider_id=self.provider_id,
                        entitlement=self.entitlement,
                        event_time_ns=available_time_ns,
                        receive_time_ns=available_time_ns,
                        symbol_mapping=holding_mapping,
                        raw_source_reference=f"{self.fixture_path.name}:{source_record_id}:{revision}",
                    )
                    envelopes.append(
                        build_disclosure_envelope(
                            normalized_event_id=normalized_id,
                            source_record_id=source_record_id,
                            instrument_id=holding_instrument,
                            event_time_ns=available_time_ns,
                            available_time_ns=available_time_ns,
                            ingest_run_id=self.ingest_run_id,
                            provider_metadata=provider_metadata,
                            disclosure_event=disclosure,
                        )
                    )
                continue
            disclosure = filing_to_disclosure_event(
                form_type=form_type,
                filer=str(filing.get("filer", "")),
                issuer=str(filing.get("issuer", symbol)),
                accepted_at=accepted_at,
                source_url=str(filing.get("source_url", "")),
                accession_number=accession,
                is_amendment=bool(filing.get("is_amendment")),
                transaction_code=filing.get("transaction_code"),
                source_revision_id=revision,
                transaction_date=filing.get("transaction_date"),
                shares=filing.get("shares"),
                price_per_share=filing.get("price_per_share"),
                shares_owned_following=filing.get("shares_owned_following"),
                is_10b5_1=filing.get("is_10b5_1"),
                stake_percent=filing.get("stake_percent"),
                campaign_objective=filing.get("campaign_objective"),
                is_passive=filing.get("is_passive"),
                quarter_end=str(quarter_end) if quarter_end is not None else None,
                holdings=holdings_list,
            )
            event_time_ns = available_time_ns
            normalized_id = normalized_event_id(
                provider_id=self.provider_id,
                venue_id="SEC",
                publisher_id="SEC_EDGAR",
                channel_id=symbol,
                source_instance_id=str(self._fixture.get("fixture_id", "FIXTURE-EDGAR")),
                source_record_id=accession,
                source_revision_id=revision,
                event_family="DISCLOSURE_EVENT",
            )
            provider_metadata = build_provider_metadata(
                provider_id=self.provider_id,
                entitlement=self.entitlement,
                event_time_ns=event_time_ns,
                receive_time_ns=available_time_ns,
                symbol_mapping=mapping,
                raw_source_reference=f"{self.fixture_path.name}:{accession}:{revision}",
            )
            envelopes.append(
                build_disclosure_envelope(
                    normalized_event_id=normalized_id,
                    source_record_id=accession,
                    instrument_id=instrument_id,
                    event_time_ns=event_time_ns,
                    available_time_ns=available_time_ns,
                    ingest_run_id=self.ingest_run_id,
                    provider_metadata=provider_metadata,
                    disclosure_event=disclosure,
                )
            )
        return _sort_envelopes(envelopes)


class LiveEdgarDisclosureProvider(FixtureEdgarDisclosureProvider):
    """Live EDGAR fetch — only when IMP_EDGAR_LIVE=1 and SEC_USER_AGENT is set."""

    provider_id = "sec.edgar.live"
    entitlement = "PUBLIC_EDGAR_LIVE"

    _lock = threading.Lock()
    _last_request = 0.0

    def __init__(self, *, user_agent: str, cik: str) -> None:
        super().__init__(fixture_path=DEFAULT_FIXTURE)
        self.user_agent = user_agent
        self.cik = cik.zfill(10)

    def _throttle(self) -> None:
        with self._lock:
            elapsed = time.monotonic() - self._last_request
            if elapsed < MIN_INTERVAL_S:
                time.sleep(MIN_INTERVAL_S - elapsed)
            self._last_request = time.monotonic()

    def fetch_disclosures(
        self,
        symbol: str,
        *,
        as_of_time_ns: int | None = None,
    ) -> ProviderResult:
        del as_of_time_ns
        if symbol.upper() != str(self._fixture.get("symbol", "")).upper():
            return ProviderResult(
                status="unavailable",
                reason_code="EDGAR_SYMBOL_NOT_IN_FIXTURE",
                provider_id=self.provider_id,
                capability=self.capability,
            )
        try:
            self._throttle()
            url = SUBMISSIONS_URL.format(self.cik)
            request = Request(url, headers={"User-Agent": self.user_agent, "Accept-Encoding": "gzip"})
            with urlopen(request, timeout=LIVE_TIMEOUT_S) as response:
                raw = response.read()
            if response.headers.get("Content-Encoding") == "gzip":
                import gzip

                raw = gzip.decompress(raw)
            payload = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs_no_duplicates)
        except OSError as exc:
            return ProviderResult(
                status="unavailable",
                reason_code=f"EDGAR_LIVE_ERROR:{exc.__class__.__name__}",
                provider_id=self.provider_id,
                capability=self.capability,
            )
        # Live mode still normalizes through fixture mapping for v1 safety.
        del payload
        return super().fetch_disclosures(symbol)


def build_edgar_provider(*, fixture_path: Path | None = None) -> FixtureEdgarDisclosureProvider:
    if os.environ.get("IMP_EDGAR_LIVE") == "1":
        user_agent = os.environ.get("SEC_USER_AGENT", "").strip()
        if user_agent:
            fixture = FixtureEdgarDisclosureProvider(fixture_path=fixture_path)
            cik = str(fixture._fixture.get("cik", ""))
            if cik:
                return LiveEdgarDisclosureProvider(user_agent=user_agent, cik=cik)
    return FixtureEdgarDisclosureProvider(fixture_path=fixture_path)


def _sort_envelopes(envelopes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        envelopes,
        key=lambda row: (
            int(row["available_time"]),
            str(row["source_record_id"]),
            str(row["source_revision_id"]),
        ),
    )


def _pairs_no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


__all__ = [
    "DEFAULT_FIXTURE",
    "FixtureEdgarDisclosureProvider",
    "LiveEdgarDisclosureProvider",
    "build_edgar_provider",
]
