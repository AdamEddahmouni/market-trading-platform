"""Cohort registry tests for multi-boundary acquisition tracks."""

from __future__ import annotations

from squeeze_core.acquisition.cohort_registry import (
    batch3f05_cohort_cases,
    frozen_cohort_cases,
    resolve_cohort_cases,
)
from squeeze_core.acquisition.operation_readiness.evidence_inputs import FROZEN_BOUNDARY, FROZEN_COHORT


def test_frozen_cohort_cases_match_frozen_cohort_constant():
    cases = frozen_cohort_cases()
    assert len(cases) == len(FROZEN_COHORT)
    assert [(c.symbol, c.case_id) for c in cases] == list(FROZEN_COHORT)
    assert all(case.boundary == FROZEN_BOUNDARY for case in cases)


def test_batch3f05_cohort_cases_loaded_from_discovery():
    cases = batch3f05_cohort_cases()
    assert len(cases) == 5
    symbols = {case.symbol for case in cases}
    assert symbols == {"AACB", "AACG", "AACI", "AACP", "AADX"}
    assert all(case.case_id.startswith("BATCH3F05_") for case in cases)
    assert len({case.boundary for case in cases}) == 1
    assert cases[0].boundary != FROZEN_BOUNDARY


def test_resolve_cohort_all_combines_tracks():
    all_cases = resolve_cohort_cases("all")
    assert len(all_cases) == len(FROZEN_COHORT) + 5
