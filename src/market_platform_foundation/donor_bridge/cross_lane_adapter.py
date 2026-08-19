"""Map IMP whale projections into cross-lane causal inputs."""

from __future__ import annotations

from typing import Any

from ..cross_lane.evidence import (
    EvidenceProvenanceClass,
    EvidenceSignal,
    LaneId,
    NormalizedLaneEvidence,
    lane_evidence_to_dict,
)


def build_cross_lane_snapshot_from_order_flow(
    order_flow_payload: dict[str, Any] | None,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """Derive cross-lane snapshot + normalized evidence from order-flow workspace payload."""
    if not order_flow_payload or not order_flow_payload.get("available"):
        return None, []

    bars = order_flow_payload.get("bars") or []
    if not isinstance(bars, list) or not bars:
        return None, []

    deltas: list[float] = []
    cumulative: list[float] = []
    for bar in bars:
        if not isinstance(bar, dict):
            continue
        delta = bar.get("delta")
        if delta is not None:
            try:
                deltas.append(float(delta))
            except (TypeError, ValueError):
                continue
        cvd = bar.get("cumulative_delta")
        if cvd is not None:
            try:
                cumulative.append(float(cvd))
            except (TypeError, ValueError):
                continue

    if not deltas and not cumulative:
        return None, []

    cvd_slope: float | None = None
    if len(cumulative) >= 2:
        cvd_slope = cumulative[-1] - cumulative[-2]
    elif len(deltas) >= 2:
        cvd_slope = sum(deltas[-3:]) / min(3, len(deltas))

    aggressive_buy = False
    aggressive_sell = False
    if deltas:
        recent = deltas[-5:]
        buy_volume = sum(value for value in recent if value > 0)
        sell_volume = abs(sum(value for value in recent if value < 0))
        aggressive_buy = buy_volume > sell_volume * 1.25 and buy_volume > 0
        aggressive_sell = sell_volume > buy_volume * 1.25 and sell_volume > 0

    snapshot = {
        "order_flow_available": True,
        "order_flow_cvd_slope": cvd_slope,
        "order_flow_aggressive_buy": aggressive_buy,
        "order_flow_aggressive_sell": aggressive_sell,
        "options_available": False,
        "attention_available": False,
    }

    evidence: list[dict[str, Any]] = []
    if aggressive_buy:
        evidence.append(
            lane_evidence_to_dict(
                NormalizedLaneEvidence(
                    lane=LaneId.ORDER_FLOW,
                    signal=EvidenceSignal.AGGRESSIVE_BUY_PRESSURE,
                    strength="MODERATE",
                    available=True,
                    source_ref="whale:order_flow",
                    detail="Recent net aggressive buy volume elevated vs sell volume",
                    provenance_class=EvidenceProvenanceClass.DERIVED,
                )
            )
        )
    if aggressive_sell:
        evidence.append(
            lane_evidence_to_dict(
                NormalizedLaneEvidence(
                    lane=LaneId.ORDER_FLOW,
                    signal=EvidenceSignal.AGGRESSIVE_SELL_PRESSURE,
                    strength="MODERATE",
                    available=True,
                    source_ref="whale:order_flow",
                    detail="Recent net aggressive sell volume elevated vs buy volume",
                    provenance_class=EvidenceProvenanceClass.DERIVED,
                )
            )
        )
    if cvd_slope is not None and cvd_slope > 0:
        evidence.append(
            lane_evidence_to_dict(
                NormalizedLaneEvidence(
                    lane=LaneId.ORDER_FLOW,
                    signal=EvidenceSignal.CVD_POSITIVE_SLOPE,
                    strength="MODERATE" if cvd_slope < 500 else "HIGH",
                    available=True,
                    source_ref="whale:order_flow",
                    detail=f"CVD slope {cvd_slope:.2f}",
                    provenance_class=EvidenceProvenanceClass.DERIVED,
                )
            )
        )
    elif cvd_slope is not None and cvd_slope < 0:
        evidence.append(
            lane_evidence_to_dict(
                NormalizedLaneEvidence(
                    lane=LaneId.ORDER_FLOW,
                    signal=EvidenceSignal.CVD_NEGATIVE_SLOPE,
                    strength="MODERATE",
                    available=True,
                    source_ref="whale:order_flow",
                    detail=f"CVD slope {cvd_slope:.2f}",
                    provenance_class=EvidenceProvenanceClass.DERIVED,
                )
            )
        )

    return snapshot, evidence


def build_cross_lane_snapshot_from_order_book(
    order_book_payload: dict[str, Any] | None,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """Publish resting-book pressure evidence without domain directional interpretation."""
    if not order_book_payload or not order_book_payload.get("available"):
        return None, []

    latest_l1 = order_book_payload.get("latest_l1")
    imbalance_ratio = order_book_payload.get("latest_imbalance_ratio")
    liquidity_summary = order_book_payload.get("latest_liquidity_summary")
    impact_summary = order_book_payload.get("latest_impact_summary")
    forecast_summary = order_book_payload.get("latest_microstructure_forecast")
    execution_summary = order_book_payload.get("latest_execution_forecast")
    qi: float | None = None
    if isinstance(latest_l1, dict):
        raw_qi = latest_l1.get("queue_imbalance")
        if isinstance(raw_qi, (int, float)):
            qi = float(raw_qi)

    snapshot = {
        "order_book_available": True,
        "order_book_imbalance_ratio": imbalance_ratio,
        "order_book_queue_imbalance_l1": qi,
    }
    if isinstance(liquidity_summary, dict):
        snapshot["order_book_liquidity_method"] = liquidity_summary.get("liquidity_method")
        snapshot["order_book_depth_withdrawal"] = liquidity_summary.get("depth_withdrawal")
        snapshot["order_book_depth_replenishment"] = liquidity_summary.get("depth_replenishment")
        snapshot["order_book_fragility_score"] = liquidity_summary.get("fragility_score")
        snapshot["order_book_resiliency_score"] = liquidity_summary.get("resiliency_score")
    if isinstance(impact_summary, dict):
        snapshot["order_book_impact_regime"] = impact_summary.get("impact_regime")
        snapshot["order_book_absorption_score"] = impact_summary.get("absorption_score")
        snapshot["order_book_exhaustion_score"] = impact_summary.get("exhaustion_score")
        snapshot["order_book_price_efficiency"] = impact_summary.get("price_efficiency")
    if isinstance(forecast_summary, dict):
        snapshot["order_book_forecast_direction"] = forecast_summary.get("direction_bias")
        snapshot["order_book_continuation_probability"] = forecast_summary.get("continuation_probability")
        snapshot["order_book_reversal_probability"] = forecast_summary.get("reversal_probability")
        snapshot["order_book_expected_mid_delta"] = forecast_summary.get("expected_mid_delta")
    if isinstance(execution_summary, dict):
        snapshot["order_book_fill_probability"] = execution_summary.get("aggressive_fill_probability")
        snapshot["order_book_expected_slippage"] = execution_summary.get("expected_slippage_spread_fraction")
        snapshot["order_book_adverse_selection_risk"] = execution_summary.get("adverse_selection_risk")
    evidence: list[dict[str, Any]] = []
    threshold = 0.15
    if qi is not None and qi >= threshold:
        evidence.append(
            lane_evidence_to_dict(
                NormalizedLaneEvidence(
                    lane=LaneId.ORDER_FLOW,
                    signal=EvidenceSignal.BOOK_IMBALANCE_BID,
                    strength="MODERATE" if qi < 0.35 else "HIGH",
                    available=True,
                    source_ref="whale:order_book",
                    detail=f"L1 queue imbalance bid-heavy ({qi:.2f}) — resting liquidity, not aggression",
                    provenance_class=EvidenceProvenanceClass.DERIVED,
                )
            )
        )
    elif qi is not None and qi <= -threshold:
        evidence.append(
            lane_evidence_to_dict(
                NormalizedLaneEvidence(
                    lane=LaneId.ORDER_FLOW,
                    signal=EvidenceSignal.BOOK_IMBALANCE_ASK,
                    strength="MODERATE" if qi > -0.35 else "HIGH",
                    available=True,
                    source_ref="whale:order_book",
                    detail=f"L1 queue imbalance ask-heavy ({qi:.2f}) — resting liquidity, not aggression",
                    provenance_class=EvidenceProvenanceClass.DERIVED,
                )
            )
        )
    if isinstance(liquidity_summary, dict):
        withdrawal = liquidity_summary.get("depth_withdrawal")
        replenishment = liquidity_summary.get("depth_replenishment")
        fragility = liquidity_summary.get("fragility_score")
        if isinstance(withdrawal, (int, float)) and withdrawal > 0:
            evidence.append(
                lane_evidence_to_dict(
                    NormalizedLaneEvidence(
                        lane=LaneId.ORDER_FLOW,
                        signal=EvidenceSignal.LIQUIDITY_WITHDRAWAL,
                        strength="MODERATE" if withdrawal < 300 else "HIGH",
                        available=True,
                        source_ref="whale:order_book",
                        detail=f"Displayed depth withdrawal {withdrawal:.0f} — not trade-confirmed",
                        provenance_class=EvidenceProvenanceClass.DERIVED,
                    )
                )
            )
        if isinstance(replenishment, (int, float)) and replenishment > 0:
            evidence.append(
                lane_evidence_to_dict(
                    NormalizedLaneEvidence(
                        lane=LaneId.ORDER_FLOW,
                        signal=EvidenceSignal.LIQUIDITY_REPLENISHMENT,
                        strength="MODERATE" if replenishment < 300 else "HIGH",
                        available=True,
                        source_ref="whale:order_book",
                        detail=f"Displayed depth replenishment {replenishment:.0f}",
                        provenance_class=EvidenceProvenanceClass.DERIVED,
                    )
                )
            )
        if isinstance(fragility, (int, float)) and fragility >= 0.25:
            evidence.append(
                lane_evidence_to_dict(
                    NormalizedLaneEvidence(
                        lane=LaneId.ORDER_FLOW,
                        signal=EvidenceSignal.BOOK_FRAGILITY_ELEVATED,
                        strength="MODERATE" if fragility < 0.4 else "HIGH",
                        available=True,
                        source_ref="whale:order_book",
                        detail=f"Book fragility score {fragility:.2f}",
                        provenance_class=EvidenceProvenanceClass.DERIVED,
                    )
                )
            )
    if isinstance(impact_summary, dict):
        regime = str(impact_summary.get("impact_regime", "NEUTRAL"))
        absorption = impact_summary.get("absorption_score")
        exhaustion = impact_summary.get("exhaustion_score")
        replenishment = liquidity_summary.get("depth_replenishment") if isinstance(liquidity_summary, dict) else None
        withdrawal = liquidity_summary.get("depth_withdrawal") if isinstance(liquidity_summary, dict) else None
        liquidity_ctx = ""
        if isinstance(replenishment, (int, float)) and replenishment > 0:
            liquidity_ctx = f"; replenishment {replenishment:.0f}"
        if isinstance(withdrawal, (int, float)) and withdrawal > 0:
            liquidity_ctx += f"; withdrawal {withdrawal:.0f}"
        if regime == "BUY_ABSORPTION":
            strength = "HIGH" if isinstance(absorption, (int, float)) and absorption >= 0.5 else "MODERATE"
            evidence.append(
                lane_evidence_to_dict(
                    NormalizedLaneEvidence(
                        lane=LaneId.ORDER_FLOW,
                        signal=EvidenceSignal.ABSORPTION_BUY,
                        strength=strength,
                        available=True,
                        source_ref="whale:order_book",
                        detail=(
                            "Book flow buy absorption — high aggression with weak upward progress"
                            + liquidity_ctx
                        ),
                        provenance_class=EvidenceProvenanceClass.DERIVED,
                    )
                )
            )
        elif regime == "SELL_ABSORPTION":
            strength = "HIGH" if isinstance(absorption, (int, float)) and absorption >= 0.5 else "MODERATE"
            evidence.append(
                lane_evidence_to_dict(
                    NormalizedLaneEvidence(
                        lane=LaneId.ORDER_FLOW,
                        signal=EvidenceSignal.ABSORPTION_SELL,
                        strength=strength,
                        available=True,
                        source_ref="whale:order_book",
                        detail=(
                            "Book flow sell absorption — high aggression with weak downward progress"
                            + liquidity_ctx
                        ),
                        provenance_class=EvidenceProvenanceClass.DERIVED,
                    )
                )
            )
        elif regime == "BUY_EXHAUSTION":
            strength = "HIGH" if isinstance(exhaustion, (int, float)) and exhaustion >= 0.5 else "MODERATE"
            evidence.append(
                lane_evidence_to_dict(
                    NormalizedLaneEvidence(
                        lane=LaneId.ORDER_FLOW,
                        signal=EvidenceSignal.EXHAUSTION_BUY,
                        strength=strength,
                        available=True,
                        source_ref="whale:order_book",
                        detail=(
                            "Book flow buy exhaustion — decaying buy aggression, progress stalling"
                            + liquidity_ctx
                        ),
                        provenance_class=EvidenceProvenanceClass.DERIVED,
                    )
                )
            )
        elif regime == "SELL_EXHAUSTION":
            strength = "HIGH" if isinstance(exhaustion, (int, float)) and exhaustion >= 0.5 else "MODERATE"
            evidence.append(
                lane_evidence_to_dict(
                    NormalizedLaneEvidence(
                        lane=LaneId.ORDER_FLOW,
                        signal=EvidenceSignal.EXHAUSTION_SELL,
                        strength=strength,
                        available=True,
                        source_ref="whale:order_book",
                        detail=(
                            "Book flow sell exhaustion — decaying sell aggression, progress stalling"
                            + liquidity_ctx
                        ),
                        provenance_class=EvidenceProvenanceClass.DERIVED,
                    )
                )
            )
    if isinstance(forecast_summary, dict):
        from ..order_flow.forecast import CONTINUATION_THRESHOLD, REVERSAL_THRESHOLD

        direction = str(forecast_summary.get("direction_bias", "NEUTRAL"))
        continuation = forecast_summary.get("continuation_probability")
        reversal = forecast_summary.get("reversal_probability")
        fragility = (
            liquidity_summary.get("fragility_score") if isinstance(liquidity_summary, dict) else None
        )
        impact_regime = (
            str(impact_summary.get("impact_regime", "NEUTRAL"))
            if isinstance(impact_summary, dict)
            else "NEUTRAL"
        )
        ctx_parts: list[str] = []
        if isinstance(fragility, (int, float)):
            ctx_parts.append(f"fragility {fragility:.2f}")
        if impact_regime != "NEUTRAL":
            ctx_parts.append(f"impact {impact_regime}")
        ctx = f" ({', '.join(ctx_parts)})" if ctx_parts else ""
        if (
            direction == "UP"
            and isinstance(continuation, (int, float))
            and continuation >= CONTINUATION_THRESHOLD
        ):
            evidence.append(
                lane_evidence_to_dict(
                    NormalizedLaneEvidence(
                        lane=LaneId.ORDER_FLOW,
                        signal=EvidenceSignal.MICROSTRUCTURE_CONTINUATION_UP,
                        strength="HIGH" if continuation >= 0.7 else "MODERATE",
                        available=True,
                        source_ref="whale:order_book",
                        detail=(
                            f"Short-horizon microstructure continuation UP "
                            f"(p={continuation:.2f}){ctx}"
                        ),
                        provenance_class=EvidenceProvenanceClass.DERIVED,
                    )
                )
            )
        elif (
            direction == "DOWN"
            and isinstance(continuation, (int, float))
            and continuation >= CONTINUATION_THRESHOLD
        ):
            evidence.append(
                lane_evidence_to_dict(
                    NormalizedLaneEvidence(
                        lane=LaneId.ORDER_FLOW,
                        signal=EvidenceSignal.MICROSTRUCTURE_CONTINUATION_DOWN,
                        strength="HIGH" if continuation >= 0.7 else "MODERATE",
                        available=True,
                        source_ref="whale:order_book",
                        detail=(
                            f"Short-horizon microstructure continuation DOWN "
                            f"(p={continuation:.2f}){ctx}"
                        ),
                        provenance_class=EvidenceProvenanceClass.DERIVED,
                    )
                )
            )
        if isinstance(reversal, (int, float)) and reversal >= REVERSAL_THRESHOLD:
            evidence.append(
                lane_evidence_to_dict(
                    NormalizedLaneEvidence(
                        lane=LaneId.ORDER_FLOW,
                        signal=EvidenceSignal.MICROSTRUCTURE_REVERSAL_RISK,
                        strength="HIGH" if reversal >= 0.6 else "MODERATE",
                        available=True,
                        source_ref="whale:order_book",
                        detail=f"Short-horizon reversal risk elevated (p={reversal:.2f}){ctx}",
                        provenance_class=EvidenceProvenanceClass.DERIVED,
                    )
                )
            )
    if isinstance(execution_summary, dict):
        from ..order_flow.evidence import (
            ADVERSE_SELECTION_THRESHOLD,
            FILL_RISK_THRESHOLD,
            SLIPPAGE_ELEVATED_THRESHOLD,
        )

        slip = execution_summary.get("expected_slippage_spread_fraction")
        fill_prob = execution_summary.get("aggressive_fill_probability")
        adverse = execution_summary.get("adverse_selection_risk")
        method = execution_summary.get("execution_method", "execution_book_aware_v1")
        if isinstance(slip, (int, float)) and slip >= SLIPPAGE_ELEVATED_THRESHOLD:
            evidence.append(
                lane_evidence_to_dict(
                    NormalizedLaneEvidence(
                        lane=LaneId.ORDER_FLOW,
                        signal=EvidenceSignal.EXECUTION_SLIPPAGE_ELEVATED,
                        strength="HIGH" if slip >= SLIPPAGE_ELEVATED_THRESHOLD * 2 else "MODERATE",
                        available=True,
                        source_ref="whale:order_book",
                        detail=f"Expected slippage elevated ({slip:.4f} spread fraction) — {method}",
                        provenance_class=EvidenceProvenanceClass.DERIVED,
                    )
                )
            )
        if isinstance(fill_prob, (int, float)) and fill_prob < FILL_RISK_THRESHOLD:
            evidence.append(
                lane_evidence_to_dict(
                    NormalizedLaneEvidence(
                        lane=LaneId.ORDER_FLOW,
                        signal=EvidenceSignal.EXECUTION_FILL_RISK,
                        strength="HIGH" if fill_prob < 0.35 else "MODERATE",
                        available=True,
                        source_ref="whale:order_book",
                        detail=f"Aggressive fill probability low (p={fill_prob:.2f})",
                        provenance_class=EvidenceProvenanceClass.DERIVED,
                    )
                )
            )
        if isinstance(adverse, (int, float)) and adverse >= ADVERSE_SELECTION_THRESHOLD:
            evidence.append(
                lane_evidence_to_dict(
                    NormalizedLaneEvidence(
                        lane=LaneId.ORDER_FLOW,
                        signal=EvidenceSignal.ADVERSE_SELECTION_RISK_ELEVATED,
                        strength="HIGH" if adverse >= 0.6 else "MODERATE",
                        available=True,
                        source_ref="whale:order_book",
                        detail=f"Adverse selection risk elevated ({adverse:.2f})",
                        provenance_class=EvidenceProvenanceClass.DERIVED,
                    )
                )
            )
    return snapshot, evidence


def build_cross_lane_snapshot_from_options(
    options_payload: dict[str, Any] | None,
    *,
    prior_cross_lane: dict[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """Derive cross-lane snapshot + normalized evidence from options workspace payload.

    Uses only admitted unusual-activity context — does not infer signed flow or dealer
    gamma when data is unavailable (fail closed per O-15, O-17).
    """
    if not options_payload:
        return None, []

    chain_available = bool(options_payload.get("chain_available"))
    if not options_payload.get("available") and not chain_available:
        execution_snapshot = options_payload.get("execution_snapshot")
        has_execution = isinstance(execution_snapshot, dict) and execution_snapshot.get("available")
        if not has_execution:
            return None, []

    activities = options_payload.get("activities") or []
    if not isinstance(activities, list):
        activities = []

    chain_contracts = options_payload.get("canonical_contracts")
    if not isinstance(chain_contracts, list):
        chain_contracts = []
    chain_snapshot = options_payload.get("chain_snapshot")
    if not chain_contracts and isinstance(chain_snapshot, dict):
        raw_contracts = chain_snapshot.get("contracts")
        if isinstance(raw_contracts, list):
            chain_contracts = raw_contracts

    if not activities and not chain_contracts:
        event_vol_snapshot = options_payload.get("event_vol_snapshot")
        strategy_snapshot = options_payload.get("strategy_snapshot")
        execution_snapshot = options_payload.get("execution_snapshot")
        has_event_vol = isinstance(event_vol_snapshot, dict) and event_vol_snapshot.get("available")
        has_strategy = isinstance(strategy_snapshot, dict) and strategy_snapshot.get("available")
        has_execution = isinstance(execution_snapshot, dict) and execution_snapshot.get("available")
        if not has_event_vol and not has_strategy and not has_execution:
            return None, []

    elevated_calls = 0
    elevated_volume = 0
    ambiguous_direction = 0
    high_scores = 0
    for activity in activities:
        if not isinstance(activity, dict):
            continue
        option_type = str(activity.get("option_type", "")).lower()
        if option_type == "call":
            vol_oi = activity.get("volume_oi_ratio")
            if isinstance(vol_oi, (int, float)) and vol_oi >= 2.0:
                elevated_calls += 1
        vol_ratio = activity.get("volume_ratio")
        if isinstance(vol_ratio, (int, float)) and vol_ratio >= 1.5:
            elevated_volume += 1
        direction = str(activity.get("direction_label", "ambiguous"))
        if direction == "ambiguous":
            ambiguous_direction += 1
        score = activity.get("confirmation_score")
        if isinstance(score, (int, float)) and score >= 70:
            high_scores += 1

    from ..options.dealer import (
        GAMMA_AMPLIFICATION_THRESHOLD,
        HEDGING_PRESSURE_THRESHOLD,
        build_dealer_snapshot,
    )
    from ..options.flow import build_flow_snapshot

    as_of_time = ""
    if activities:
        as_of_time = str(activities[0].get("event_time", ""))
    elif chain_contracts:
        as_of_time = str(chain_contracts[0].get("event_time", ""))

    flow_snapshot = options_payload.get("signed_flow_snapshot")
    if not isinstance(flow_snapshot, dict) and activities:
        flow_snapshot = build_flow_snapshot(activities, as_of_time=as_of_time)
    if not isinstance(flow_snapshot, dict):
        flow_snapshot = {}

    signed_flow_available = bool(flow_snapshot.get("signed_flow_available"))

    dealer_snapshot = options_payload.get("dealer_snapshot")
    if not isinstance(dealer_snapshot, dict):
        dealer_source = chain_contracts if chain_contracts else activities
        dealer_snapshot = build_dealer_snapshot(
            dealer_source if isinstance(dealer_source, list) else [],
            as_of_time=as_of_time,
        )
    dealer_position_available = bool(dealer_snapshot.get("available"))

    net_gamma = dealer_snapshot.get("estimated_dealer_gamma", 0)
    gamma_regime = str(dealer_snapshot.get("gamma_regime", ""))
    hedging_pressure = dealer_snapshot.get("hedging_pressure_estimate")
    gamma_amplification = (
        dealer_position_available
        and gamma_regime == "negative_gamma"
        and isinstance(net_gamma, (int, float))
        and abs(net_gamma) >= GAMMA_AMPLIFICATION_THRESHOLD
    )
    call_demand_anomaly = elevated_calls >= 2 and elevated_volume >= 2

    dominant_direction = flow_snapshot.get("dominant_direction")
    options_flow_reversal = bool(
        signed_flow_available and dominant_direction == "sell_initiated"
    )

    prior_gamma_amp = False
    prior_hedging: float | None = None
    if isinstance(prior_cross_lane, dict):
        prior_gamma_amp = bool(prior_cross_lane.get("options_gamma_amplification"))
        prior_hedging_raw = prior_cross_lane.get("options_hedging_pressure")
        if isinstance(prior_hedging_raw, (int, float)):
            prior_hedging = float(prior_hedging_raw)

    options_gamma_decay = False
    if dealer_position_available:
        if prior_gamma_amp and not gamma_amplification:
            options_gamma_decay = True
        elif (
            prior_hedging is not None
            and prior_hedging >= HEDGING_PRESSURE_THRESHOLD
            and isinstance(hedging_pressure, (int, float))
            and hedging_pressure < HEDGING_PRESSURE_THRESHOLD
        ):
            options_gamma_decay = True

    snapshot = {
        "options_available": True,
        "options_activity_count": len(activities),
        "options_elevated_call_count": elevated_calls,
        "options_elevated_volume_count": elevated_volume,
        "options_ambiguous_direction_count": ambiguous_direction,
        "options_high_confirmation_count": high_scores,
        "options_signed_flow_available": signed_flow_available,
        "options_dealer_position_available": dealer_position_available,
        "options_call_demand_anomaly": call_demand_anomaly,
        "options_gamma_amplification": gamma_amplification,
        "options_flow_reversal": options_flow_reversal,
        "options_gamma_decay": options_gamma_decay,
    }
    if isinstance(hedging_pressure, (int, float)):
        snapshot["options_hedging_pressure"] = float(hedging_pressure)

    evidence: list[dict[str, Any]] = []
    if elevated_calls >= 2 and elevated_volume >= 2:
        evidence.append(
            lane_evidence_to_dict(
                NormalizedLaneEvidence(
                    lane=LaneId.OPTIONS,
                    signal=EvidenceSignal.CALL_DEMAND_ANOMALY,
                    strength="MODERATE" if elevated_calls < 4 else "HIGH",
                    available=True,
                    source_ref="whale:options",
                    detail=(
                        f"{elevated_calls} elevated call activities with elevated volume "
                        f"({ambiguous_direction} ambiguous direction labels)"
                    ),
                    provenance_class=EvidenceProvenanceClass.DERIVED,
                    quality_flags=("FLOW_DIRECTION_UNCERTAIN",),
                )
            )
        )

    if signed_flow_available:
        dominant = str(flow_snapshot.get("dominant_direction", ""))
        aggregate = flow_snapshot.get("aggregate", {})
        net_delta = aggregate.get("net_delta_flow", 0) if isinstance(aggregate, dict) else 0
        strength = "MODERATE"
        if isinstance(net_delta, (int, float)) and abs(net_delta) > 5000:
            strength = "HIGH"
        detail = f"Signed flow dominant direction: {dominant}"
        if isinstance(net_delta, (int, float)):
            detail += f"; net_delta_flow={net_delta}"
        evidence.append(
            lane_evidence_to_dict(
                NormalizedLaneEvidence(
                    lane=LaneId.OPTIONS,
                    signal=EvidenceSignal.OPTION_FLOW_DIRECTION,
                    strength=strength,
                    available=True,
                    source_ref="options:signed_flow",
                    detail=detail,
                    provenance_class=EvidenceProvenanceClass.DERIVED,
                )
            )
        )
        if options_flow_reversal:
            evidence.append(
                lane_evidence_to_dict(
                    NormalizedLaneEvidence(
                        lane=LaneId.OPTIONS,
                        signal=EvidenceSignal.OPTIONS_FLOW_REVERSAL,
                        strength="MODERATE",
                        available=True,
                        source_ref="options:signed_flow",
                        detail="Sell-initiated dominant signed flow — exhaustion context",
                        provenance_class=EvidenceProvenanceClass.DERIVED,
                    )
                )
            )

    if dealer_position_available:
        confidence = str(dealer_snapshot.get("confidence", "LOW"))
        flow_note = ""
        if signed_flow_available:
            flow_note = "; signed flow available for context (not used in gamma proxy)"

        evidence.append(
            lane_evidence_to_dict(
                NormalizedLaneEvidence(
                    lane=LaneId.OPTIONS,
                    signal=EvidenceSignal.OPTIONS_DATA_CONFIDENCE,
                    strength="LOW" if confidence == "LOW" else "MODERATE",
                    available=True,
                    source_ref="options:dealer_proxy",
                    detail=(
                        f"Dealer positioning proxy ({dealer_snapshot.get('method', '')}) "
                        f"confidence={confidence}{flow_note}"
                    ),
                    provenance_class=EvidenceProvenanceClass.MODEL_OUTPUT,
                )
            )
        )

        if (
            gamma_regime == "negative_gamma"
            and isinstance(net_gamma, (int, float))
            and abs(net_gamma) >= GAMMA_AMPLIFICATION_THRESHOLD
        ):
            evidence.append(
                lane_evidence_to_dict(
                    NormalizedLaneEvidence(
                        lane=LaneId.OPTIONS,
                        signal=EvidenceSignal.GAMMA_AMPLIFICATION_POTENTIAL,
                        strength="MODERATE" if abs(net_gamma) < 5.0 else "HIGH",
                        available=True,
                        source_ref="options:dealer_proxy",
                        detail=(
                            f"Estimated dealer gamma proxy {net_gamma} "
                            f"(regime={gamma_regime}); not true dealer GEX"
                        ),
                        provenance_class=EvidenceProvenanceClass.MODEL_OUTPUT,
                    )
                )
            )

        if (
            isinstance(hedging_pressure, (int, float))
            and hedging_pressure >= HEDGING_PRESSURE_THRESHOLD
        ):
            evidence.append(
                lane_evidence_to_dict(
                    NormalizedLaneEvidence(
                        lane=LaneId.OPTIONS,
                        signal=EvidenceSignal.ESTIMATED_HEDGING_PRESSURE,
                        strength="MODERATE" if hedging_pressure < 10.0 else "HIGH",
                        available=True,
                        source_ref="options:dealer_proxy",
                        detail=(
                            f"Hedging pressure estimate {hedging_pressure} "
                            f"from OI×gamma proxy; not a trade signal"
                        ),
                        provenance_class=EvidenceProvenanceClass.MODEL_OUTPUT,
                    )
                )
            )

    event_vol_snapshot = options_payload.get("event_vol_snapshot")
    if not isinstance(event_vol_snapshot, dict):
        from ..options.event_vol import build_event_vol_snapshot, load_earnings_event_fixture

        earnings_fixture = load_earnings_event_fixture(str(options_payload.get("symbol", "")))
        if earnings_fixture:
            event_vol_snapshot = build_event_vol_snapshot(
                str(earnings_fixture.get("symbol", "")),
                as_of_time,
                earnings_event=earnings_fixture,
            )
        else:
            event_vol_snapshot = {}

    event_vol_available = bool(event_vol_snapshot.get("available"))
    if event_vol_available:
        snapshot["options_event_vol_available"] = True
        snapshot["options_event_state"] = str(event_vol_snapshot.get("event_state", "NO_EVENT"))
        premium = event_vol_snapshot.get("event_volatility_premium")
        if isinstance(premium, (int, float)) and premium >= 0.02:
            evidence.append(
                lane_evidence_to_dict(
                    NormalizedLaneEvidence(
                        lane=LaneId.OPTIONS,
                        signal=EvidenceSignal.EVENT_VOL_PREMIUM,
                        strength="MODERATE" if premium < 0.05 else "HIGH",
                        available=True,
                        source_ref="options:event_vol",
                        detail=(
                            f"Event vol premium {premium:.4f}% "
                            f"(implied minus forecast move); state={event_vol_snapshot.get('event_state')}"
                        ),
                        provenance_class=EvidenceProvenanceClass.MODEL_OUTPUT,
                    )
                )
            )
        expected_crush = event_vol_snapshot.get("expected_iv_crush")
        pre_iv = event_vol_snapshot.get("pre_iv")
        event_state = str(event_vol_snapshot.get("event_state", "NO_EVENT"))
        crush_risk = (
            isinstance(expected_crush, (int, float))
            and isinstance(pre_iv, (int, float))
            and pre_iv > 0
            and (expected_crush / pre_iv) >= 0.05
            and event_state in {"EVENT_IMMINENT", "EVENT_RESOLUTION"}
        )
        if crush_risk:
            evidence.append(
                lane_evidence_to_dict(
                    NormalizedLaneEvidence(
                        lane=LaneId.OPTIONS,
                        signal=EvidenceSignal.IV_CRUSH_RISK,
                        strength=str(event_vol_snapshot.get("vega_risk", "MODERATE")),
                        available=True,
                        source_ref="options:event_vol",
                        detail=(
                            f"Expected IV crush {expected_crush} "
                            f"during {event_state}; not a trade signal"
                        ),
                        provenance_class=EvidenceProvenanceClass.MODEL_OUTPUT,
                    )
                )
            )
        if event_state == "POST_EVENT_NORMALIZATION":
            evidence.append(
                lane_evidence_to_dict(
                    NormalizedLaneEvidence(
                        lane=LaneId.OPTIONS,
                        signal=EvidenceSignal.POST_EVENT_IV_NORMALIZATION,
                        strength="MODERATE",
                        available=True,
                        source_ref="options:event_vol",
                        detail="Post-event IV normalization window active",
                        provenance_class=EvidenceProvenanceClass.MODEL_OUTPUT,
                    )
                )
            )

    strategy_snapshot = options_payload.get("strategy_snapshot")
    if not isinstance(strategy_snapshot, dict):
        from ..options.strategy import build_strategy_snapshot, load_strategy_optimizer_fixture

        fixture = load_strategy_optimizer_fixture(str(options_payload.get("symbol", "")))
        if fixture:
            scenario = fixture["scenarios"]["bullish_directional"]
            strategy_snapshot = build_strategy_snapshot(
                str(fixture.get("symbol", "")),
                str(fixture.get("as_of_time", as_of_time)),
                executable_edge=scenario["executable_edge"],
                physical_forecast=fixture.get("physical_forecast"),
                chain_rows=fixture.get("chain_rows", []),
                friction=scenario.get("friction"),
            )
        else:
            strategy_snapshot = {}

    if strategy_snapshot.get("available"):
        snapshot["options_strategy_available"] = True
        snapshot["options_strategy_outcome"] = str(strategy_snapshot.get("outcome", "NO_CLEAR_EDGE"))
        if strategy_snapshot.get("status") == "RANKED":
            best = strategy_snapshot.get("best_candidate")
            net_pnl = best.get("net_expected_pnl") if isinstance(best, dict) else None
            if isinstance(net_pnl, (int, float)) and net_pnl > 0:
                evidence.append(
                    lane_evidence_to_dict(
                        NormalizedLaneEvidence(
                            lane=LaneId.OPTIONS,
                            signal=EvidenceSignal.STRATEGY_OPPORTUNITY_RANKED,
                            strength="MODERATE",
                            available=True,
                            source_ref="options:strategy",
                            detail=(
                                f"Ranked template {best.get('template')} "
                                f"net_expected_pnl={net_pnl}; not a trade recommendation"
                            ),
                            provenance_class=EvidenceProvenanceClass.MODEL_OUTPUT,
                        )
                    )
                )
        elif strategy_snapshot.get("outcome") == "NO_CLEAR_EDGE":
            evidence.append(
                lane_evidence_to_dict(
                    NormalizedLaneEvidence(
                        lane=LaneId.OPTIONS,
                        signal=EvidenceSignal.NO_CLEAR_EDGE,
                        strength="LOW",
                        available=True,
                        source_ref="options:strategy",
                        detail=(
                            f"No clear edge: {strategy_snapshot.get('reason', 'EDGE_BELOW_THRESHOLDS')}; "
                            "valid research outcome"
                        ),
                        provenance_class=EvidenceProvenanceClass.MODEL_OUTPUT,
                    )
                )
            )

    execution_snapshot = options_payload.get("execution_snapshot")
    if not isinstance(execution_snapshot, dict):
        from ..options.execution import build_execution_snapshot, load_execution_fixture
        from ..options.strategy import build_strategy_snapshot, load_strategy_optimizer_fixture

        fixture = load_execution_fixture(str(options_payload.get("symbol", "")))
        strategy_fixture = load_strategy_optimizer_fixture(str(options_payload.get("symbol", "")))
        if fixture and strategy_fixture:
            scenario_edge = strategy_fixture["scenarios"]["bullish_directional"]
            strategy_snapshot = build_strategy_snapshot(
                str(fixture.get("symbol", "")),
                str(fixture.get("as_of_time", as_of_time)),
                executable_edge=scenario_edge["executable_edge"],
                physical_forecast=strategy_fixture.get("physical_forecast"),
                chain_rows=fixture.get("chain_rows", []),
                friction=scenario_edge.get("friction"),
            )
            execution_snapshot = build_execution_snapshot(
                str(fixture.get("symbol", "")),
                str(fixture.get("as_of_time", as_of_time)),
                strategy_snapshot=strategy_snapshot,
                chain_rows=fixture.get("chain_rows", []),
                friction=scenario_edge.get("friction"),
                scenario=fixture["scenarios"].get("single_leg_fill"),
            )
        else:
            execution_snapshot = {}

    if execution_snapshot.get("available"):
        snapshot["options_execution_available"] = True
        snapshot["options_execution_status"] = str(execution_snapshot.get("status", "UNAVAILABLE"))
        if execution_snapshot.get("status") == "SIMULATED" and execution_snapshot.get("entry_fills"):
            evidence.append(
                lane_evidence_to_dict(
                    NormalizedLaneEvidence(
                        lane=LaneId.OPTIONS,
                        signal=EvidenceSignal.OPTIONS_EXECUTION_SIMULATED,
                        strength="MODERATE",
                        available=True,
                        source_ref="options:execution",
                        detail=(
                            f"Simulated {execution_snapshot.get('strategy_template')} "
                            f"realized_pnl={execution_snapshot.get('realized_pnl')}; "
                            "research simulation only"
                        ),
                        provenance_class=EvidenceProvenanceClass.MODEL_OUTPUT,
                    )
                )
            )
        lifecycle_events = execution_snapshot.get("lifecycle_events", [])
        assignment_events = [
            event
            for event in lifecycle_events
            if isinstance(event, dict) and event.get("event_type") == "ASSIGNMENT"
        ]
        if assignment_events:
            evidence.append(
                lane_evidence_to_dict(
                    NormalizedLaneEvidence(
                        lane=LaneId.OPTIONS,
                        signal=EvidenceSignal.ASSIGNMENT_RISK,
                        strength="HIGH",
                        available=True,
                        source_ref="options:execution",
                        detail=(
                            f"{len(assignment_events)} assignment event(s) in simulation; "
                            "not a live assignment claim"
                        ),
                        provenance_class=EvidenceProvenanceClass.MODEL_OUTPUT,
                    )
                )
            )

    if high_scores >= 2:
        evidence.append(
            lane_evidence_to_dict(
                NormalizedLaneEvidence(
                    lane=LaneId.OPTIONS,
                    signal=EvidenceSignal.OPTIONS_DATA_CONFIDENCE,
                    strength="MODERATE",
                    available=True,
                    source_ref="whale:options",
                    detail=(
                        f"{high_scores} activities with elevated unusual-activity score; "
                        "not a directional or pricing edge claim"
                    ),
                    provenance_class=EvidenceProvenanceClass.DERIVED,
                )
            )
        )

    return snapshot, evidence


def build_cross_lane_snapshot_from_futures(
    futures_payload: dict[str, Any] | None,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """Derive cross-lane snapshot + normalized evidence from futures workspace payload.

    Uses depth-derived signals and contract context only — does not infer COT,
    curve carry, or liquidation risk when data is unavailable (fail closed).
    """
    if not futures_payload or not futures_payload.get("available"):
        return None, []

    imbalance_signal = str(futures_payload.get("imbalance_signal", "neutral"))
    imbalance_ratio = futures_payload.get("imbalance_ratio")
    book_pressure = str(
        futures_payload.get("book_pressure_side", futures_payload.get("latest_book_pressure_side", "neutral"))
    )
    contract_month = futures_payload.get("contract_month", "")
    depth_available = futures_payload.get("snapshot_count", 0) > 0

    snapshot = {
        "futures_available": True,
        "futures_contract_month": contract_month,
        "futures_depth_available": depth_available,
        "futures_imbalance_signal": imbalance_signal,
        "futures_imbalance_ratio": imbalance_ratio,
        "futures_book_pressure_side": book_pressure,
        "futures_curve_available": bool(futures_payload.get("futures_curve_available")),
        "futures_positioning_available": False,
        "futures_carry_available": bool(futures_payload.get("futures_carry_available")),
        "futures_data_kind": "depth_derived",
    }

    evidence: list[dict[str, Any]] = []
    if depth_available and book_pressure == "bid_heavy":
        evidence.append(
            lane_evidence_to_dict(
                NormalizedLaneEvidence(
                    lane=LaneId.ORDER_FLOW,
                    signal=EvidenceSignal.BOOK_IMBALANCE_BID,
                    strength="MODERATE",
                    available=True,
                    source_ref="whale:futures_depth",
                    detail=f"Resting book bid-heavy (ratio={imbalance_ratio}) — raw pressure, not domain direction",
                    provenance_class=EvidenceProvenanceClass.DERIVED,
                    quality_flags=("DEPTH_DERIVED_NOT_COT",),
                )
            )
        )
    elif depth_available and book_pressure == "ask_heavy":
        evidence.append(
            lane_evidence_to_dict(
                NormalizedLaneEvidence(
                    lane=LaneId.ORDER_FLOW,
                    signal=EvidenceSignal.BOOK_IMBALANCE_ASK,
                    strength="MODERATE",
                    available=True,
                    source_ref="whale:futures_depth",
                    detail=f"Resting book ask-heavy (ratio={imbalance_ratio}) — raw pressure, not domain direction",
                    provenance_class=EvidenceProvenanceClass.DERIVED,
                    quality_flags=("DEPTH_DERIVED_NOT_COT",),
                )
            )
        )

    if depth_available:
        evidence.append(
            lane_evidence_to_dict(
                NormalizedLaneEvidence(
                    lane=LaneId.FUTURES,
                    signal=EvidenceSignal.FUTURES_DATA_CONFIDENCE,
                    strength="LOW",
                    available=True,
                    source_ref="whale:futures_depth",
                    detail=(
                        "Depth fixture only (data_kind=depth_derived); "
                        "legacy whale family futures_positioning is not COT; "
                        "curve, margin, and carry not available"
                    ),
                    provenance_class=EvidenceProvenanceClass.DERIVED,
                )
            )
        )

    curve = futures_payload.get("curve_snapshot")
    carry_obs = futures_payload.get("carry_observation")
    if isinstance(carry_obs, dict) and carry_obs.get("available"):
        snapshot["futures_carry_available"] = True
        annualized_carry = carry_obs.get("annualized_carry")
        if isinstance(annualized_carry, (int, float)):
            if annualized_carry > 0:
                strength = "MODERATE" if annualized_carry > 0.02 else "LOW"
                evidence.append(
                    lane_evidence_to_dict(
                        NormalizedLaneEvidence(
                            lane=LaneId.FUTURES,
                            signal=EvidenceSignal.FUTURES_CARRY_POSITIVE,
                            strength=strength,
                            available=True,
                            source_ref="futures:carry_engine",
                            detail=(
                                f"Calendar implied carry positive ({annualized_carry:.4f} annualized); "
                                "fair-value context, not directional forecast"
                            ),
                            provenance_class=EvidenceProvenanceClass.DERIVED,
                        )
                    )
                )
            elif annualized_carry < 0:
                strength = "MODERATE" if annualized_carry < -0.02 else "LOW"
                evidence.append(
                    lane_evidence_to_dict(
                        NormalizedLaneEvidence(
                            lane=LaneId.FUTURES,
                            signal=EvidenceSignal.FUTURES_CARRY_NEGATIVE,
                            strength=strength,
                            available=True,
                            source_ref="futures:carry_engine",
                            detail=(
                                f"Calendar implied carry negative ({annualized_carry:.4f} annualized); "
                                "fair-value context, not directional forecast"
                            ),
                            provenance_class=EvidenceProvenanceClass.DERIVED,
                        )
                    )
                )

    if isinstance(curve, dict) and curve.get("available"):
        regime = str(curve.get("regime", "flat"))
        if regime == "contango":
            evidence.append(
                lane_evidence_to_dict(
                    NormalizedLaneEvidence(
                        lane=LaneId.FUTURES,
                        signal=EvidenceSignal.FUTURES_CURVE_CONTANGO,
                        strength="MODERATE",
                        available=True,
                        source_ref="futures:curve_engine",
                        detail="Term structure in contango (back > front)",
                        provenance_class=EvidenceProvenanceClass.DERIVED,
                    )
                )
            )
        elif regime == "backwardation":
            evidence.append(
                lane_evidence_to_dict(
                    NormalizedLaneEvidence(
                        lane=LaneId.FUTURES,
                        signal=EvidenceSignal.FUTURES_CURVE_BACKWARDATION,
                        strength="MODERATE",
                        available=True,
                        source_ref="futures:curve_engine",
                        detail="Term structure in backwardation (front > back)",
                        provenance_class=EvidenceProvenanceClass.DERIVED,
                    )
                )
            )
        snapshot["futures_curve_regime"] = regime

    positioning = futures_payload.get("positioning_snapshot")
    if bool(futures_payload.get("futures_positioning_available")) and isinstance(positioning, dict):
        snapshot["futures_positioning_available"] = True
        net_percentile = positioning.get("net_percentile")
        crowding = str(futures_payload.get("crowding_regime", positioning.get("crowding_regime", "NEUTRAL")))
        snapshot["futures_crowding_regime"] = crowding
        snapshot["futures_cot_net"] = positioning.get("net")
        snapshot["futures_cot_net_percentile"] = net_percentile
        participant = positioning.get("participant_category", "managed_money")
        if crowding == "CROWDED_LONG":
            strength = "HIGH" if isinstance(net_percentile, (int, float)) and net_percentile >= 0.9 else "MODERATE"
            evidence.append(
                lane_evidence_to_dict(
                    NormalizedLaneEvidence(
                        lane=LaneId.FUTURES,
                        signal=EvidenceSignal.FUTURES_POSITIONING_CROWDED_LONG,
                        strength=strength,
                        available=True,
                        source_ref="cot.fixture.futures_positioning",
                        detail=(
                            f"COT {participant} crowded long "
                            f"(net percentile={net_percentile:.2f}); crowding context, not directional forecast"
                        ),
                        provenance_class=EvidenceProvenanceClass.DERIVED,
                    )
                )
            )
        elif crowding == "CROWDED_SHORT":
            strength = "HIGH" if isinstance(net_percentile, (int, float)) and net_percentile <= 0.1 else "MODERATE"
            evidence.append(
                lane_evidence_to_dict(
                    NormalizedLaneEvidence(
                        lane=LaneId.FUTURES,
                        signal=EvidenceSignal.FUTURES_POSITIONING_CROWDED_SHORT,
                        strength=strength,
                        available=True,
                        source_ref="cot.fixture.futures_positioning",
                        detail=(
                            f"COT {participant} crowded short "
                            f"(net percentile={net_percentile:.2f}); crowding context, not directional forecast"
                        ),
                        provenance_class=EvidenceProvenanceClass.DERIVED,
                    )
                )
            )

    if bool(futures_payload.get("futures_baselines_available")):
        snapshot["futures_baselines_available"] = True
        trend_regime = str(futures_payload.get("trend_regime", "NEUTRAL"))
        snapshot["futures_trend_regime"] = trend_regime
        trend_snapshot = futures_payload.get("trend_baseline_snapshot")
        trend_3m = None
        if isinstance(trend_snapshot, dict):
            trend_3m = trend_snapshot.get("trend_3m")
            snapshot["futures_trend_3m"] = trend_3m

        if trend_regime == "TREND_UP":
            strength = "MODERATE"
            if isinstance(trend_3m, (int, float)) and trend_3m >= 1.0:
                strength = "HIGH"
            evidence.append(
                lane_evidence_to_dict(
                    NormalizedLaneEvidence(
                        lane=LaneId.FUTURES,
                        signal=EvidenceSignal.FUTURES_TREND_UP,
                        strength=strength,
                        available=True,
                        source_ref="bars.fixture.futures_settlement",
                        detail=(
                            f"Vol-scaled 3m trend elevated (trend_3m={trend_3m}); "
                            "baseline context, not directional forecast"
                        ),
                        provenance_class=EvidenceProvenanceClass.DERIVED,
                    )
                )
            )
        elif trend_regime == "TREND_DOWN":
            strength = "MODERATE"
            if isinstance(trend_3m, (int, float)) and trend_3m <= -1.0:
                strength = "HIGH"
            evidence.append(
                lane_evidence_to_dict(
                    NormalizedLaneEvidence(
                        lane=LaneId.FUTURES,
                        signal=EvidenceSignal.FUTURES_TREND_DOWN,
                        strength=strength,
                        available=True,
                        source_ref="bars.fixture.futures_settlement",
                        detail=(
                            f"Vol-scaled 3m trend depressed (trend_3m={trend_3m}); "
                            "baseline context, not directional forecast"
                        ),
                        provenance_class=EvidenceProvenanceClass.DERIVED,
                    )
                )
            )

    return snapshot, evidence


def build_cross_lane_snapshot_from_distribution(
    distribution_payload: dict[str, Any] | None,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """Publish physical P distribution MODEL_OUTPUT evidence for cross-lane consumers."""
    if not distribution_payload or not distribution_payload.get("available"):
        return None, []

    forecast = distribution_payload.get("forecast")
    if not isinstance(forecast, dict):
        return None, []

    vol = forecast.get("vol_forecast_annualized")
    horizons = forecast.get("horizons", [])
    snapshot = {
        "distribution_available": True,
        "distribution_vol_forecast": vol,
        "distribution_model": forecast.get("model"),
        "distribution_event_window_active": forecast.get("event_window_active", False),
    }
    evidence: list[dict[str, Any]] = []
    rv_threshold = 0.15
    if isinstance(vol, (int, float)) and vol >= rv_threshold:
        evidence.append(
            lane_evidence_to_dict(
                NormalizedLaneEvidence(
                    lane=LaneId.CATALYST,
                    signal=EvidenceSignal.FORECAST_RV_ELEVATED,
                    strength="MODERATE" if vol < 0.35 else "HIGH",
                    available=True,
                    source_ref="platform:distribution_forecast",
                    detail=f"Annualized vol forecast {vol:.4f} above baseline threshold",
                    provenance_class=EvidenceProvenanceClass.MODEL_OUTPUT,
                )
            )
        )
    if isinstance(horizons, list) and horizons:
        latest = horizons[-1]
        if isinstance(latest, dict):
            upside = latest.get("upside_tail_probability")
            downside = latest.get("downside_tail_probability")
            if isinstance(upside, (int, float)) and upside >= 0.05:
                evidence.append(
                    lane_evidence_to_dict(
                        NormalizedLaneEvidence(
                            lane=LaneId.CATALYST,
                            signal=EvidenceSignal.UPSIDE_TAIL_PROBABILITY_PHYSICAL,
                            strength="MODERATE",
                            available=True,
                            source_ref="platform:distribution_forecast",
                            detail=f"Physical upside tail probability {upside:.4f}",
                            provenance_class=EvidenceProvenanceClass.MODEL_OUTPUT,
                        )
                    )
                )
            if isinstance(downside, (int, float)) and downside >= 0.05:
                evidence.append(
                    lane_evidence_to_dict(
                        NormalizedLaneEvidence(
                            lane=LaneId.CATALYST,
                            signal=EvidenceSignal.DOWNSIDE_TAIL_PROBABILITY_PHYSICAL,
                            strength="MODERATE",
                            available=True,
                            source_ref="platform:distribution_forecast",
                            detail=f"Physical downside tail probability {downside:.4f}",
                            provenance_class=EvidenceProvenanceClass.MODEL_OUTPUT,
                        )
                    )
                )
    return snapshot, evidence


def build_cross_lane_snapshot_from_squeeze(
    squeeze_detail: dict[str, Any] | None,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """Publish squeeze MODEL_OUTPUT evidence for Options and cross-lane consumers."""
    if not squeeze_detail or not isinstance(squeeze_detail, dict):
        return None, []

    causal = squeeze_detail.get("causal_intelligence")
    if not isinstance(causal, dict):
        causal = squeeze_detail

    state = causal.get("state") or squeeze_detail.get("ignition_state")
    if not state:
        return None, []

    ignition_strength = causal.get("ignition_strength") or causal.get("overall_confidence") or "LOW"
    state_upper = str(state).upper()
    strength = "LOW"
    if state_upper in {"IGNITION_WATCH", "VULNERABLE"}:
        strength = "MODERATE"
    elif state_upper in {"ACTIVE_SQUEEZE", "LIVE_CONFIRMATION"}:
        strength = "HIGH"

    snapshot = {
        "squeeze_available": True,
        "squeeze_state": str(state),
        "squeeze_ignition_strength": str(ignition_strength),
        "squeeze_structural_vulnerability": state_upper in {
            "VULNERABLE",
            "IGNITION_WATCH",
            "ACTIVE_SQUEEZE",
        },
    }
    remaining_fuel = causal.get("remaining_fuel")
    exhaustion_risk = causal.get("exhaustion_risk")
    if isinstance(remaining_fuel, (int, float)):
        snapshot["remaining_fuel"] = float(remaining_fuel)
    if isinstance(exhaustion_risk, (int, float)):
        snapshot["exhaustion_risk"] = float(exhaustion_risk)

    evidence: list[dict[str, Any]] = [
        lane_evidence_to_dict(
            NormalizedLaneEvidence(
                lane=LaneId.SHORT_SQUEEZE,
                signal=EvidenceSignal.SQUEEZE_STATE,
                strength=strength,
                available=True,
                source_ref="squeeze:causal_intelligence",
                detail=f"Causal state {state}",
                provenance_class=EvidenceProvenanceClass.MODEL_OUTPUT,
            )
        ),
        lane_evidence_to_dict(
            NormalizedLaneEvidence(
                lane=LaneId.SHORT_SQUEEZE,
                signal=EvidenceSignal.SQUEEZE_IGNITION_STRENGTH,
                strength=str(ignition_strength).upper() if ignition_strength else "LOW",
                available=True,
                source_ref="squeeze:causal_intelligence",
                detail=f"Ignition strength context {ignition_strength}",
                provenance_class=EvidenceProvenanceClass.MODEL_OUTPUT,
            )
        ),
    ]
    if isinstance(remaining_fuel, (int, float)) and remaining_fuel >= 40:
        evidence.append(
            lane_evidence_to_dict(
                NormalizedLaneEvidence(
                    lane=LaneId.SHORT_SQUEEZE,
                    signal=EvidenceSignal.REMAINING_SQUEEZE_FUEL,
                    strength="MODERATE" if remaining_fuel < 65 else "HIGH",
                    available=True,
                    source_ref="squeeze:causal_intelligence",
                    detail=f"Remaining squeeze fuel estimate {remaining_fuel:.1f} (structural proxy)",
                    provenance_class=EvidenceProvenanceClass.MODEL_OUTPUT,
                )
            )
        )
    if isinstance(exhaustion_risk, (int, float)) and exhaustion_risk >= 50:
        evidence.append(
            lane_evidence_to_dict(
                NormalizedLaneEvidence(
                    lane=LaneId.SHORT_SQUEEZE,
                    signal=EvidenceSignal.EXHAUSTION_RISK,
                    strength="MODERATE" if exhaustion_risk < 70 else "HIGH",
                    available=True,
                    source_ref="squeeze:causal_intelligence",
                    detail=f"Exhaustion risk estimate {exhaustion_risk:.1f} (order-flow proxy)",
                    provenance_class=EvidenceProvenanceClass.MODEL_OUTPUT,
                )
            )
        )
    return snapshot, evidence


def build_cross_lane_evidence_from_risk_neutral(
    risk_neutral_payload: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Publish IMPLIED_UPSIDE_TAIL evidence when O3 Q inference is available."""
    if not risk_neutral_payload or not risk_neutral_payload.get("available"):
        return []
    horizons = risk_neutral_payload.get("horizons", [])
    if not isinstance(horizons, list) or not horizons:
        return []
    latest = horizons[-1]
    if not isinstance(latest, dict):
        return []
    upside = latest.get("upside_tail_probability")
    if not isinstance(upside, (int, float)) or upside < 0.03:
        return []
    strength = "MODERATE" if upside < 0.08 else "HIGH"
    return [
        lane_evidence_to_dict(
            NormalizedLaneEvidence(
                lane=LaneId.OPTIONS,
                signal=EvidenceSignal.IMPLIED_UPSIDE_TAIL_PROBABILITY,
                strength=strength,
                available=True,
                source_ref="options:risk_neutral_q",
                detail=f"Risk-neutral upside tail probability {upside:.4f}",
                provenance_class=EvidenceProvenanceClass.MODEL_OUTPUT,
            )
        )
    ]


def merge_cross_lane_snapshots(
    *snapshots: dict[str, Any] | None,
) -> dict[str, Any]:
    """Merge partial lane snapshots into one cross_lane input dict."""
    merged: dict[str, Any] = {
        "order_flow_available": False,
        "options_available": False,
        "futures_available": False,
        "order_book_available": False,
        "distribution_available": False,
        "squeeze_available": False,
        "attention_available": False,
    }
    for snapshot in snapshots:
        if not snapshot:
            continue
        merged.update(snapshot)
    return merged


def merge_cross_lane_evidence(*evidence_lists: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Concatenate evidence lists from multiple lane adapters."""
    merged: list[dict[str, Any]] = []
    for items in evidence_lists:
        merged.extend(items)
    return merged
