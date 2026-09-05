"""Frozen cohort symbol list consistency across acquisition modules."""

from __future__ import annotations

from squeeze_core.acquisition.operation_readiness.evidence_inputs import FROZEN_COHORT
from tools.ibkr_historical_export import cohort

from scripts.acquisition.build_evidence_bundles import PRIMARY_EXCHANGE


def test_frozen_cohort_symbols_match_ibkr_export():
    symbols_from_inputs = tuple(symbol for symbol, _ in FROZEN_COHORT)
    assert cohort.FROZEN_SYMBOLS == symbols_from_inputs


def test_frozen_cohort_case_ids_match_ibkr_export():
    for symbol, case_id in FROZEN_COHORT:
        assert cohort.CASE_IDS[symbol] == case_id


def test_evidence_bundle_primary_exchange_covers_frozen_cohort():
    symbols_from_inputs = {symbol for symbol, _ in FROZEN_COHORT}
    assert set(PRIMARY_EXCHANGE) == symbols_from_inputs
