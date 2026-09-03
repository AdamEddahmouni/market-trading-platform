"""Platformization P6 — shadow/forward-validation infrastructure tests.

These tests prove INFRASTRUCTURE ONLY (immutability, causality enforcement,
abstention accounting, metric math against hand-computed fixtures,
walk-forward boundaries, restart-safety, determinism). They are NOT
forward-validation evidence — see the P6 design spec §0.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.canonical import canonical_bytes  # noqa: E402
from market_platform_foundation.shadow import metrics as shadow_metrics  # noqa: E402
from market_platform_foundation.shadow import runs as shadow_runs  # noqa: E402
from market_platform_foundation.shadow.labeling import (  # noqa: E402
    LabelingViolation,
    attach_label,
)
from market_platform_foundation.shadow.records import (  # noqa: E402
    ShadowIntegrityError,
    ShadowPredictionRecord,
    ShadowRunManifest,
    build_prediction,
    build_run_manifest,
    compute_prediction_hash,
    verify_prediction,
)
from market_platform_foundation.shadow.store import ShadowStore  # noqa: E402

DECISION_NS = 1_000_000_000_000_000_000
HORIZON_NS = 500_000_000  # 0.5s in ns
LABEL_TIME_NS = DECISION_NS + HORIZON_NS + 250_000_000
AVAILABLE_NS = LABEL_TIME_NS + 100_000_000


def _manifest_kwargs(**overrides) -> dict:
    kwargs = dict(
        strategy_version="fixture-strategy/1",
        prediction_version="shadow/fixture/1",
        universe=("BIYA",),
        data_window_refs=({"kind": "replay", "ref": "fixtures/biya-slice"},),
        train_window_end_ns=DECISION_NS,
        eval_window_start_ns=DECISION_NS,
        eval_window_end_ns=DECISION_NS + HORIZON_NS * 100,
        created_at_ns=DECISION_NS - 1_000_000_000,
    )
    kwargs.update(overrides)
    return kwargs


def _manifest(**overrides) -> ShadowRunManifest:
    return build_run_manifest(**_manifest_kwargs(**overrides))


def _prediction(run_id: str, *, probability: float, instrument: str = "BIYA", seq: int = 0):
    return build_prediction(
        run_id=run_id,
        instrument_id=instrument,
        decision_time_ns=DECISION_NS + seq * HORIZON_NS,
        horizon_ns=HORIZON_NS,
        predicted_probability=probability,
        payload={"seq": seq},
        pit_snapshot_ref=f"snapshot-{seq}",
        created_at_ns=DECISION_NS - 500,
    )


def _open_store(name: str) -> tuple[ShadowStore, Path]:
    tmp = tempfile.mkdtemp(prefix="shadow-p6-")
    path = Path(tmp) / name
    return ShadowStore(path), path


def _fake_label(prediction_id: str, observed_positive: bool):
    """Minimal label stand-in for pure-metric unit tests (no store needed)."""

    class _L:
        pass

    label = _L()
    label.prediction_id = prediction_id
    label.observed_positive = observed_positive
    label.observed_return_bps = None
    return label


class ImmutabilityTests(unittest.TestCase):
    """Content-addressed identity detects any retrospective mutation."""

    def test_record_hash_matches_content(self) -> None:
        record = _prediction("run-x", probability=0.7)
        verify_prediction(record)
        like = {
            "run_id": record.run_id,
            "instrument_id": record.instrument_id,
            "decision_time_ns": record.decision_time_ns,
            "horizon_ns": record.horizon_ns,
            "predicted_probability": 0.7,
            "predicted_positive": True,
            "abstained": False,
            "abstain_reason": None,
            "regime_tag": None,
            "payload": {"seq": 0},
            "pit_snapshot_ref": "snapshot-0",
            "created_at_ns": DECISION_NS - 500,
        }
        self.assertEqual(record.record_hash, compute_prediction_hash(like))

    def test_mutation_detected_via_hash(self) -> None:
        record = _prediction("run-x", probability=0.7)
        tampered = ShadowPredictionRecord(
            **{**record.__dict__, "predicted_probability": 0.9}
        )
        with self.assertRaises(ShadowIntegrityError):
            verify_prediction(tampered)

    def test_store_rejects_tampered_row_on_read(self) -> None:
        store, _ = _open_store("state.db")
        try:
            manifest, inserted = shadow_runs.open_shadow_run(
                store, **_manifest_kwargs()
            )
            self.assertTrue(inserted)
            record, _ = shadow_runs.record_prediction(
                store,
                manifest,
                instrument_id="BIYA",
                decision_time_ns=DECISION_NS,
                horizon_ns=HORIZON_NS,
                predicted_probability=0.6,
                pit_snapshot_ref="snap",
                created_at_ns=DECISION_NS - 500,
            )
            # Simulate retrospective mutation directly in SQLite (bypassing API).
            import json

            row = store._conn.execute(
                "SELECT record_json FROM shadow_predictions WHERE prediction_id=?",
                (record.prediction_id,),
            ).fetchone()
            mutated = json.loads(row["record_json"])
            mutated["predicted_probability"] = 0.99
            store._conn.execute(
                "UPDATE shadow_predictions SET record_json=? WHERE prediction_id=?",
                (json.dumps(mutated, sort_keys=True), record.prediction_id),
            )
            with self.assertRaises(ShadowIntegrityError):
                store.get_prediction(record.prediction_id)
        finally:
            store.close()


class InsertOnceTests(unittest.TestCase):
    def test_duplicate_prediction_is_noop_returning_existing(self) -> None:
        store, _ = _open_store("state.db")
        try:
            manifest, _ = shadow_runs.open_shadow_run(store, **_manifest_kwargs())
            args = dict(
                instrument_id="BIYA",
                decision_time_ns=DECISION_NS,
                horizon_ns=HORIZON_NS,
                predicted_probability=0.6,
                pit_snapshot_ref="snap",
                created_at_ns=DECISION_NS - 500,
            )
            first, inserted_first = shadow_runs.record_prediction(store, manifest, **args)
            second, inserted_second = shadow_runs.record_prediction(store, manifest, **args)
            self.assertTrue(inserted_first)
            self.assertFalse(inserted_second)
            self.assertEqual(first.prediction_id, second.prediction_id)
            self.assertEqual(first.record_hash, second.record_hash)
            self.assertEqual(store.counts()["predictions"], 1)
        finally:
            store.close()

    def test_manifest_insert_once(self) -> None:
        store, _ = _open_store("state.db")
        try:
            args = _manifest_kwargs()
            m1, i1 = shadow_runs.open_shadow_run(store, **args)
            m2, i2 = shadow_runs.open_shadow_run(store, **args)
            self.assertTrue(i1)
            self.assertFalse(i2)
            self.assertEqual(m1.run_id, m2.run_id)
            self.assertEqual(store.counts()["runs"], 1)
        finally:
            store.close()


class CausalityEnforcementTests(unittest.TestCase):
    def setUp(self) -> None:
        self.record = _prediction("run-c", probability=0.7)
        self.store, _ = _open_store("causality.db")
        self.addCleanup(self.store.close)

    def test_label_time_not_after_decision_refused(self) -> None:
        with self.assertRaises(LabelingViolation):
            attach_label(
                self.store,
                self.record,
                observed_positive=True,
                label_time_ns=self.record.decision_time_ns,
                available_time_ns=self.record.decision_time_ns + self.record.horizon_ns + 1,
            )

    def test_available_within_horizon_refused(self) -> None:
        for available in (
            self.record.decision_time_ns,  # before horizon end
            self.record.decision_time_ns + self.record.horizon_ns,  # == horizon end
        ):
            with self.assertRaises(LabelingViolation):
                attach_label(
                    self.store,
                    self.record,
                    observed_positive=True,
                    label_time_ns=self.record.decision_time_ns + 1,
                    available_time_ns=available,
                )

    def test_available_before_resolved_refused(self) -> None:
        with self.assertRaises(LabelingViolation):
            attach_label(
                self.store,
                self.record,
                observed_positive=True,
                label_time_ns=LABEL_TIME_NS + 1_000_000,
                available_time_ns=LABEL_TIME_NS,
            )

    def test_valid_label_accepted_and_joined(self) -> None:
        manifest, _ = shadow_runs.open_shadow_run(
            self.store, **_manifest_kwargs()
        )
        record, _ = shadow_runs.record_prediction(
            self.store,
            manifest,
            instrument_id="BIYA",
            decision_time_ns=DECISION_NS,
            horizon_ns=HORIZON_NS,
            predicted_probability=0.7,
            pit_snapshot_ref="snap",
            created_at_ns=DECISION_NS - 500,
        )
        label, inserted = attach_label(
            self.store,
            record,
            observed_positive=True,
            label_time_ns=LABEL_TIME_NS,
            available_time_ns=AVAILABLE_NS,
        )
        self.assertTrue(inserted)
        fetched = self.store.get_label_for_run_prediction(manifest.run_id, record.prediction_id)
        assert fetched is not None
        self.assertEqual(fetched.label_id, label.label_id)
        self.assertGreater(fetched.available_time_ns, DECISION_NS + HORIZON_NS)


class AbstentionTests(unittest.TestCase):
    def test_abstained_record_requires_reason_no_probability(self) -> None:
        record = build_prediction(
            run_id="run-a",
            instrument_id="BIYA",
            decision_time_ns=DECISION_NS,
            horizon_ns=HORIZON_NS,
            abstained=True,
            abstain_reason="INSUFFICIENT_DATA",
            created_at_ns=DECISION_NS - 1,
        )
        self.assertIsNone(record.predicted_probability)
        self.assertIsNone(record.predicted_positive)
        with self.assertRaises(ValueError):
            build_prediction(
                run_id="run-a",
                instrument_id="BIYA",
                decision_time_ns=DECISION_NS,
                horizon_ns=HORIZON_NS,
                abstained=True,
                created_at_ns=DECISION_NS - 1,
            )

    def test_abstentions_counted_and_excluded_from_scored_metrics(self) -> None:
        scored_pair = {
            "prediction": _prediction("run-b", probability=0.8),
            "label": _fake_label(_prediction("run-b", probability=0.8).prediction_id, False),
        }
        pending_pair = {"prediction": _prediction("run-b", probability=0.2, seq=1), "label": None}
        abstained_record = build_prediction(
            run_id="run-b",
            instrument_id="BIYA",
            decision_time_ns=DECISION_NS + 9 * HORIZON_NS,
            horizon_ns=HORIZON_NS,
            abstained=True,
            abstain_reason="NO_SIGNAL",
            created_at_ns=DECISION_NS - 1,
        )
        abstained_pair = {"prediction": abstained_record, "label": None}
        result = shadow_metrics.observed_metrics([scored_pair, pending_pair, abstained_pair])
        self.assertEqual(result["total_predictions"], 3)
        self.assertEqual(result["scored"], 1)
        self.assertEqual(result["pending_labels"], 1)
        self.assertEqual(result["abstained"], 1)
        self.assertAlmostEqual(result["abstention_rate"], 1 / 3)
        self.assertIsNotNone(result["brier_score"])


class CalibrationMathTests(unittest.TestCase):
    """Hand-computed fixture: 10 scored records, one per positional decile."""

    PROBABILITIES = [0.05, 0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 0.95]
    OUTCOMES = [False, False, False, False, True, True, True, True, True, True]

    def _pairs(self) -> list[dict]:
        pairs = []
        for seq, (prob, outcome) in enumerate(zip(self.PROBABILITIES, self.OUTCOMES)):
            record = _prediction("run-cal", probability=prob, seq=seq)
            pairs.append({"prediction": record, "label": _fake_label(record.prediction_id, outcome)})
        return pairs

    def test_hit_rate_brier_calibration_hand_computed(self) -> None:
        result = shadow_metrics.observed_metrics(self._pairs(), bucket_count=10)
        # Predicted positive iff p >= 0.5: last five hit; p=0.45 vs observed
        # positive is the single directional miss.
        self.assertEqual(result["hits"], 9)
        self.assertAlmostEqual(result["hit_rate"], 0.9)
        # Brier: y=0 rows contribute p^2, y=1 rows contribute (1-p)^2.
        neg = sum(p * p for p in self.PROBABILITIES[:4])
        pos = sum((1 - p) ** 2 for p in self.PROBABILITIES[4:])
        self.assertAlmostEqual(result["brier_score"], (neg + pos) / 10)
        self.assertAlmostEqual(result["brier_score"], 0.0925)
        buckets = result["calibration_buckets"]
        self.assertEqual(len(buckets), 10)
        for index, bucket in enumerate(buckets):
            self.assertEqual(bucket["n"], 1)
            self.assertAlmostEqual(bucket["mean_predicted_probability"], self.PROBABILITIES[index])
            expected_freq = 1.0 if self.OUTCOMES[index] else 0.0
            self.assertAlmostEqual(bucket["observed_frequency"], expected_freq)
            self.assertAlmostEqual(bucket["gap"], self.PROBABILITIES[index] - expected_freq)


class WalkForwardBoundaryTests(unittest.TestCase):
    def _pairs_with_times(self, times: list[int]) -> list[dict]:
        pairs = []
        for seq, decision_ns in enumerate(times):
            record = build_prediction(
                run_id="run-wf",
                instrument_id="BIYA",
                decision_time_ns=decision_ns,
                horizon_ns=HORIZON_NS,
                predicted_probability=0.5,
                created_at_ns=decision_ns - 1,
            )
            pairs.append({"prediction": record, "label": None})
        return pairs

    def test_eval_start_equal_to_train_end_allowed_no_peeking(self) -> None:
        manifest = _manifest(
            train_window_end_ns=DECISION_NS + 10,
            eval_window_start_ns=DECISION_NS + 10,
        )
        pairs = self._pairs_with_times(
            [DECISION_NS, DECISION_NS + 5, DECISION_NS + 10, DECISION_NS + 20]
        )
        report = shadow_metrics.walk_forward_evaluation(pairs, manifest)
        # Boundary-exclusive train side: decision at train end is eval-side.
        self.assertEqual(report["train_coverage"]["n"], 2)
        self.assertEqual(report["eval"]["total_predictions"], 2)

    def test_builder_rejects_leaking_windows_up_front(self) -> None:
        with self.assertRaises(ValueError):
            _manifest(
                train_window_end_ns=DECISION_NS + 10,
                eval_window_start_ns=DECISION_NS + 5,
            )

    def test_split_guard_raises_on_overlapping_windows(self) -> None:
        valid = _manifest(
            train_window_end_ns=DECISION_NS + 10,
            eval_window_start_ns=DECISION_NS + 10,
        )
        # Construct a leaking window set directly (defense-in-depth guard).
        leaking = ShadowRunManifest(
            **{**valid.__dict__, "eval_window_start_ns": DECISION_NS + 4}
        )
        with self.assertRaises(shadow_metrics.WalkForwardLeakageError):
            shadow_metrics.walk_forward_evaluation([], leaking)

    def test_records_outside_both_windows_accounted(self) -> None:
        manifest = _manifest(
            train_window_end_ns=DECISION_NS + 10,
            eval_window_start_ns=DECISION_NS + 20,
            eval_window_end_ns=DECISION_NS + 30,
        )
        pairs = self._pairs_with_times([DECISION_NS, DECISION_NS + 25, DECISION_NS + 99])
        report = shadow_metrics.walk_forward_evaluation(pairs, manifest)
        self.assertEqual(report["train_coverage"]["n"], 1)
        self.assertEqual(report["eval"]["total_predictions"], 1)
        self.assertEqual(report["outside_windows"], 1)


class RegimeSegmentationTests(unittest.TestCase):
    def test_regime_tags_pass_through_segmented(self) -> None:
        risk_record = build_prediction(
            run_id="run-r",
            instrument_id="BIYA",
            decision_time_ns=DECISION_NS,
            horizon_ns=HORIZON_NS,
            predicted_probability=0.9,
            regime_tag="RISK_ON",
            created_at_ns=DECISION_NS - 1,
        )
        calm_record = build_prediction(
            run_id="run-r",
            instrument_id="BIYA",
            decision_time_ns=DECISION_NS + HORIZON_NS,
            horizon_ns=HORIZON_NS,
            predicted_probability=0.1,
            regime_tag="CALM",
            created_at_ns=DECISION_NS,
        )
        segments = shadow_metrics.segment_by_regime(
            [
                {"prediction": risk_record, "label": _fake_label(risk_record.prediction_id, True)},
                {"prediction": calm_record, "label": _fake_label(calm_record.prediction_id, True)},
            ]
        )
        self.assertEqual(sorted(segments), ["CALM", "RISK_ON"])
        self.assertEqual(segments["RISK_ON"]["hits"], 1)
        self.assertEqual(segments["CALM"]["hits"], 0)

    def test_missing_regime_tag_grouped_as_untagged(self) -> None:
        pair = {
            "prediction": _prediction("run-r2", probability=0.4),
            "label": None,
        }
        segments = shadow_metrics.segment_by_regime([pair])
        self.assertEqual(list(segments), ["UNTAGGED"])


class OverlaySeparationTests(unittest.TestCase):
    def test_overlay_lives_in_disjoint_namespace(self) -> None:
        record = _prediction("run-o", probability=0.9)
        store, _ = _open_store("overlay.db")
        try:
            label = attach_label(
                store,
                record,
                observed_positive=True,
                label_time_ns=record.decision_time_ns + HORIZON_NS + 1,
                available_time_ns=record.decision_time_ns + HORIZON_NS + 2,
                observed_return_bps=50.0,
            )[0]
        finally:
            store.close()
        pairs = [{"prediction": record, "label": label}]
        overlay = shadow_metrics.assumption_overlay(
            pairs, slippage_bps=10.0, cost_model_version="fixture_cost_v1"
        )
        observed = shadow_metrics.observed_metrics(pairs)
        # Observed namespace carries no assumption keys; overlay declares itself.
        self.assertNotIn("overlay", observed)
        self.assertNotIn(b"slippage_bps", canonical_bytes(observed))
        self.assertEqual(overlay["cost_model_version"], "fixture_cost_v1")
        self.assertEqual(overlay["positive_after_assumed_costs"], 1)
        self.assertEqual(overlay["disclaimer"], "ASSUMPTION_ONLY_NOT_AN_OBSERVED_OUTCOME")
        # Long direction: 50 gross - 10 assumed slippage = +40 net.
        self.assertEqual(overlay["rows"][0]["net_of_assumed_slippage_bps"], 40.0)

    def test_short_direction_net_flips_sign(self) -> None:
        short_record = build_prediction(
            run_id="run-o2",
            instrument_id="BIYA",
            decision_time_ns=DECISION_NS,
            horizon_ns=HORIZON_NS,
            predicted_probability=0.1,
            created_at_ns=DECISION_NS - 1,
        )
        label = _fake_label(short_record.prediction_id, False)  # short thesis realized
        label.observed_return_bps = -30.0  # mark fell 30bps
        overlay = shadow_metrics.assumption_overlay(
            [{"prediction": short_record, "label": label}],
            slippage_bps=10.0,
            cost_model_version="fixture_cost_v1",
        )
        # Short direction: -(-30) - 10 = +20 net under the assumption.
        self.assertEqual(overlay["rows"][0]["net_of_assumed_slippage_bps"], 20.0)


class RestartSafetyTests(unittest.TestCase):
    def test_reopen_store_continue_appending(self) -> None:
        tmp = tempfile.mkdtemp(prefix="shadow-p6-restart-")
        db_path = Path(tmp) / "restart.db"
        store = ShadowStore(db_path)
        manifest, _ = shadow_runs.open_shadow_run(store, **_manifest_kwargs())
        record, _ = shadow_runs.record_prediction(
            store,
            manifest,
            instrument_id="BIYA",
            decision_time_ns=DECISION_NS,
            horizon_ns=HORIZON_NS,
            predicted_probability=0.65,
            regime_tag="TREND",
            pit_snapshot_ref="snap-r",
            created_at_ns=DECISION_NS - 500,
        )
        store.close()

        reopened = ShadowStore(db_path)
        try:
            self.assertEqual(reopened.counts()["predictions"], 1)
            stored = reopened.get_prediction(record.prediction_id)
            assert stored is not None
            self.assertEqual(stored.predicted_probability, 0.65)
            # Continue the run after restart: labeling works across reopen.
            label, inserted = attach_label(
                reopened,
                stored,
                observed_positive=True,
                label_time_ns=LABEL_TIME_NS,
                available_time_ns=AVAILABLE_NS,
            )
            self.assertTrue(inserted)
            self.assertEqual(reopened.counts()["labels"], 1)
            # Manifest survives restart intact (hash verified on read).
            reread = reopened.get_manifest(manifest.run_id)
            assert reread is not None
            self.assertEqual(reread.run_id, manifest.run_id)
        finally:
            reopened.close()


class DeterminismTests(unittest.TestCase):
    def _run_fixture_run(self, db_path: Path) -> dict:
        store = ShadowStore(db_path)
        try:
            manifest, _ = shadow_runs.open_shadow_run(store, **_manifest_kwargs())
            example = {
                "example_id": "ss-ex-000001",
                "instrument_id": "BIYA",
                "features": [
                    {
                        "evidence_family": "SQUEEZE_STATE",
                        "available_time_ns": DECISION_NS - 1,
                    }
                ],
            }
            probabilities_outcomes = [(0.3, False), (0.8, True), (0.5, True)]
            for seq, (prob, outcome) in enumerate(probabilities_outcomes):
                record, _ = shadow_runs.record_prediction(
                    store,
                    manifest,
                    instrument_id="NVDA" if seq else "BIYA",
                    decision_time_ns=DECISION_NS + seq * 2 * HORIZON_NS,
                    horizon_ns=HORIZON_NS,
                    predicted_probability=prob,
                    regime_tag="REGIME_A" if seq % 2 else "REGIME_B",
                    payload=(
                        shadow_runs.prediction_payload_from_decision_example(example)
                        if seq == 0
                        else {"seq": seq}
                    ),
                    pit_snapshot_ref=f"snap-{seq}",
                    created_at_ns=DECISION_NS - 500 + seq,
                )
                shadow_runs.record_label(
                    store,
                    record,
                    observed_positive=outcome,
                    label_time_ns=record.decision_time_ns + HORIZON_NS + 1,
                    available_time_ns=record.decision_time_ns + 2 * HORIZON_NS,
                    observed_return_bps=10.0 * (seq + 1),
                )
            # One abstaining prediction left unlabeled (pending).
            shadow_runs.record_prediction(
                store,
                manifest,
                instrument_id="BOXL",
                decision_time_ns=DECISION_NS + 20 * HORIZON_NS,
                horizon_ns=HORIZON_NS,
                abstained=True,
                abstain_reason="QUALITY_GATE_FAILED",
                pit_snapshot_ref="snap-abstain",
                created_at_ns=DECISION_NS - 400,
            )
            return shadow_runs.finalize_report(
                store,
                manifest,
                overlays=[{"slippage_bps": 5.0, "cost_model_version": "fixture_cost_v1"}],
            )
        finally:
            store.close()

    def test_two_identical_runs_produce_identical_bytes(self) -> None:
        reports = []
        for index in range(2):
            _, db_path = _open_store(f"det{index}.db")
            reports.append(canonical_bytes(self._run_fixture_run(db_path)))
        self.assertEqual(reports[0], reports[1])

    def test_different_inputs_change_report_id(self) -> None:
        ids = set()
        for probability in (0.3, 0.4):
            store, _ = _open_store(f"d{probability}.db")
            try:
                manifest, _ = shadow_runs.open_shadow_run(
                    store, **_manifest_kwargs()
                )
                record, _ = shadow_runs.record_prediction(
                    store,
                    manifest,
                    instrument_id="BIYA",
                    decision_time_ns=DECISION_NS,
                    horizon_ns=HORIZON_NS,
                    predicted_probability=probability,
                    pit_snapshot_ref="s",
                    created_at_ns=DECISION_NS - 500,
                )
                shadow_runs.record_label(
                    store,
                    record,
                    observed_positive=True,
                    label_time_ns=LABEL_TIME_NS,
                    available_time_ns=AVAILABLE_NS,
                )
                ids.add(shadow_runs.finalize_report(store, manifest)["report_id"])
            finally:
                store.close()
        self.assertEqual(len(ids), 2)


if __name__ == "__main__":
    unittest.main()
