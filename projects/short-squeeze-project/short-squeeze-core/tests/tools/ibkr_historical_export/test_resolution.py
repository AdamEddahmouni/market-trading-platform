"""Outcome-blind contract resolution."""

from __future__ import annotations

from tools.ibkr_historical_export.resolution import resolve_contract
from tools.ibkr_historical_export.statuses import ContractStatus

from ._fakes import make_candidate as _cand


def test_single_candidate_resolves():
    res = resolve_contract("XNCR", [_cand(symbol="XNCR", con_id=111)])
    assert res.status is ContractStatus.CONTRACT_RESOLVED
    assert res.resolved.con_id == 111


def test_no_matching_candidate_not_resolved():
    res = resolve_contract("XNCR", [_cand(symbol="OTHER", con_id=222)])
    assert res.status is ContractStatus.CONTRACT_NOT_RESOLVED
    assert res.resolved is None


def test_empty_candidates_not_resolved():
    res = resolve_contract("XNCR", [])
    assert res.status is ContractStatus.CONTRACT_NOT_RESOLVED


def test_two_distinct_conids_ambiguous():
    res = resolve_contract("XNCR", [
        _cand(symbol="XNCR", con_id=111),
        _cand(symbol="XNCR", con_id=333),
    ])
    assert res.status is ContractStatus.CONTRACT_AMBIGUOUS
    assert res.resolved is None


def test_duplicate_same_conid_collapses_to_resolved():
    res = resolve_contract("XNCR", [
        _cand(symbol="XNCR", con_id=111, exchange="SMART"),
        _cand(symbol="XNCR", con_id=111, exchange="NASDAQ"),
    ])
    assert res.status is ContractStatus.CONTRACT_RESOLVED
    assert res.resolved.con_id == 111


def test_non_usd_rejected():
    res = resolve_contract("XNCR", [_cand(symbol="XNCR", con_id=111, currency="EUR")])
    assert res.status is ContractStatus.CONTRACT_NOT_RESOLVED


def test_non_stk_rejected():
    res = resolve_contract("XNCR", [_cand(symbol="XNCR", con_id=111, sec_type="OPT")])
    assert res.status is ContractStatus.CONTRACT_NOT_RESOLVED


def test_zero_conid_rejected():
    res = resolve_contract("XNCR", [_cand(symbol="XNCR", con_id=0)])
    assert res.status is ContractStatus.CONTRACT_NOT_RESOLVED


def test_local_symbol_match_accepted():
    res = resolve_contract("XNCR", [_cand(symbol="OTHER", local_symbol="XNCR", con_id=111)])
    assert res.status is ContractStatus.CONTRACT_RESOLVED


def test_all_candidates_preserved():
    cands = [_cand(symbol="XNCR", con_id=111), _cand(symbol="ZZZ", con_id=999)]
    res = resolve_contract("XNCR", cands)
    assert len(res.candidates) == 2
