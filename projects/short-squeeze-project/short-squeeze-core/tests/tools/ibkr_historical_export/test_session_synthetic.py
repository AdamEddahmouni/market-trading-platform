"""Synthetic exercise of the ibapi session callbacks (no socket, no real bars).

Uses real ``ibapi`` ``ContractDetails``/``BarData`` containers populated with fake values.
"""

from __future__ import annotations

import threading
from decimal import Decimal

from ibapi.common import BarData
from ibapi.contract import Contract, ContractDetails

# UNSET_DECIMAL was removed in ibapi 9.81.1. Use float('nan') which
# _decimalMaxString converts to None (matching the old behaviour).
_UNSET_SENTINEL = float('nan')

from tools.ibkr_historical_export.cohort import REQUEST_A
from tools.ibkr_historical_export.session import IbkrSession, make_conid_contract


def _details(con_id=111, symbol="XNCR", sec_type="STK", currency="USD"):
    details = ContractDetails()
    contract = Contract()
    contract.conId = con_id
    contract.symbol = symbol
    contract.localSymbol = symbol
    contract.secType = sec_type
    contract.currency = currency
    contract.exchange = "SMART"
    contract.primaryExchange = "NASDAQ"
    contract.tradingClass = symbol
    details.contract = contract
    details.longName = f"{symbol} Inc"
    details.timeZoneId = "US/Eastern"
    details.validExchanges = "SMART,NASDAQ"
    return details


def _bar(date="1784000000", volume=Decimal("1000"), wap=Decimal("10.25")):
    bar = BarData()
    bar.date = date
    bar.open = 10.0
    bar.high = 11.0
    bar.low = 9.5
    bar.close = 10.5
    bar.volume = volume
    bar.wap = wap
    bar.barCount = 42
    return bar


def test_contract_details_accumulate_and_convert():
    session = IbkrSession()
    session.contractDetails(5, _details(con_id=111))
    session.contractDetails(5, _details(con_id=222, symbol="XNCR"))
    assert len(session._contract_candidates[5]) == 2
    first = session._contract_candidates[5][0]
    assert first.con_id == 111
    assert first.sec_type == "STK"
    assert first.currency == "USD"
    assert first.primary_exchange == "NASDAQ"


def test_contract_details_end_sets_event():
    session = IbkrSession()
    done = threading.Event()
    session._contract_done[7] = done
    session.contractDetailsEnd(7)
    assert done.is_set()


def test_historical_data_converts_bar():
    session = IbkrSession()
    session._req_context[9] = (REQUEST_A.request_name, "XNCR", 111)
    session.historicalData(9, _bar())
    record = session._bars[9][0]
    assert record.timestamp_epoch == 1_784_000_000
    assert record.timestamp_utc.endswith("Z")
    assert record.open == "10.0"
    assert record.volume == "1000"
    assert record.wap == "10.25"
    assert record.bar_count == 42
    assert record.requested_symbol == "XNCR"


def test_unset_volume_wap_become_none():
    session = IbkrSession()
    session._req_context[9] = (REQUEST_A.request_name, "XNCR", 111)
    session.historicalData(9, _bar(volume=_UNSET_SENTINEL, wap=_UNSET_SENTINEL))
    record = session._bars[9][0]
    assert record.volume is None
    assert record.wap is None


def test_error_records_diagnostic_and_ends_request():
    session = IbkrSession()
    hist_done = threading.Event()
    session._hist_done[12] = hist_done
    session.error(12, 354, "Requested market data is not subscribed", "")
    assert hist_done.is_set()
    diags = session.all_diagnostics()
    assert diags[0].error_code == 354


def test_farm_notification_does_not_end_request():
    session = IbkrSession()
    hist_done = threading.Event()
    session._hist_done[12] = hist_done
    session.error(-1, 2106, "HMDS data farm connection is OK", "")
    assert not hist_done.is_set()


def test_managed_accounts_not_stored():
    session = IbkrSession()
    session.managedAccounts("DU1234567,DU7654321")
    # The account identifier must not be retained anywhere on the session.
    blob = repr({k: v for k, v in session.__dict__.items()})
    assert "DU1234567" not in blob
    assert "DU7654321" not in blob
    assert session._ready.is_set()


def test_next_valid_id_marks_ready():
    session = IbkrSession()
    session.nextValidId(1)
    assert session._ready.is_set()


def test_connection_closed_marks_session_not_live():
    session = IbkrSession()
    session.record_endpoint("127.0.0.1", 4001, 27185)
    session.nextValidId(1)
    session.connectionClosed()
    assert session.is_live() is False


def test_disconnect_error_marks_session_not_live():
    session = IbkrSession()
    session.nextValidId(1)
    session.error(-1, 1100, "Connectivity between IB and TWS has been lost", "")
    assert session.is_live() is False


def test_make_conid_contract_fields():
    contract = make_conid_contract(111, "XNCR")
    assert contract.conId == 111
    assert contract.secType == "STK"
    assert contract.exchange == "SMART"
    assert contract.currency == "USD"
