"""Lane C isolated SEC insider disclosure vertical tests."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from market_platform_foundation.intelligence.contracts import (
    ContractKind,
    ContractReference,
    IntelligenceScope,
    QualityState,
    QualitySummary,
    SemanticEventType,
    SnapshotV1,
)
from market_platform_foundation.intelligence.normalization.models import (
    AvailabilityBasis,
    IngestionMode,
    NormalizationContext,
)
from market_platform_foundation.intelligence.normalization.providers.market_trackers_sec_insider import (
    normalize_sec_insider_row,
)
from market_platform_foundation.intelligence.normalization.providers.sec_edgar import normalize_sec_filing
from market_platform_foundation.intelligence.opportunity.sec_insider import (
    EXPERT_ID,
    LANE_B_EVENT_TYPE,
    LANE_PAYLOAD_KIND,
    SecInsiderFailureCode,
    assert_candidate_not_form4_directional,
    filing_payload_with_sec_insider_section,
    is_lane_b_insider_ownership_event,
    run_sec_insider_vertical,
)
from market_platform_foundation.intelligence.opportunity.sec_insider.constants import (
    FORBIDDEN_CANDIDATE_DIRECTIONS,
)

_MT_FIXTURE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "market_trackers" / "sec_insider" / "form4_open_market_purchase.json"
)
_EDGAR_FIXTURE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "sec_edgar" / "insider_form4_nvda_submission.json"
)
_PLATFORM_RECEIVED_NS = 1_725_100_800_000_000_000
ONE_DAY = 86_400_000_000_000


def _snapshot(*, decision_time_ns: int, instrument: str = "xa01.provisional:US:NVDA") -> SnapshotV1:
    return SnapshotV1(
        snapshot_id="SNAP-SEC-LANE-C",
        schema_version="1",
        decision_time_ns=decision_time_ns,
        scope=IntelligenceScope(instrument_ids=(instrument,)),
        quality=QualitySummary(state=QualityState.GOOD),
        source_event_refs=(ContractReference(kind=ContractKind.EVENT.value, id="EVT-SEC-1"),),
    )


def _lane_b_event_from_row(*, transaction_code: str = "P"):
    row = json.loads(_MT_FIXTURE.read_text(encoding="utf-8"))
    row = dict(row)
    row["code"] = transaction_code
    edgar = json.loads(_EDGAR_FIXTURE.read_text(encoding="utf-8"))
    ctx = NormalizationContext(
        received_time_ns=_PLATFORM_RECEIVED_NS,
        ingestion_mode=IngestionMode.FIXTURE,
    )
    result = normalize_sec_insider_row(row, context=ctx, edgar_primary=edgar)
    assert result.event is not None, result.diagnostics
    return result.event


def _legacy_event_from_fixture(*, transaction_code: str = "P"):
    row = json.loads(_MT_FIXTURE.read_text(encoding="utf-8"))
    row = dict(row)
    row["code"] = transaction_code
    filing = {
        "accession_number": row["accessionNumber"],
        "form_type": row["formType"],
        "filing_date": row["filedAt"],
        "acceptance_datetime": f"{row['filedAt']}T16:05:03",
        "cik": row["issuerCik"],
    }
    ctx = NormalizationContext(
        received_time_ns=_PLATFORM_RECEIVED_NS,
        ingestion_mode=IngestionMode.HISTORICAL_RECONSTRUCTED,
        historical_available_time_ns=_PLATFORM_RECEIVED_NS + ONE_DAY,
        availability_basis=AvailabilityBasis.PUBLICATION_TIME,
    )
    normalized = normalize_sec_filing(filing, context=ctx, instrument_id="US:NVDA")
    assert normalized.event is not None
    payload = filing_payload_with_sec_insider_section(normalized.event.payload, sec_insider_row=row)
    base = normalized.event
    from market_platform_foundation.intelligence.contracts import EventV1

    return EventV1(
        event_id=base.event_id,
        schema_version=base.schema_version,
        event_type=base.event_type,
        event_time_ns=base.event_time_ns,
        available_time_ns=base.available_time_ns,
        payload=payload,
        quality=base.quality,
        source=base.source,
        instrument_id=base.instrument_id,
        provider_time_ns=base.provider_time_ns,
        received_time_ns=base.received_time_ns,
    )


class SecInsiderLaneBBindTests(unittest.TestCase):
    def test_normalize_sec_insider_row_to_vertical(self) -> None:
        event = _lane_b_event_from_row(transaction_code="P")
        self.assertEqual(event.event_type, LANE_B_EVENT_TYPE)
        self.assertTrue(is_lane_b_insider_ownership_event(event))
        self.assertIn("clocks", event.payload)
        self.assertNotIn("sec_insider", event.payload)
        clocks = event.payload["clocks"]
        economic = clocks["economic_event_time_ns"]
        assert economic is not None
        self.assertGreater(event.available_time_ns, economic)
        snapshot = _snapshot(decision_time_ns=event.available_time_ns + ONE_DAY, instrument=event.instrument_id or "")
        result = run_sec_insider_vertical(event=event, snapshot=snapshot)
        self.assertTrue(result.ok, result.reason_codes)
        assert result.detection is not None
        assert result.evidence is not None
        assert result.candidate is not None
        self.assertEqual(result.detection.semantic_event_type, SemanticEventType.SEC_INSIDER_DISCLOSURE)
        self.assertEqual(result.evidence.expert_id, EXPERT_ID)
        self.assertIsNone(result.evidence.directional_score)

    def test_lane_b_form4_p_and_d_never_set_trade_direction(self) -> None:
        for code in ("P", "D"):
            with self.subTest(code=code):
                event = _lane_b_event_from_row(transaction_code=code)
                snapshot = _snapshot(
                    decision_time_ns=event.available_time_ns + ONE_DAY,
                    instrument=event.instrument_id or "",
                )
                result = run_sec_insider_vertical(event=event, snapshot=snapshot)
                self.assertTrue(result.ok, result.reason_codes)
                assert result.candidate is not None
                assert result.evidence is not None
                expression = str(result.candidate["direction_or_expression"]).upper()
                self.assertNotIn(expression, FORBIDDEN_CANDIDATE_DIRECTIONS)
                self.assertIsNone(result.evidence.directional_score)
                assert_candidate_not_form4_directional(result.candidate)


class SecInsiderLegacyCompatTests(unittest.TestCase):
    def test_legacy_filing_payload_adapter_still_works(self) -> None:
        event = _legacy_event_from_fixture(transaction_code="P")
        snapshot = _snapshot(decision_time_ns=event.available_time_ns + ONE_DAY)
        result = run_sec_insider_vertical(event=event, snapshot=snapshot)
        self.assertTrue(result.ok, result.reason_codes)
        self.assertEqual(event.payload.get("lane_payload_kind"), LANE_PAYLOAD_KIND)

    def test_fail_closed_when_snapshot_before_availability(self) -> None:
        event = _lane_b_event_from_row()
        snapshot = _snapshot(decision_time_ns=event.available_time_ns - 1, instrument=event.instrument_id or "")
        result = run_sec_insider_vertical(event=event, snapshot=snapshot)
        self.assertFalse(result.ok)
        self.assertIn(SecInsiderFailureCode.SNAPSHOT_BEFORE_AVAILABILITY.value, result.reason_codes)

    def test_fail_closed_when_plain_filing_without_lane_b_or_legacy_section(self) -> None:
        filing = {
            "accession_number": "0001045810-25-000011",
            "form_type": "4",
            "filing_date": "2025-01-17",
            "acceptance_datetime": "2025-01-17T16:05:03",
            "cik": "0001045810",
        }
        ctx = NormalizationContext(
            received_time_ns=_PLATFORM_RECEIVED_NS,
            ingestion_mode=IngestionMode.HISTORICAL_RECONSTRUCTED,
            historical_available_time_ns=_PLATFORM_RECEIVED_NS + ONE_DAY,
            availability_basis=AvailabilityBasis.PUBLICATION_TIME,
        )
        normalized = normalize_sec_filing(filing, context=ctx, instrument_id="US:NVDA")
        assert normalized.event is not None
        event = normalized.event
        snapshot = _snapshot(decision_time_ns=event.available_time_ns + ONE_DAY)
        result = run_sec_insider_vertical(event=event, snapshot=snapshot)
        self.assertFalse(result.ok)
        self.assertIn(SecInsiderFailureCode.EVENT_NOT_ACCEPTED.value, result.reason_codes)


if __name__ == "__main__":
    unittest.main()
