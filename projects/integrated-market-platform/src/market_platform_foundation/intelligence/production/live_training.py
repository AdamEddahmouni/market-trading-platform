"""Path A PRODUCTION specialist + calibrator from the live feature corpus, judged on an untouched holdout.

Per instrument the settled corpus rows are split in decision-time order into train, calibration and holdout.
Each later split starts only after every label of the earlier one was available (a horizon embargo), so no
label used to fit or calibrate overlaps a decision used to judge. Train and calibration rows go through the
existing governed manifest and ``build_path_a_production_artifacts``; the holdout never enters that manifest
and is read once, afterwards, to score the built artifact. Eligibility for Paper forecasting is the
preregistered rule below, fixed before any holdout is scored. Nothing here calls a model service, writes the
canonical store or places an order.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

from ...canonical import canonical_bytes, sha256_bytes, write_canonical_json
from ..fusion.calibrators import apply_calibration
from .errors import ProductionTrainingError
from .identity import path_a_direction_target, path_a_horizon
from .live_feature_corpus import load_training_examples
from .model import ProductionTrainingExample, _extract_features, fit_production_specialist
from .model_store import load_production_specialist_model
from .readiness import TRAINING_MANIFEST_KIND

BUILD_SCHEMA_VERSION = "imp-live-forecast-build/1.0.0"
CORPUS_EVIDENCE_AUTHORITY = "PROSPECTIVE_FEATURE_EVIDENCE"
SPLIT_FRACTIONS = (0.6, 0.2, 0.2)

# Preregistered eligibility rule. Fixed in code before any holdout is scored; a build never edits it.
ELIGIBILITY_RULE_ID = "path-a-live-holdout-brier-skill/1"
MINIMUM_HOLDOUT_SAMPLES = 60
MINIMUM_BRIER_SKILL = 0.0  # strictly better than the training base rate on the untouched holdout
EDGE_REPORTING_THRESHOLD = 0.05


@dataclass(frozen=True, slots=True)
class Split:
    train: tuple[ProductionTrainingExample, ...]
    calibration: tuple[ProductionTrainingExample, ...]
    holdout: tuple[ProductionTrainingExample, ...]
    embargo_dropped: int


def _after_labels(rows: list[ProductionTrainingExample], start: int, label_cutoff_ns: int) -> int:
    """First index at or after ``start`` whose decision is strictly after ``label_cutoff_ns``."""
    index = start
    while index < len(rows) and rows[index].snapshot.decision_time_ns <= label_cutoff_ns:
        index += 1
    return index


def time_ordered_split(examples: Iterable[ProductionTrainingExample], fractions=SPLIT_FRACTIONS) -> Split:
    rows = sorted(examples, key=lambda e: (e.snapshot.decision_time_ns, e.snapshot.snapshot_id))
    n = len(rows)
    train_end = int(n * fractions[0])
    cal_end = int(n * (fractions[0] + fractions[1]))
    train = rows[:train_end]
    cal_start = _after_labels(rows, train_end, max((e.label_available_time_ns for e in train), default=-1))
    calibration = rows[cal_start:max(cal_start, cal_end)]
    hold_start = _after_labels(rows, max(cal_start, cal_end), max((e.label_available_time_ns for e in calibration), default=-1))
    holdout = rows[hold_start:]
    dropped = (cal_start - train_end) + (hold_start - max(cal_start, cal_end))
    return Split(tuple(train), tuple(calibration), tuple(holdout), dropped)


def _feature_row(example: ProductionTrainingExample) -> dict[str, Any]:
    by_type = {signal.signal_type: float(signal.value) for signal in example.signals}
    return dict(snapshot_id=example.snapshot.snapshot_id, decision_time_ns=example.snapshot.decision_time_ns,
                label=int(example.label), label_available_time_ns=int(example.label_available_time_ns),
                momentum=by_type["momentum_simple"], net_signed_share=by_type["net_signed_share"])


def _predict(model, example: ProductionTrainingExample) -> float:
    vector = _extract_features(example.snapshot, example.signals)
    if vector is None:
        raise ProductionTrainingError("FEATURE_EXTRACTION_FAILED")
    return float(model.predict_probability_up(vector))


def score_holdout(model, calibration, holdout: tuple[ProductionTrainingExample, ...], *, base_rate: float) -> dict[str, Any]:
    """Proper scores of the calibrated output against the training base rate, on rows never used to build."""
    probabilities, labels = [], []
    for example in holdout:
        probabilities.append(apply_calibration(calibration, _predict(model, example)))
        labels.append(int(example.label))
    n = len(labels)
    if not n:
        return dict(samples=0)
    eps = 1e-12
    brier = sum((p - y) ** 2 for p, y in zip(probabilities, labels)) / n
    climatology = sum((base_rate - y) ** 2 for y in labels) / n
    log_loss = -sum(y * math.log(max(p, eps)) + (1 - y) * math.log(max(1 - p, eps)) for p, y in zip(probabilities, labels)) / n
    long_edges = [(p, y) for p, y in zip(probabilities, labels) if p - 0.5 >= EDGE_REPORTING_THRESHOLD]
    short_edges = [(p, y) for p, y in zip(probabilities, labels) if 0.5 - p >= EDGE_REPORTING_THRESHOLD]
    return dict(samples=n, holdout_up_rate=sum(labels) / n, train_base_rate=base_rate, brier=brier,
                climatology_brier=climatology, brier_skill=(1 - brier / climatology) if climatology > 0 else None,
                log_loss=log_loss, accuracy_at_half=sum((p >= 0.5) == (y == 1) for p, y in zip(probabilities, labels)) / n,
                calibrated_min=min(probabilities), calibrated_max=max(probabilities),
                long_edge_count=len(long_edges), long_edge_hit_rate=(sum(y for _p, y in long_edges) / len(long_edges)) if long_edges else None,
                short_edge_count=len(short_edges), short_edge_hit_rate=(sum(1 - y for _p, y in short_edges) / len(short_edges)) if short_edges else None,
                edge_threshold=EDGE_REPORTING_THRESHOLD)


def eligibility(scores: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons = []
    if scores.get("samples", 0) < MINIMUM_HOLDOUT_SAMPLES:
        reasons.append("HOLDOUT_TOO_SMALL")
    skill = scores.get("brier_skill")
    if skill is None or not skill > MINIMUM_BRIER_SKILL:
        reasons.append("NO_HOLDOUT_SKILL_OVER_BASE_RATE")
    return not reasons, reasons


def build_instrument(instrument_id: str, examples: list[ProductionTrainingExample], *, output_dir: Path,
                     decision_time_ns: int, mode: str = "paper") -> dict[str, Any]:
    """One instrument's build record. Every refusal is recorded with its reason; nothing is forced."""
    from ...strategy.path_a_forecast_producer import load_paper_demo_calibration
    from .training_build import build_path_a_production_artifacts

    split = time_ordered_split(examples)
    record: dict[str, Any] = dict(instrument_id=instrument_id, samples=len(examples), train=len(split.train),
                                  calibration=len(split.calibration), holdout=len(split.holdout),
                                  embargo_dropped=split.embargo_dropped, eligible=False)
    if not split.train or not split.calibration:
        return dict(record, status="BLOCKED", reason_codes=["INSUFFICIENT_SETTLED_CORPUS"])
    target, horizon = path_a_direction_target(instrument_id), path_a_horizon()
    training_cutoff_ns = max(e.label_available_time_ns for e in split.train)
    calibration_cutoff_ns = max(e.label_available_time_ns for e in split.calibration)
    if calibration_cutoff_ns >= decision_time_ns:
        return dict(record, status="BLOCKED", reason_codes=["CALIBRATION_LABELS_NOT_YET_AVAILABLE"])
    try:
        model = fit_production_specialist(list(split.train), target=target, horizon=horizon, training_cutoff_ns=training_cutoff_ns)
    except ProductionTrainingError as error:
        return dict(record, status="BLOCKED", reason_codes=[str(error)])
    if model is None:
        return dict(record, status="BLOCKED", reason_codes=["INSUFFICIENT_LABELLED_PRODUCTION_CORPUS"])
    calibration_rows = [dict(_feature_row(e), raw_probability=_predict(model, e), forecast_decision_time_ns=e.snapshot.decision_time_ns,
                             raw_fusion_id=f"RFF-live-{instrument_id}-{e.snapshot.decision_time_ns}") for e in split.calibration]
    manifest = dict(artifact_kind=TRAINING_MANIFEST_KIND, target_instrument_id=instrument_id,
                    corpus_evidence_authority=CORPUS_EVIDENCE_AUTHORITY, training_cutoff_ns=training_cutoff_ns,
                    calibration_cutoff_ns=calibration_cutoff_ns,
                    scope=dict(instrument_ids=[instrument_id], context_id=f"paper-live-corpus:{instrument_id}"),
                    examples=[_feature_row(e) for e in split.train], calibration_examples=calibration_rows,
                    source=dict(schema=BUILD_SCHEMA_VERSION, split_fractions=list(SPLIT_FRACTIONS),
                                holdout_excluded=True, holdout_first_decision_ns=split.holdout[0].snapshot.decision_time_ns if split.holdout else None))
    directory = output_dir / instrument_id
    directory.mkdir(parents=True, exist_ok=True)
    manifest_path = directory / "training-manifest.json"
    write_canonical_json(manifest_path, manifest)
    built = build_path_a_production_artifacts(manifest_path, output_dir=directory, mode=mode, decision_time_ns=decision_time_ns)
    record.update(status=built.status, reason_codes=list(built.reason_codes), model_id=built.model_id,
                  calibration_model_id=built.calibration_model_id, artifact_hashes=built.artifact_hashes,
                  training_cutoff_ns=training_cutoff_ns, calibration_cutoff_ns=calibration_cutoff_ns)
    if not built.built:
        return record
    # The governed build refits from the manifest. The artifact is the one this split produced, or it is refused.
    stored = load_production_specialist_model(directory / "model")
    if stored is None or stored.model_id != model.model_id:
        return dict(record, status="BLOCKED", reason_codes=["REBUILT_MODEL_IDENTITY_MISMATCH"])
    calibration = load_paper_demo_calibration(directory / "calibration")
    if calibration is None:
        return dict(record, status="BLOCKED", reason_codes=["CALIBRATION_ARTIFACT_UNREADABLE"])
    base_rate = sum(e.label for e in split.train) / len(split.train)
    scores = score_holdout(stored, calibration, split.holdout, base_rate=base_rate)
    ok, reasons = eligibility(scores)
    record.update(holdout_scores=scores, eligible=ok, eligibility_rule=ELIGIBILITY_RULE_ID,
                  eligibility_reasons=reasons or ["HOLDOUT_SKILL_OVER_BASE_RATE"])
    write_canonical_json(directory / "evaluation.json", record)
    return record


def build_from_corpus(corpus_paths: Iterable[Path], *, output_root: Path, decision_time_ns: int,
                      instruments: Iterable[str] | None = None, mode: str = "paper") -> dict[str, Any]:
    paths = sorted(Path(p) for p in corpus_paths)
    grouped: dict[str, list[ProductionTrainingExample]] = {}
    for (instrument_id, _decision_ns), example in load_training_examples(paths):
        grouped.setdefault(instrument_id, []).append(example)
    wanted = sorted(set(instruments) if instruments else grouped)
    corpus_digest = sha256_bytes(canonical_bytes([[p.name, sha256_bytes(p.read_bytes())] for p in paths]))
    build_id = f"PFB-{datetime.fromtimestamp(decision_time_ns / 1e9, UTC).strftime('%Y%m%dT%H%M%SZ')}-{corpus_digest[:12]}"
    output_dir = output_root / build_id
    output_dir.mkdir(parents=True, exist_ok=True)
    results = [build_instrument(iid, grouped.get(iid, []), output_dir=output_dir, decision_time_ns=decision_time_ns, mode=mode)
               for iid in wanted]
    summary = dict(schema_version=BUILD_SCHEMA_VERSION, build_id=build_id, built_at=datetime.fromtimestamp(decision_time_ns / 1e9, UTC).isoformat(),
                   corpus_files=[p.name for p in paths], corpus_digest=corpus_digest, eligibility_rule=ELIGIBILITY_RULE_ID,
                   minimum_holdout_samples=MINIMUM_HOLDOUT_SAMPLES, split_fractions=list(SPLIT_FRACTIONS),
                   instruments={r["instrument_id"]: {k: r.get(k) for k in ("status", "eligible", "reason_codes", "eligibility_reasons", "samples",
                                                                          "train", "calibration", "holdout", "model_id", "calibration_model_id")}
                                for r in results},
                   eligible=[r["instrument_id"] for r in results if r.get("eligible")])
    write_canonical_json(output_dir / "build.json", summary)
    return summary


def read_build(directory: Path) -> dict[str, Any] | None:
    try:
        return json.loads((Path(directory) / "build.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


__all__ = [
    "BUILD_SCHEMA_VERSION",
    "ELIGIBILITY_RULE_ID",
    "MINIMUM_HOLDOUT_SAMPLES",
    "Split",
    "build_from_corpus",
    "build_instrument",
    "eligibility",
    "read_build",
    "score_holdout",
    "time_ordered_split",
]
