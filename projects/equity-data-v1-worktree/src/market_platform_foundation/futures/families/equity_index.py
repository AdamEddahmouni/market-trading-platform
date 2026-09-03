"""EQUITY_INDEX family plugin — ES/NQ interpretation (F6 v1)."""

from __future__ import annotations

from typing import Any

from ...contracts.futures import FuturesFamily
from .base import FAMILY_MODEL_VERSION, FamilyContextSnapshot


class EquityIndexFamilyModel:
    """Index futures family model — curve, carry, COT crowding, macro sensitivity."""

    family = FuturesFamily.EQUITY_INDEX
    model_version = FAMILY_MODEL_VERSION

    def required_capabilities(self) -> tuple[str, ...]:
        return (
            "futures_curve",
            "futures_positioning",
            "futures_baselines",
        )

    def curve_interpretation(self, workspace_context: dict[str, Any]) -> str:
        carry = workspace_context.get("carry_observation")
        curve_momentum = workspace_context.get("curve_momentum")
        if not isinstance(carry, dict) or not carry.get("available"):
            return "Curve/carry context unavailable — fail-closed."
        regime = "unknown"
        if isinstance(curve_momentum, dict):
            regime = str(curve_momentum.get("regime", "unknown"))
        annualized = carry.get("annualized_carry")
        if regime == "contango":
            return (
                f"Equity index term structure in contango "
                f"(annualized carry={annualized}); roll cost context, not return forecast."
            )
        if regime == "backwardation":
            return (
                f"Equity index term structure in backwardation "
                f"(annualized carry={annualized}); fair-value context only."
            )
        return f"Equity index carry observed (annualized carry={annualized}); interpretive context only."

    def positioning_interpretation(self, workspace_context: dict[str, Any]) -> str:
        if not workspace_context.get("futures_positioning_available"):
            return "COT positioning unavailable — crowding context suppressed."
        crowding = str(workspace_context.get("crowding_regime", "NEUTRAL"))
        positioning = workspace_context.get("positioning_snapshot")
        percentile = None
        if isinstance(positioning, dict):
            percentile = positioning.get("net_percentile")
        if crowding == "CROWDED_LONG":
            return (
                f"Managed-money COT crowded long (net percentile={percentile}); "
                "positioning pressure context, not directional forecast."
            )
        if crowding == "CROWDED_SHORT":
            return (
                f"Managed-money COT crowded short (net percentile={percentile}); "
                "positioning pressure context, not directional forecast."
            )
        return "COT positioning neutral — no crowding regime flagged."

    def event_context(self, macro_snapshot: dict[str, Any] | None) -> str:
        if not macro_snapshot or not macro_snapshot.get("available"):
            return "Macro event calendar unavailable — index event sensitivity suppressed."
        regime = str(macro_snapshot.get("macro_risk_regime", "UNAVAILABLE"))
        upcoming = macro_snapshot.get("upcoming_event_type")
        if regime == "ELEVATED" and upcoming:
            return (
                f"Index futures macro window elevated ahead of {upcoming}; "
                "rates/inflation surprise sensitivity — not a directional call."
            )
        if macro_snapshot.get("event_window_active"):
            return "Macro event window active for index futures — elevated vol context."
        return "Macro calendar normal — no elevated index event window."

    def risk_features(self, leverage_snapshot: dict[str, Any] | None) -> str:
        if not leverage_snapshot or not leverage_snapshot.get("available"):
            return "Leverage stress unavailable — liquidation context suppressed."
        regime = str(leverage_snapshot.get("stress_regime", "UNAVAILABLE"))
        long_risk = leverage_snapshot.get("long_liquidation_risk")
        short_risk = leverage_snapshot.get("short_liquidation_risk")
        if regime == "HIGH" and long_risk:
            return (
                "Elevated leveraged-long liquidation stress on index futures "
                "(distinct from equity short squeeze mechanics)."
            )
        if regime == "HIGH" and short_risk:
            return (
                "Elevated leveraged-short liquidation stress on index futures "
                "(distinct from equity short squeeze mechanics)."
            )
        if regime == "MODERATE":
            return "Moderate leverage stress on index futures — monitor margin + crowding jointly."
        return "Leverage stress low — no liquidation regime flagged."

    def build_context_snapshot(
        self,
        workspace_context: dict[str, Any],
        *,
        macro_snapshot: dict[str, Any] | None = None,
        leverage_snapshot: dict[str, Any] | None = None,
    ) -> FamilyContextSnapshot:
        quality_flags: list[str] = []
        if not workspace_context.get("futures_carry_available"):
            quality_flags.append("CURVE_CONTEXT_DEGRADED")
        if not workspace_context.get("futures_positioning_available"):
            quality_flags.append("POSITIONING_CONTEXT_DEGRADED")
        if macro_snapshot is None or not macro_snapshot.get("available"):
            quality_flags.append("MACRO_CONTEXT_DEGRADED")
        if leverage_snapshot is None or not leverage_snapshot.get("available"):
            quality_flags.append("LEVERAGE_CONTEXT_DEGRADED")

        return FamilyContextSnapshot(
            family=self.family,
            model_version=self.model_version,
            curve_read=self.curve_interpretation(workspace_context),
            positioning_read=self.positioning_interpretation(workspace_context),
            event_context_read=self.event_context(macro_snapshot),
            risk_context=self.risk_features(leverage_snapshot),
            quality_flags=tuple(dict.fromkeys(quality_flags)),
        )
