"""Batch 3F-05 external cohort helpers."""

from __future__ import annotations

from datetime import UTC, datetime

from tools.ibkr_historical_export.batch3f05_external import (
    case_id,
    case_ids,
    cohort_boundary,
    forward_window_end,
    request_specs,
    symbols,
)


def test_cohort_boundary_from_fixture():
    document = {
        "rows": [
            {"ticker": "AACB", "observed_at": "2026-08-17T22:09:23.412932Z"},
        ],
    }
    boundary = cohort_boundary(document)
    assert boundary == datetime(2026, 8, 17, 22, 9, 23, 412932, tzinfo=UTC)
    assert forward_window_end(boundary).hour == 22
    assert symbols(document) == ("AACB",)
    assert case_id("AACB", boundary) == "BATCH3F05_AACB_20260817"
    assert case_ids(document)["AACB"] == "BATCH3F05_AACB_20260817"


def test_request_specs_use_boundary():
    boundary = datetime(2026, 8, 17, 22, 9, 23, 412932, tzinfo=UTC)
    specs = request_specs(boundary)
    assert len(specs) == 2
    assert specs[0].request_name == "DETECTION_CONTEXT_PRECEDING_24H"
    assert specs[0].end_datetime == "20260817 22:09:23 UTC"
    assert specs[1].request_name == "FROZEN_FORWARD_24H"
