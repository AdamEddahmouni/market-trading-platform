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
    return snapshot, evidence


def build_cross_lane_snapshot_from_options(
    options_payload: dict[str, Any] | None,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """Derive cross-lane snapshot + normalized evidence from options workspace payload.

    Uses only admitted unusual-activity context — does not infer signed flow or dealer
    gamma when data is unavailable (fail closed per O-15, O-17).
    """
    if not options_payload or not options_payload.get("available"):
        return None, []

    activities = options_payload.get("activities") or []
    if not isinstance(activities, list) or not activities:
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

    from ..options.flow import build_flow_snapshot

    flow_snapshot = options_payload.get("signed_flow_snapshot")
    if not isinstance(flow_snapshot, dict):
        flow_snapshot = build_flow_snapshot(activities, as_of_time=str(activities[0].get("event_time", "")) if activities else "")

    signed_flow_available = bool(flow_snapshot.get("signed_flow_available"))

    snapshot = {
        "options_available": True,
        "options_activity_count": len(activities),
        "options_elevated_call_count": elevated_calls,
        "options_elevated_volume_count": elevated_volume,
        "options_ambiguous_direction_count": ambiguous_direction,
        "options_high_confirmation_count": high_scores,
        "options_signed_flow_available": signed_flow_available,
        "options_dealer_position_available": False,
    }

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
