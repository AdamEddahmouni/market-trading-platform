"""G8 contract resolution tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "providers"))

from market_platform_foundation.providers.ibkr_observational.identity import (
    IdentityAdmissionError,
    Xa01Admission,
)
from market_platform_foundation.xa01.enums import InstrumentKind

from ibkr_observational_support import FakeLookup, make_record
from market_platform_foundation.providers.ibkr_observational.contract_resolution import (
    qualification_from_contract,
    resolve_equity_contract,
    resolve_specific_contract,
)


class FakeQualifyBroker:
    def __init__(self, contracts: dict[str, object] | None = None) -> None:
        self._contracts = contracts or {}

    def qualifyContracts(self, *contracts: object) -> list[object]:
        symbol = str(getattr(contracts[0], "symbol", "") or "")
        if symbol in self._contracts:
            return [self._contracts[symbol]]
        con_id = getattr(contracts[0], "conId", None)
        if con_id is not None:
            return [
                SimpleNamespace(
                    conId=con_id,
                    symbol=symbol or "AAPL",
                    secType="STK",
                    exchange="SMART",
                    currency="USD",
                )
            ]
        return []


class ContractResolutionTests(unittest.TestCase):
    def test_canonical_equity_resolved(self) -> None:
        broker = FakeQualifyBroker(
            {
                "AAPL": SimpleNamespace(
                    conId=265598,
                    symbol="AAPL",
                    secType="STK",
                    exchange="SMART",
                    currency="USD",
                )
            }
        )
        canonical, qual = resolve_equity_contract(
            broker,
            instrument_id="AAPL",
            lookup=FakeLookup(make_record("AAPL")),
        )
        self.assertEqual(canonical, "AAPL")
        self.assertEqual(qual.con_id, 265598)

    def test_ambiguous_display_symbol_fails(self) -> None:
        broker = FakeQualifyBroker()
        with self.assertRaises(IdentityAdmissionError):
            resolve_equity_contract(
                broker,
                instrument_id="UNKNOWN",
                lookup=FakeLookup(),
            )

    def test_unknown_conid_fails(self) -> None:
        with self.assertRaises(ValueError):
            qualification_from_contract(SimpleNamespace(conId=0))

    def test_provider_alias_cannot_replace_canonical_identity(self) -> None:
        qual = qualification_from_contract(
            SimpleNamespace(
                conId=999, symbol="AAPL", secType="STK", exchange="SMART", currency="USD"
            )
        )
        self.assertEqual(qual.con_id, 999)
        self.assertNotEqual(qual.symbol, "")

    def test_specific_option_contract_accepted(self) -> None:
        broker = FakeQualifyBroker()
        option = SimpleNamespace(
            symbol="AAPL",
            secType="OPT",
            conId=123,
            exchange="SMART",
            currency="USD",
            strike=150.0,
            right="C",
            lastTradeDateOrContractMonth="20251219",
        )
        record = make_record("AAPL250119C00150000", kind=InstrumentKind.OPTION_CONTRACT)
        canonical, qual = resolve_specific_contract(
            broker,
            instrument_id="AAPL250119C00150000",
            contract_builder=option,
            lookup=FakeLookup(record),
        )
        self.assertEqual(canonical, "AAPL250119C00150000")
        self.assertEqual(qual.con_id, 123)

    def test_underlying_only_option_fails(self) -> None:
        broker = FakeQualifyBroker()
        option = SimpleNamespace(symbol="AAPL", secType="OPT", exchange="SMART", currency="USD")
        with self.assertRaises(IdentityAdmissionError):
            resolve_specific_contract(
                broker,
                instrument_id="AAPL250119C00150000",
                contract_builder=option,
            )

    def test_specific_future_contract_accepted(self) -> None:
        broker = FakeQualifyBroker()
        future = SimpleNamespace(
            symbol="ES",
            secType="FUT",
            conId=555,
            exchange="CME",
            currency="USD",
            lastTradeDateOrContractMonth="202512",
        )
        record = make_record("ESZ5", kind=InstrumentKind.FUTURE_CONTRACT)
        gate = Xa01Admission()
        admitted = gate.admit_with_lookup(instrument_id="ESZ5", lookup=FakeLookup(record))
        qualified = broker.qualifyContracts(future)
        qual = qualification_from_contract(qualified[0])
        self.assertEqual(admitted.instrument_id, "ESZ5")
        self.assertEqual(qual.con_id, 555)

    def test_future_family_fails_via_admission(self) -> None:
        record = make_record("ES", kind=InstrumentKind.FUTURE_FAMILY)
        gate = Xa01Admission()
        with self.assertRaises(IdentityAdmissionError):
            gate.admit_with_lookup(instrument_id="ES", lookup=FakeLookup(record))

    def test_continuous_future_fails(self) -> None:
        record = make_record("ES1!", kind=InstrumentKind.CONTINUOUS_SERIES)
        gate = Xa01Admission()
        with self.assertRaises(IdentityAdmissionError):
            gate.admit_with_lookup(instrument_id="ES1!", lookup=FakeLookup(record))

    def test_provider_conid_provenance_preserved(self) -> None:
        qual = qualification_from_contract(
            SimpleNamespace(
                conId=42,
                symbol="NVDA",
                secType="STK",
                exchange="SMART",
                currency="USD",
                multiplier="1",
            )
        )
        self.assertEqual(qual.con_id, 42)
        self.assertEqual(qual.multiplier, "1")

    def test_no_silent_multiplier_fabrication(self) -> None:
        qual = qualification_from_contract(
            SimpleNamespace(conId=42, symbol="NVDA", secType="STK", exchange="SMART", currency="USD")
        )
        self.assertIsNone(qual.multiplier)

    def test_no_provider_request_before_identity_admission(self) -> None:
        broker = FakeQualifyBroker()
        calls: list[object] = []
        broker.qualifyContracts = lambda *a, **k: calls.append(a) or []  # type: ignore[method-assign]
        with self.assertRaises(IdentityAdmissionError):
            resolve_equity_contract(broker, instrument_id="UNKNOWN", lookup=FakeLookup())
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
