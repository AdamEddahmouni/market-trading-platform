"""Walk-forward OOS harness (DECISION-RESEARCH-001 §7).

Deterministic folds over ``ResearchExample`` rows ordered by
``decision_time_ns`` (``example_id`` tiebreak) — no RNG anywhere. Default is an
**expanding** window with a fixed tail-anchored OOS block
``B = max(min_oos_block, ceil(oos_block_frac * N))`` and ``folds`` sequential
blocks; optional **rolling** window (``window`` examples) per card's
``evaluation_window``. When the block scheme cannot fit, the harness falls back
to a single split delegating to ``chronological_split`` (0.6/0.2).

Run records are deterministic: same cards + examples + registry -> same
``run_id`` / ``run_root_hash`` (``DEC-DET-001``). Fold membership is
re-verified for PIT integrity every time (``verify_harness_folds``) and a
``CARD-*`` must be registry-bound into the run or verification fails closed
(``DEC-PRE-001``).

The harness performs no provider I/O; the only I/O is the registry check that
binds a run to its preregistered cards.
"""

from __future__ import annotations

import math
import uuid
from collections.abc import Callable
from typing import Any

from ...canonical import canonical_bytes, sha256_bytes
from .pit_gate import chronological_split, validate_temporal_example
from .registry import verify_experiment_card_registration

# Namespace for deterministic RUN-<uuid5> ids (same family as CARD ids).
RUN_NAMESPACE = uuid.UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8")

# Canonical family aliases: cards name lanes per spec §4 (e.g. MARKET_CONTEXT),
# while the example builder emits canonical family names (MACRO_CONTEXT). The
# harness canonicalizes both sides before matching.
CANONICAL_FAMILY_ALIASES: dict[str, str] = {"MARKET_CONTEXT": "MACRO_CONTEXT"}

Evaluator = Callable[..., dict[str, Any]]


def canonical_family(name: str) -> str:
    return CANONICAL_FAMILY_ALIASES.get(name, name)


def order_examples(examples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deterministic order: decision_time_ns asc, example_id asc tiebreak."""
    return sorted(
        examples, key=lambda ex: (int(ex["decision_time_ns"]), str(ex.get("example_id", "")))
    )


def example_family_set(example: dict[str, Any]) -> set[str]:
    return {canonical_family(f["evidence_family"]) for f in example.get("features", [])}


def evidence_bearing_subset(
    examples: list[dict[str, Any]],
    required_families: list[str],
) -> list[dict[str, Any]]:
    """Examples carrying every required family (canonicalized, no coercion)."""
    required = [canonical_family(f) for f in required_families]
    return [
        ex
        for ex in examples
        if all(r in example_family_set(ex) for r in required)
    ]


def _make_fold(
    fold_id: int,
    train: list[dict[str, Any]],
    test: list[dict[str, Any]],
    *,
    train_start_index: int,
    train_end_index: int,
    test_start_index: int,
    test_end_index: int,
) -> dict[str, Any]:
    return {
        "fold_id": fold_id,
        "train_start_cutoff": int(train[0]["decision_time_ns"]) if train else None,
        "train_end_cutoff": int(train[-1]["decision_time_ns"]) if train else None,
        "test_start_cutoff": int(test[0]["decision_time_ns"]) if test else None,
        "test_end_cutoff": int(test[-1]["decision_time_ns"]) if test else None,
        "train_count": len(train),
        "test_count": len(test),
        "train_start_index": train_start_index,
        "train_end_index": train_end_index,
        "test_start_index": test_start_index,
        "test_end_index": test_end_index,
    }


def build_folds(
    examples: list[dict[str, Any]],
    *,
    mode: str = "expanding",
    folds: int | None = None,
    oos_block_frac: float | None = None,
    min_oos_block: int | None = None,
    window: int | None = None,
    evaluation_window: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Deterministic positional folds over ``examples`` (order fixed internally).

    ``evaluation_window`` (from a card) overrides the scalar arguments: it may
    carry ``schema`` (``expanding_window`` | ``rolling_window``), ``folds``,
    ``oos_block_frac``, ``min_oos_block``, and ``window`` (rolling only).
    """
    cfg = dict(evaluation_window or {})
    schema = str(cfg.get("schema", "expanding_window"))
    if schema == "rolling_window":
        mode = "rolling"
    elif schema != "expanding_window":
        raise ValueError(f"HARNESS_FOLD_SCHEMA_INVALID:{schema}")
    folds = int(folds if folds is not None else cfg.get("folds", 4))
    oos_block_frac = float(oos_block_frac if oos_block_frac is not None else cfg.get("oos_block_frac", 0.15))
    min_oos_block = int(min_oos_block if min_oos_block is not None else cfg.get("min_oos_block", 50))
    window = int(window if window is not None else cfg.get("window", 0))

    if mode not in ("expanding", "rolling"):
        raise ValueError(f"HARNESS_FOLD_MODE_INVALID:{mode}")
    if folds < 1:
        raise ValueError("HARNESS_FOLD_COUNT_INVALID")

    ordered = order_examples(examples)
    n = len(ordered)
    if n < 2:
        return []
    block = max(min_oos_block, math.ceil(oos_block_frac * n))

    out: list[dict[str, Any]] = []
    if mode == "rolling" and window > 0:
        if n <= folds * block:
            return []
        for j in range(folds):
            test_start = n - (folds - j) * block
            test_end = test_start + block
            train_start = max(0, test_start - window)
            out.append(
                _make_fold(
                    j,
                    ordered[train_start:test_start],
                    ordered[test_start:test_end],
                    train_start_index=train_start,
                    train_end_index=test_start,
                    test_start_index=test_start,
                    test_end_index=test_end,
                )
            )
        return out

    # Expanding (default). If the block scheme cannot fit, fall back to a single
    # split that delegates to chronological_split (0.6/0.2).
    if n <= folds * block:
        split = chronological_split(ordered)
        test = split["validation"] + split["test"]
        if not test:
            return []
        train = split["train"]
        return [
            _make_fold(
                0,
                ordered[: len(train)],
                ordered[len(train) :],
                train_start_index=0,
                train_end_index=len(train),
                test_start_index=len(train),
                test_end_index=n,
            )
        ]

    for j in range(folds):
        test_start = n - (folds - j) * block
        test_end = test_start + block
        out.append(
            _make_fold(
                j,
                ordered[:test_start],
                ordered[test_start:test_end],
                train_start_index=0,
                train_end_index=test_start,
                test_start_index=test_start,
                test_end_index=test_end,
            )
        )
    return out


def fold_train_examples(
    fold: dict[str, Any], ordered: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    return list(ordered[int(fold["train_start_index"]) : int(fold["train_end_index"])])


def fold_test_examples(
    fold: dict[str, Any], ordered: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    return list(ordered[int(fold["test_start_index"]) : int(fold["test_end_index"])])


def verify_harness_folds(
    folds: list[dict[str, Any]], ordered: list[dict[str, Any]]
) -> tuple[str, list[str]]:
    """Re-verify fold PIT integrity and reject any boundary/leak violation.

    Checks, per fold: train strictly precedes test in decision time; no train
    example at-or-after the fold's test start; no test example at-or-before the
    fold's train end; every member example still passes the PIT gate.
    """
    reasons: list[str] = []
    for fold in folds:
        train = fold_train_examples(fold, ordered)
        test = fold_test_examples(fold, ordered)
        if not test:
            reasons.append(f"EMPTY_FOLD_TEST:{fold['fold_id']}")
            continue
        test_start = int(test[0]["decision_time_ns"])
        if train:
            train_end = int(train[-1]["decision_time_ns"])
            if train_end >= test_start:
                reasons.append(f"FOLD_TRAIN_TEST_OVERLAP:{fold['fold_id']}")
            for example in train:
                if int(example["decision_time_ns"]) >= test_start:
                    reasons.append(
                        f"FOLD_TRAIN_AFTER_TEST_START:{example.get('example_id')}"
                    )
        for example in train:
            ok, _reasons = validate_temporal_example(example)
            if not ok:
                reasons.append(f"FOLD_PIT_VIOLATION:{example.get('example_id')}")
        for example in test:
            if int(example["decision_time_ns"]) < test_start:
                reasons.append(f"FOLD_TEST_BEFORE_TEST_START:{example.get('example_id')}")
            ok, _reasons = validate_temporal_example(example)
            if not ok:
                reasons.append(f"FOLD_PIT_VIOLATION:{example.get('example_id')}")
    status = "PASS" if not reasons else "FAIL"
    return status, sorted(set(reasons))


def _run_body(
    *,
    family: str,
    cards: dict[str, Any],
    fold_plan: dict[str, list[dict[str, Any]]],
    results: dict[str, dict[str, Any]],
    oos_counts: dict[str, dict[str, int]],
    fold_pit: dict[str, str],
) -> dict[str, Any]:
    return {
        "family": family,
        "bound_card_hashes": {cid: card.card_hash for cid, card in sorted(cards.items())},
        "fold_plan": fold_plan,
        "results": results,
        "oos_counts": oos_counts,
        "fold_pit_status": fold_pit,
        "execution_authority": "NONE",
        "auto_strategy_promotion": False,
    }


def run_harness(
    cards: dict[str, Any],
    examples: list[dict[str, Any]],
    *,
    registry: Any | None = None,
    evaluate: Evaluator | None = None,
    family: str = "SHORT_SQUEEZE",
) -> dict[str, Any]:
    """Run the OOS harness for every card and return a deterministic run record.

    Fail-closed guarantees: every ``CARD-*`` must be bound into the run record
    (``DEC-PRE-001``) and, when ``registry`` is provided, present in it; any
    fold PIT violation raises. The canonical gate path always passes a registry.
    """
    from .experiments import evaluate_experiment

    if not cards:
        raise ValueError("HARNESS_NO_CARDS")
    ordered = order_examples(examples)
    evaluator = evaluate or evaluate_experiment

    # Bind every card into the run record first, then verify registration.
    prelim = {"bound_card_hashes": sorted({c.card_hash for c in cards.values()})}
    for card in cards.values():
        verify_experiment_card_registration(card, prelim, registry=registry)

    results: dict[str, dict[str, Any]] = {}
    fold_plan: dict[str, list[dict[str, Any]]] = {}
    oos_counts: dict[str, dict[str, int]] = {}
    fold_pit: dict[str, str] = {}

    ordered_cards = sorted(cards.values(), key=lambda c: c.experiment_id)

    # First pass: build and PIT-verify each card's OOS slice from its OWN
    # evidence-bearing subset (DEC-OOS-001).
    slices: dict[str, list[dict[str, Any]]] = {}
    pools: dict[str, int] = {}
    for card in ordered_cards:
        required = list((card.feature_spec or {}).get("required", []))
        subset = evidence_bearing_subset(ordered, required)
        folds = build_folds(subset, evaluation_window=card.evaluation_window)
        status, reasons = verify_harness_folds(folds, order_examples(subset))
        if status != "PASS" or reasons:
            raise RuntimeError("HARNESS_FOLD_PIT_FAIL:" + ";".join(reasons))
        fold_plan[card.experiment_id] = folds
        oos_examples = [
            ex for fold in folds for ex in fold_test_examples(fold, order_examples(subset))
        ]
        slices[card.experiment_id] = oos_examples
        pools[card.experiment_id] = len(subset)
        oos_counts[card.experiment_id] = {
            "evidence_bearing": len(subset),
            "oos": len(oos_examples),
        }

    # Second pass: evaluate. A baseline-relative metric must use the baseline
    # card's OWN measured OOS slice — never another card's slice and never a
    # 0.0 substitution (research integrity: fail closed rather than inventing
    # a baseline).
    for card in ordered_cards:
        baseline_rate: float | None = None
        if card.primary_metric != "oos_positive_base_rate":
            base_slice = slices.get(card.baseline_id)
            if base_slice is None:
                # The family is mispreregistered: there is no baseline card
                # result to measure against. Fail closed.
                raise ValueError(f"HARNESS_BASELINE_MISSING:{card.baseline_id}")
            if base_slice:
                positives = sum(
                    1 for ex in base_slice if ex.get("outcome", {}).get("positive")
                )
                baseline_rate = positives / len(base_slice)
            # An empty baseline OOS slice stays ``None``: cards that cannot
            # reach adjudication keep their negative results
            # (NEEDS_PROSPECTIVE_VALIDATION / INSUFFICIENT_DATA), while the
            # evaluator raises HARNESS_BASELINE_MISSING if a SUPPORTED-capable
            # branch would run without a measured baseline.
        result = evaluator(
            card,
            slices[card.experiment_id],
            baseline_rate=baseline_rate,
            pool_count=pools[card.experiment_id],
        )
        results[card.experiment_id] = result
        fold_pit[card.experiment_id] = "PASS"

    body = _run_body(
        family=family,
        cards=cards,
        fold_plan=fold_plan,
        results=results,
        oos_counts=oos_counts,
        fold_pit=fold_pit,
    )
    run_root_hash = sha256_bytes(canonical_bytes(body))
    run_id = "RUN-" + str(
        uuid.uuid5(RUN_NAMESPACE, canonical_bytes(body).decode("latin-1"))
    )
    body["run_id"] = run_id
    body["run_root_hash"] = run_root_hash
    body["registry_bound"] = registry is not None
    return body


__all__ = [
    "CANONICAL_FAMILY_ALIASES",
    "RUN_NAMESPACE",
    "build_folds",
    "canonical_family",
    "evidence_bearing_subset",
    "example_family_set",
    "fold_test_examples",
    "fold_train_examples",
    "order_examples",
    "run_harness",
    "verify_harness_folds",
]
