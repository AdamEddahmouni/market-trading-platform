"""Path A label evidence linkage (IMP-EVIDENCE-HARDENING-02 Lane A)."""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.outcomes.label_evidence import (  # noqa: E402
    BAR_OHLCV_REFUSED_FOR_PATH_A_LABEL,
    NO_ELIGIBLE_TRADE,
    RETRIEVAL_BEFORE_TERMINAL_WINDOW_END,
    attach_label_evidence,
    derive_source_observation_hash,
)
from market_platform_foundation.intelligence.outcomes.path_a_label_linker import (  # noqa: E402
    DUPLICATE_LABEL_EVIDENCE_ID,
    LABEL_INVALID_PROVENANCE,
    LABEL_OBSERVATION_HASH_MISMATCH,
    LABEL_OBSERVATION_ID_MISMATCH,
    PathALabelLinkageError,
    link_path_a_label_evidence,
    prospective_source_observation_from_item9_receipt,
)
from market_platform_foundation.paper.calibration.item9_calibration_protocol import (  # noqa: E402
    build_dataset_row,
)

SIGNAL_NS = 1_789_661_252_872_965_400
BAR_END = 1_789_661_280_000_000_000
HORIZON_NS = 300_000_000_000
TARGET_NS = SIGNAL_NS + HORIZON_NS
WINDOW_END_NS = TARGET_NS + 60_000_000_000
REQUEST_OK_NS = WINDOW_END_NS + 1
INSTRUMENT = "AAPL"
OBS_ID = "item9-fixture-obs-1"


def _p0_trade() -> dict[str, object]:
    return {
        "event_id": "p0-trade-1",
        "price": 100.0,
        "event_time_ns": SIGNAL_NS,
        "available_time_ns": SIGNAL_NS,
        "observation_kind": "TRADE",
    }


def _item9_receipt() -> dict[str, object]:
    return {
        "experiment_id": OBS_ID,
        "instrument_id": INSTRUMENT,
        "signal_time_ns": SIGNAL_NS,
        "bar_available_time_ns": BAR_END,
        "first_post_signal_bar": {"available_time_ns": BAR_END},
        "runtime_git_sha": "test-sha",
    }


def _source_observation() -> dict[str, object]:
    return prospective_source_observation_from_item9_receipt(_item9_receipt(), p0=_p0_trade())


def _terminal_trade(*, price: float = 110.0) -> dict[str, object]:
    return {
        "instrument_id": INSTRUMENT,
        "observation_kind": "TRADE",
        "price": price,
        "event_time_ns": TARGET_NS,
        "available_time_ns": TARGET_NS,
        "trade_id": "t1",
    }


def _attached_label(**trade_kw: object) -> dict[str, object]:
    source = _source_observation()
    body = {
        "source_observation_id": source["source_observation_id"],
        "source_evidence_class": source["source_evidence_class"],
        "instrument_id": source["instrument_id"],
        "signal_time_ns": source["signal_time_ns"],
        "feature_cutoff_ns": source["feature_cutoff_ns"],
        "horizon_ns": source["horizon_ns"],
        "source_code_sha": source["source_code_sha"],
        "p0": source["p0"],
        "source_observation_hash": source["source_observation_hash"],
    }
    result = attach_label_evidence(
        body,
        trades=[_terminal_trade(**trade_kw)],
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
    return result.label_evidence


class PathALabelLinkerTests(unittest.TestCase):
    def test_no_label_evidence_returns_empty_ids(self) -> None:
        source = _source_observation()
        before = derive_source_observation_hash(source)
        result = link_path_a_label_evidence(source, ())
        self.assertEqual(result.path_a_label_evidence_ids, ())
        self.assertIsNone(result.path_a_label_value)
        self.assertEqual(result.source_hash_before, before)
        self.assertEqual(result.source_hash_after, before)

    def test_one_valid_linked_label_artifact(self) -> None:
        source = _source_observation()
        label = _attached_label()
        result = link_path_a_label_evidence(source, (label,))
        self.assertEqual(len(result.path_a_label_evidence_ids), 1)
        self.assertEqual(result.path_a_label_evidence_ids[0], label["label_evidence_id"])
        self.assertEqual(result.path_a_label_value, "LONG")
        self.assertEqual(result.source_hash_before, result.source_hash_after)

    def test_duplicate_label_id_refused(self) -> None:
        label = _attached_label()
        with self.assertRaises(PathALabelLinkageError) as ctx:
            link_path_a_label_evidence(_source_observation(), (label, label))
        self.assertEqual(ctx.exception.reason_code, DUPLICATE_LABEL_EVIDENCE_ID)

    def test_mismatched_observation_id_refused(self) -> None:
        label = _attached_label()
        bad = copy.deepcopy(label)
        bad["source_observation_id"] = "other-id"
        with self.assertRaises(PathALabelLinkageError) as ctx:
            link_path_a_label_evidence(_source_observation(), (bad,))
        self.assertEqual(ctx.exception.reason_code, LABEL_OBSERVATION_ID_MISMATCH)

    def test_mismatched_observation_hash_refused(self) -> None:
        label = _attached_label()
        bad = copy.deepcopy(label)
        bad["source_observation_hash"] = "sha-mismatch"
        with self.assertRaises(PathALabelLinkageError) as ctx:
            link_path_a_label_evidence(_source_observation(), (bad,))
        self.assertEqual(ctx.exception.reason_code, LABEL_OBSERVATION_HASH_MISMATCH)

    def test_bar_evidence_attempting_to_bind_refused(self) -> None:
        label = _attached_label()
        bad = copy.deepcopy(label)
        bad["capability_id"] = "BAR_OHLCV_1M"
        with self.assertRaises(PathALabelLinkageError) as ctx:
            link_path_a_label_evidence(_source_observation(), (bad,))
        self.assertEqual(ctx.exception.reason_code, BAR_OHLCV_REFUSED_FOR_PATH_A_LABEL)

    def test_label_retrieved_before_maturity_refused(self) -> None:
        label = _attached_label()
        bad = copy.deepcopy(label)
        bad["request_time_ns"] = WINDOW_END_NS - 1
        with self.assertRaises(PathALabelLinkageError) as ctx:
            link_path_a_label_evidence(_source_observation(), (bad,))
        self.assertEqual(ctx.exception.reason_code, RETRIEVAL_BEFORE_TERMINAL_WINDOW_END)

    def test_invalid_missing_provenance_refused(self) -> None:
        label = _attached_label()
        bad = copy.deepcopy(label)
        del bad["corpus_evidence_authority"]
        with self.assertRaises(PathALabelLinkageError) as ctx:
            link_path_a_label_evidence(_source_observation(), (bad,))
        self.assertEqual(ctx.exception.reason_code, LABEL_INVALID_PROVENANCE)

    def test_unlabelable_outcome_still_links_evidence_id(self) -> None:
        source = _source_observation()
        body = {
            "source_observation_id": source["source_observation_id"],
            "source_evidence_class": source["source_evidence_class"],
            "instrument_id": source["instrument_id"],
            "signal_time_ns": source["signal_time_ns"],
            "feature_cutoff_ns": source["feature_cutoff_ns"],
            "horizon_ns": source["horizon_ns"],
            "source_code_sha": source["source_code_sha"],
            "p0": source["p0"],
            "source_observation_hash": source["source_observation_hash"],
        }
        result = attach_label_evidence(
            body,
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
        label = result.label_evidence
        self.assertEqual(label["refusal_reason"], NO_ELIGIBLE_TRADE)
        linked = link_path_a_label_evidence(source, (label,))
        self.assertEqual(len(linked.path_a_label_evidence_ids), 1)
        self.assertIsNone(linked.path_a_label_value)

    def test_source_observation_not_mutated_by_linkage(self) -> None:
        source = _source_observation()
        before = copy.deepcopy(source)
        link_path_a_label_evidence(source, (_attached_label(),))
        self.assertEqual(source, before)

    def test_build_dataset_row_populates_path_a_label_evidence_ids(self) -> None:
        label = _attached_label()
        row = build_dataset_row(
            _item9_receipt(),
            prospective_p0=_p0_trade(),
            label_evidences=(label,),
        )
        self.assertEqual(row["path_a_label_evidence_ids"], [label["label_evidence_id"]])
        self.assertEqual(row["path_a_label_value"], "LONG")
        self.assertIsNotNone(row["path_a_label_availability_ns"])

    def test_build_dataset_row_without_labels_keeps_empty_ids(self) -> None:
        row = build_dataset_row(_item9_receipt())
        self.assertEqual(row["path_a_label_evidence_ids"], [])


if __name__ == "__main__":
    unittest.main()
