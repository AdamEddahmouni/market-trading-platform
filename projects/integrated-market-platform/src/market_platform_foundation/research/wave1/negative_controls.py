"""Deterministic negative controls for Wave 1 sanity checks."""

from __future__ import annotations

import copy
from typing import Any

from .config import Wave1FamilyConfig


def apply_negative_control(
    control_id: str,
    examples: list[dict[str, Any]],
    *,
    seed: int,
) -> list[dict[str, Any]]:
    if control_id == "label_shuffle":
        return _label_shuffle(examples, seed=seed)
    if control_id == "feature_permutation":
        return _permute_feature_keys(examples, seed=seed + 1)
    if control_id in {"vol_scale_null", "geometry_mirror", "regime_permutation", "weight_permutation"}:
        return _scale_noise(examples, seed=seed + 2)
    if control_id in {"cost_stack_inflate", "macro_state_shuffle", "ofi_sign_flip"}:
        return _invert_scores_inputs(examples, control_id=control_id)
    return copy.deepcopy(examples)


def run_negative_controls(
    config: Wave1FamilyConfig,
    examples: list[dict[str, Any]],
    *,
    seed: int,
) -> dict[str, list[dict[str, Any]]]:
    return {
        control_id: apply_negative_control(control_id, examples, seed=seed + index)
        for index, control_id in enumerate(config.negative_controls)
    }


def _label_shuffle(examples: list[dict[str, Any]], *, seed: int) -> list[dict[str, Any]]:
    shuffled = copy.deepcopy(examples)
    outcomes = [ex.get("outcome") for ex in shuffled]
    order = _deterministic_order(len(outcomes), seed)
    rotated = [outcomes[i] for i in order]
    for ex, outcome in zip(shuffled, rotated, strict=True):
        ex["outcome"] = copy.deepcopy(outcome)
    return shuffled


def _permute_feature_keys(examples: list[dict[str, Any]], *, seed: int) -> list[dict[str, Any]]:
    mutated = copy.deepcopy(examples)
    for index, ex in enumerate(mutated):
        feats = dict(ex.get("features") or {})
        if not feats:
            continue
        keys = sorted(feats.keys())
        if len(keys) < 2:
            continue
        shift = 1 + (seed + index) % (len(keys) - 1)
        rotated = keys[shift:] + keys[:shift]
        ex["features"] = {rotated[i]: feats[keys[i]] for i in range(len(keys))}
    return mutated


def _scale_noise(examples: list[dict[str, Any]], *, seed: int) -> list[dict[str, Any]]:
    mutated = copy.deepcopy(examples)
    for index, ex in enumerate(mutated):
        feats = dict(ex.get("features") or {})
        for key, value in list(feats.items()):
            if isinstance(value, (int, float)):
                sign = -1.0 if (seed + index) % 2 else 1.0
                feats[key] = sign * float(value)
        ex["features"] = feats
    return mutated


def _invert_scores_inputs(examples: list[dict[str, Any]], *, control_id: str) -> list[dict[str, Any]]:
    mutated = copy.deepcopy(examples)
    for ex in mutated:
        feats = dict(ex.get("features") or {})
        if control_id == "cost_stack_inflate" and "stack_cost_bps" in feats:
            feats["stack_cost_bps"] = float(feats["stack_cost_bps"]) * 4.0
        if control_id == "macro_state_shuffle" and "macro_prob_calibrated" in feats:
            feats["macro_prob_calibrated"] = 1.0 - float(feats["macro_prob_calibrated"])
        if control_id == "ofi_sign_flip" and "ofi" in feats:
            feats["ofi"] = -float(feats["ofi"])
        ex["features"] = feats
    return mutated


def _deterministic_order(n: int, seed: int) -> list[int]:
    order = list(range(n))
    if n < 2:
        return order
    shift = 1 + seed % (n - 1)
    return order[shift:] + order[:shift]
