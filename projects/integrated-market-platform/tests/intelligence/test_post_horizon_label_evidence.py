"""Post-horizon label evidence and leakage tests (IMP-DUAL-CORPUS-01 Lane C)."""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.outcomes.historical_trade_retrieval import (  # noqa: E402
    retrieve_historical_trades_bounded,
)
from market_platform_foundation.intelligence.outcomes.label_evidence import (  # noqa: E402
    BAR_OHLCV_REFUSED_FOR_PATH_A_LABEL,
    HISTORICAL_EVENT_NOT_PROSPECTIVE,
    IMPLICIT_LABEL_COLUMN_MERGE_REFUSED,
    INSTRUMENT_OR_HASH_MISMATCH,
    MALFORMED_PROVIDER_TRADE_RECORD,
    NO_ELIGIBLE_TRADE,
    RETRIEVAL_BEFORE_TERMINAL_WINDOW_END,
    LabelEvidenceError,
    assert_feature_constructor_corpus_safe,
    assert_retrieval_not_before_terminal_window,
    attach_label_evidence,
    derive_source_observation_hash,
    select_terminal_trade,
)
from market_platform_foundation.paper.calibration.dual_corpus.consumption import (  # noqa: E402
    CONSUMPTION_REFUSED_PROTECTED_CORPUS,
    ProtectedCorpusConsumptionError,
    assert_corpus_consumable_for_selection_or_training,
)
from market_platform_foundation.paper.calibration.dual_corpus.evidence_authority import (  # noqa: E402
    CORPUS_EVIDENCE_AUTHORITY_PROSPECTIVE_FEATURE_EVIDENCE,
    CORPUS_EVIDENCE_AUTHORITY_UNTOUCHED_FORWARD_EVALUATION,
)
from market_platform_foundation.providers.ibkr_observational.historical_trades import (  # noqa: E402
    BAR_OHLCV_PAYLOAD_REFUSED,
    normalize_ibkr_historical_trades_payload,
)

SIGNAL_NS = 1_000_000_000_000
HORIZON_NS = 300_000_000_000
TARGET_NS = SIGNAL_NS + HORIZON_NS
WINDOW_END_NS = TARGET_NS + 60_000_000_000
REQUEST_OK_NS = WINDOW_END_NS
INSTRUMENT = "AAPL"


def _sample_source(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "source_observation_id": "SRC-TEST-001",
        "source_evidence_class": CORPUS_EVIDENCE_AUTHORITY_PROSPECTIVE_FEATURE_EVIDENCE,
        "instrument_id": INSTRUMENT,
        "signal_time_ns": SIGNAL_NS,
        "feature_cutoff_ns": SIGNAL_NS,
        "horizon_ns": HORIZON_NS,
        "source_code_sha": "deadbeef",
        "p0": {
            "event_id": "p0-trade-1",
            "price": 100.0,
            "event_time_ns": SIGNAL_NS,
            "available_time_ns": SIGNAL_NS,
            "observation_kind": "TRADE",
        },
    }
    body.update(overrides)
    body["source_observation_hash"] = derive_source_observation_hash(body)
    return body


def _terminal_trade(*, price: float, event_time_ns: int = TARGET_NS, trade_id: str = "t1") -> dict[str, object]:
    return {
        "instrument_id": INSTRUMENT,
        "observation_kind": "TRADE",
        "price": price,
        "event_time_ns": event_time_ns,
        "available_time_ns": event_time_ns,
        "trade_id": trade_id,
    }


class _FakeTradePort:
    def __init__(self, trades: list[dict[str, object]]) -> None:
        self._trades = trades

    def fetch_trades_for_window(self, **kwargs: object) -> dict[str, object]:
        return {
            "trades": self._trades,
            "provider_id": "ibkr.observational",
            "capability_id": "IBKR_HISTORICAL_TRADES",
            "raw_trade_ref": "fixture",
            "raw_trade_payload_sha256": "abc",
        }


class PostHorizonLabelEvidenceTests(unittest.TestCase):
    def test_attach_does_not_mutate_source_observation(self) -> None:
        source = _sample_source()
        before = copy.deepcopy(source)
        result = attach_label_evidence(
            source,
            trades=[_terminal_trade(price=110.0)],
            request_time_ns=REQUEST_OK_NS,
            actual_retrieval_time_ns=REQUEST_OK_NS + 1,
            provider_id="ibkr.observational",
            capability_id="IBKR_HISTORICAL_TRADES",
            retrieval_params={"useRTH": True},
            raw_trade_ref="fixture",
            raw_trade_payload_sha256="abc",
            source_code_sha="deadbeef",
            labeler_code_sha="cafebabe",
        )
        self.assertEqual(source, before)
        self.assertEqual(result.source_observation, before)

    def test_source_hash_identical_before_and_after_attach(self) -> None:
        source = _sample_source()
        before_hash = derive_source_observation_hash(source)
        result = attach_label_evidence(
            source,
            trades=[_terminal_trade(price=105.0)],
            request_time_ns=REQUEST_OK_NS,
            actual_retrieval_time_ns=REQUEST_OK_NS,
            provider_id="ibkr.observational",
            capability_id="IBKR_HISTORICAL_TRADES",
            retrieval_params={},
            raw_trade_ref="fixture",
            raw_trade_payload_sha256="abc",
            source_code_sha="deadbeef",
            labeler_code_sha="cafebabe",
        )
        self.assertEqual(result.source_hash_before, before_hash)
        self.assertEqual(result.source_hash_after, before_hash)

    def test_retrieval_before_terminal_window_end_refused(self) -> None:
        with self.assertRaises(LabelEvidenceError) as ctx:
            assert_retrieval_not_before_terminal_window(
                request_time_ns=WINDOW_END_NS - 1,
                terminal_window_end_ns=WINDOW_END_NS,
            )
        self.assertEqual(ctx.exception.reason_code, RETRIEVAL_BEFORE_TERMINAL_WINDOW_END)

    def test_valid_post_window_accepted(self) -> None:
        result = attach_label_evidence(
            _sample_source(),
            trades=[_terminal_trade(price=111.0)],
            request_time_ns=REQUEST_OK_NS,
            actual_retrieval_time_ns=REQUEST_OK_NS,
            provider_id="ibkr.observational",
            capability_id="IBKR_HISTORICAL_TRADES",
            retrieval_params={},
            raw_trade_ref="fixture",
            raw_trade_payload_sha256="abc",
            source_code_sha="deadbeef",
            labeler_code_sha="cafebabe",
        )
        self.assertEqual(result.label_evidence["direction_label"], "LONG")
        self.assertIsNone(result.label_evidence["refusal_reason"])

    def test_no_trade_unlabelable(self) -> None:
        result = attach_label_evidence(
            _sample_source(),
            trades=[],
            request_time_ns=REQUEST_OK_NS,
            actual_retrieval_time_ns=REQUEST_OK_NS,
            provider_id="ibkr.observational",
            capability_id="IBKR_HISTORICAL_TRADES",
            retrieval_params={},
            raw_trade_ref="fixture",
            raw_trade_payload_sha256="abc",
            source_code_sha="deadbeef",
            labeler_code_sha="cafebabe",
        )
        self.assertEqual(result.label_evidence["refusal_reason"], NO_ELIGIBLE_TRADE)
        self.assertEqual(result.label_evidence["terminal_candidates"], [])

    def test_no_eligible_trade_terminal_candidates_are_filtered_not_full_tape(self) -> None:
        out_of_window = _terminal_trade(price=101.0, event_time_ns=TARGET_NS - 1_000_000_000)
        result = attach_label_evidence(
            _sample_source(),
            trades=[out_of_window],
            request_time_ns=REQUEST_OK_NS,
            actual_retrieval_time_ns=REQUEST_OK_NS,
            provider_id="ibkr.observational",
            capability_id="IBKR_HISTORICAL_TRADES",
            retrieval_params={},
            raw_trade_ref="fixture",
            raw_trade_payload_sha256="abc",
            source_code_sha="deadbeef",
            labeler_code_sha="cafebabe",
        )
        self.assertEqual(result.label_evidence["refusal_reason"], NO_ELIGIBLE_TRADE)
        self.assertEqual(result.label_evidence["terminal_candidates"], [])
        self.assertEqual(result.label_evidence["returned_trade_count"], 1)

    def test_bar_only_capability_refused(self) -> None:
        with self.assertRaises(LabelEvidenceError) as ctx:
            attach_label_evidence(
                _sample_source(),
                trades=[_terminal_trade(price=110.0)],
                request_time_ns=REQUEST_OK_NS,
                actual_retrieval_time_ns=REQUEST_OK_NS,
                provider_id="moomoo.opend",
                capability_id="BAR_OHLCV_1M",
                retrieval_params={},
                raw_trade_ref="fixture",
                raw_trade_payload_sha256="abc",
                source_code_sha="deadbeef",
                labeler_code_sha="cafebabe",
            )
        self.assertEqual(ctx.exception.reason_code, BAR_OHLCV_REFUSED_FOR_PATH_A_LABEL)

    def test_mismatched_source_hash_refused(self) -> None:
        source = _sample_source()
        source["source_observation_hash"] = "WRONG"
        with self.assertRaises(LabelEvidenceError) as ctx:
            attach_label_evidence(
                source,
                trades=[_terminal_trade(price=110.0)],
                request_time_ns=REQUEST_OK_NS,
                actual_retrieval_time_ns=REQUEST_OK_NS,
                provider_id="ibkr.observational",
                capability_id="IBKR_HISTORICAL_TRADES",
                retrieval_params={},
                raw_trade_ref="fixture",
                raw_trade_payload_sha256="abc",
                source_code_sha="deadbeef",
                labeler_code_sha="cafebabe",
            )
        self.assertEqual(ctx.exception.reason_code, INSTRUMENT_OR_HASH_MISMATCH)

    def test_malformed_provider_record_refused(self) -> None:
        with self.assertRaises(LabelEvidenceError) as ctx:
            attach_label_evidence(
                _sample_source(),
                trades=[{"instrument_id": INSTRUMENT, "observation_kind": "TRADE", "price": 1.0}],
                request_time_ns=REQUEST_OK_NS,
                actual_retrieval_time_ns=REQUEST_OK_NS,
                provider_id="ibkr.observational",
                capability_id="IBKR_HISTORICAL_TRADES",
                retrieval_params={},
                raw_trade_ref="fixture",
                raw_trade_payload_sha256="abc",
                source_code_sha="deadbeef",
                labeler_code_sha="cafebabe",
            )
        self.assertEqual(ctx.exception.reason_code, MALFORMED_PROVIDER_TRADE_RECORD)

    def test_multiple_candidates_use_deterministic_first_in_window(self) -> None:
        later = _terminal_trade(price=120.0, event_time_ns=TARGET_NS + 10_000_000_000, trade_id="late")
        earlier = _terminal_trade(price=115.0, event_time_ns=TARGET_NS, trade_id="early")
        selected, _ = select_terminal_trade(
            [later, earlier],
            instrument_id=INSTRUMENT,
            target_window_start_ns=TARGET_NS,
            target_window_end_ns=WINDOW_END_NS,
            availability_cutoff_ns=WINDOW_END_NS,
        )
        assert selected is not None
        self.assertEqual(selected["trade_id"], "early")

    def test_feature_constructors_cannot_see_post_horizon_columns_without_join(self) -> None:
        with self.assertRaises(LabelEvidenceError) as ctx:
            assert_feature_constructor_corpus_safe(
                ["momentum_5m", "direction_label"],
                label_columns=["direction_label"],
            )
        self.assertEqual(ctx.exception.reason_code, IMPLICIT_LABEL_COLUMN_MERGE_REFUSED)

    def test_historical_observation_cannot_relabel_as_prospective(self) -> None:
        source = _sample_source(
            p0={
                "event_id": "p0-old",
                "price": 100.0,
                "event_time_ns": SIGNAL_NS - 1,
                "available_time_ns": SIGNAL_NS - 1,
                "observation_kind": "TRADE",
            }
        )
        with self.assertRaises(LabelEvidenceError) as ctx:
            validate = attach_label_evidence
            validate(
                source,
                trades=[_terminal_trade(price=110.0)],
                request_time_ns=REQUEST_OK_NS,
                actual_retrieval_time_ns=REQUEST_OK_NS,
                provider_id="ibkr.observational",
                capability_id="IBKR_HISTORICAL_TRADES",
                retrieval_params={},
                raw_trade_ref="fixture",
                raw_trade_payload_sha256="abc",
                source_code_sha="deadbeef",
                labeler_code_sha="cafebabe",
            )
        self.assertEqual(ctx.exception.reason_code, HISTORICAL_EVENT_NOT_PROSPECTIVE)

    def test_untouched_forward_evaluation_not_consumable_for_training(self) -> None:
        with self.assertRaises(ProtectedCorpusConsumptionError) as ctx:
            assert_corpus_consumable_for_selection_or_training(
                corpus_evidence_authority=CORPUS_EVIDENCE_AUTHORITY_UNTOUCHED_FORWARD_EVALUATION,
            )
        self.assertIn(CONSUMPTION_REFUSED_PROTECTED_CORPUS, str(ctx.exception))

    def test_ibkr_fixture_normalization(self) -> None:
        fixture_path = Path(__file__).parent / "fixtures" / "ibkr_historical_trades_sample.json"
        rows = json.loads(fixture_path.read_text(encoding="utf-8"))
        trades = normalize_ibkr_historical_trades_payload(
            {"data": rows},
            instrument_id=INSTRUMENT,
        )
        self.assertEqual(len(trades), 2)
        self.assertEqual(trades[0].observation_kind, "TRADE")

    def test_ibkr_bar_payload_refused(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            normalize_ibkr_historical_trades_payload(
                {"data": [{"t": 1, "o": 1, "c": 2}]},
                instrument_id=INSTRUMENT,
            )
        self.assertEqual(str(ctx.exception), BAR_OHLCV_PAYLOAD_REFUSED)

    def test_historical_trade_port_refuses_early_request(self) -> None:
        result = retrieve_historical_trades_bounded(
            _FakeTradePort([_terminal_trade(price=101.0)]),
            instrument_id=INSTRUMENT,
            start_time_ns=TARGET_NS,
            end_time_ns=WINDOW_END_NS,
            request_time_ns=WINDOW_END_NS - 1,
            terminal_window_end_ns=WINDOW_END_NS,
        )
        self.assertFalse(result.accepted)
        self.assertEqual(result.reason, RETRIEVAL_BEFORE_TERMINAL_WINDOW_END)


if __name__ == "__main__":
    unittest.main()
