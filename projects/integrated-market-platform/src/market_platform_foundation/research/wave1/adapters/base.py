"""Family adapter registry (scores only; does not restate preregistered hypotheses)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..config import Wave1FamilyConfig
from ..errors import Wave1ConfigError


class Wave1ExampleAdapter(ABC):
    adapter_kind: str

    @abstractmethod
    def required_feature_tags(self) -> tuple[str, ...]:
        raise NotImplementedError

    @abstractmethod
    def baseline_score(self, example: dict[str, Any]) -> float | None:
        raise NotImplementedError

    @abstractmethod
    def candidate_score(self, example: dict[str, Any]) -> float | None:
        raise NotImplementedError

    def example_matches(self, example: dict[str, Any]) -> bool:
        tags = set(example.get("feature_tags") or [])
        return all(t in tags for t in self.required_feature_tags())


class _XsMediumTermMomentumAdapter(Wave1ExampleAdapter):
    adapter_kind = "xs_medium_term_momentum"

    def required_feature_tags(self) -> tuple[str, ...]:
        return ("XS_MOM_MEDIUM",)

    def baseline_score(self, example: dict[str, Any]) -> float | None:
        feats = example.get("features") or {}
        mom = feats.get("xs_mom_medium")
        return float(mom) if mom is not None else None

    def candidate_score(self, example: dict[str, Any]) -> float | None:
        feats = example.get("features") or {}
        if feats.get("xs_mom_medium") is None:
            return None
        vol = float(feats.get("realized_vol", 1.0) or 1.0)
        return float(feats["xs_mom_medium"]) / max(vol, 1e-6)


class _FuturesTsMomVolAdapter(Wave1ExampleAdapter):
    adapter_kind = "futures_ts_mom_vol_scaling"

    def required_feature_tags(self) -> tuple[str, ...]:
        return ("FUTURES_TS_MOM",)

    def baseline_score(self, example: dict[str, Any]) -> float | None:
        feats = example.get("features") or {}
        mom = feats.get("ts_mom")
        return float(mom) if mom is not None else None

    def candidate_score(self, example: dict[str, Any]) -> float | None:
        feats = example.get("features") or {}
        mom = feats.get("ts_mom")
        if mom is None:
            return None
        target_vol = float(feats.get("target_vol", 0.15) or 0.15)
        realized = float(feats.get("realized_vol", target_vol) or target_vol)
        scale = target_vol / max(realized, 1e-6)
        return float(mom) * scale


class _PriceActionGeometryAdapter(Wave1ExampleAdapter):
    adapter_kind = "continuous_price_action_geometry"

    def required_feature_tags(self) -> tuple[str, ...]:
        return ("PRICE_GEOMETRY",)

    def baseline_score(self, example: dict[str, Any]) -> float | None:
        feats = example.get("features") or {}
        slope = feats.get("geometry_slope")
        return float(slope) if slope is not None else None

    def candidate_score(self, example: dict[str, Any]) -> float | None:
        feats = example.get("features") or {}
        slope = feats.get("geometry_slope")
        curvature = feats.get("geometry_curvature")
        if slope is None or curvature is None:
            return None
        return float(slope) + 0.25 * float(curvature)


class _RvContinuousRegimeAdapter(Wave1ExampleAdapter):
    adapter_kind = "rv_continuous_vs_regime"

    def required_feature_tags(self) -> tuple[str, ...]:
        return ("RV_CONTINUOUS",)

    def baseline_score(self, example: dict[str, Any]) -> float | None:
        feats = example.get("features") or {}
        rv = feats.get("rv_continuous")
        return float(rv) if rv is not None else None

    def candidate_score(self, example: dict[str, Any]) -> float | None:
        feats = example.get("features") or {}
        rv = feats.get("rv_continuous")
        regime = feats.get("rv_regime_scale")
        if rv is None or regime is None:
            return None
        return float(rv) * float(regime)


class _ExecutionCostStackAdapter(Wave1ExampleAdapter):
    adapter_kind = "execution_cost_stack_survival"

    def required_feature_tags(self) -> tuple[str, ...]:
        return ("EXEC_COST_STACK",)

    def baseline_score(self, example: dict[str, Any]) -> float | None:
        feats = example.get("features") or {}
        cost = feats.get("stack_cost_bps")
        return -float(cost) if cost is not None else None

    def candidate_score(self, example: dict[str, Any]) -> float | None:
        feats = example.get("features") or {}
        cost = feats.get("stack_cost_bps")
        alpha = feats.get("alpha_bps")
        if cost is None or alpha is None:
            return None
        return float(alpha) - float(cost)


class _AllocationAdapter(Wave1ExampleAdapter):
    adapter_kind = "allocation_inverse_vol_erc_minvar"

    def required_feature_tags(self) -> tuple[str, ...]:
        return ("ALLOCATION",)

    def baseline_score(self, example: dict[str, Any]) -> float | None:
        feats = example.get("features") or {}
        w = feats.get("equal_weight_return_bps")
        return float(w) if w is not None else None

    def candidate_score(self, example: dict[str, Any]) -> float | None:
        feats = example.get("features") or {}
        for key in ("inverse_vol_return_bps", "erc_return_bps", "minvar_return_bps"):
            if feats.get(key) is not None:
                return float(feats[key])
        return None


class _MacroStateCalibrationAdapter(Wave1ExampleAdapter):
    adapter_kind = "pit_macro_state_calibration"

    def required_feature_tags(self) -> tuple[str, ...]:
        return ("MACRO_STATE",)

    def baseline_score(self, example: dict[str, Any]) -> float | None:
        feats = example.get("features") or {}
        p = feats.get("macro_prob")
        return float(p) if p is not None else None

    def candidate_score(self, example: dict[str, Any]) -> float | None:
        feats = example.get("features") or {}
        p = feats.get("macro_prob_calibrated")
        if p is None:
            return None
        return float(p)


class _L1TobOfiAdapter(Wave1ExampleAdapter):
    adapter_kind = "l1_tob_ofi_incremental"

    def required_feature_tags(self) -> tuple[str, ...]:
        return ("L1_TOB_OFI",)

    def baseline_score(self, example: dict[str, Any]) -> float | None:
        feats = example.get("features") or {}
        mid = feats.get("mid_return_bps")
        return float(mid) if mid is not None else None

    def candidate_score(self, example: dict[str, Any]) -> float | None:
        feats = example.get("features") or {}
        mid = feats.get("mid_return_bps")
        ofi = feats.get("ofi")
        if mid is None or ofi is None:
            return None
        return float(mid) + 0.01 * float(ofi)


_ADAPTERS: dict[str, Wave1ExampleAdapter] = {
    cls.adapter_kind: cls()
    for cls in (
        _XsMediumTermMomentumAdapter,
        _FuturesTsMomVolAdapter,
        _PriceActionGeometryAdapter,
        _RvContinuousRegimeAdapter,
        _ExecutionCostStackAdapter,
        _AllocationAdapter,
        _MacroStateCalibrationAdapter,
        _L1TobOfiAdapter,
    )
}


def get_family_adapter(config: Wave1FamilyConfig) -> Wave1ExampleAdapter:
    adapter = _ADAPTERS.get(config.adapter_kind)
    if adapter is None:
        raise Wave1ConfigError(
            "W1_ADAPTER_KIND_UNKNOWN",
            details={"adapter_kind": config.adapter_kind, "family_id": config.family_id},
        )
    return adapter
