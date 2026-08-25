"""Deterministic semantic event detector orchestration (BUILD 09)."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import math
from typing import Any

from ..contracts import (
    ComponentLineage,
    ContractKind,
    ContractReference,
    DetectionSeverity,
    DetectionV1,
    EventV1,
    QualityState,
    QualitySummary,
    SemanticEventType,
    SignalV1,
)
from ..quality import DecisionAction
from .identity import derive_detection_id
from .models import (
    DetectionEngineResult,
    DetectionFrame,
    DetectorStateSnapshot,
    DetectorSupport,
    DetectorSupportStatus,
)
from .policy import DetectionPolicyV1


@dataclass(slots=True)
class _ScopeState:
    last_material_nss: SignalV1 | None = None
    last_spread: SignalV1 | None = None
    liquidity_stressed: bool = False
    last_short_interest: EventV1 | None = None
    last_regime_key: str | None = None


def _scope_key(frame: DetectionFrame) -> str:
    instruments = ",".join(frame.snapshot.scope.instrument_ids)
    return f"{instruments}|{frame.snapshot.scope.context_id or ''}"


def _ref(kind: ContractKind, record_id: str) -> ContractReference:
    return ContractReference(kind=kind.value, id=record_id)


def _quality_summary(frame: DetectionFrame, sources: tuple[SignalV1 | EventV1, ...]) -> QualitySummary:
    states = [frame.snapshot.quality.state, frame.quality_decision.quality_state]
    states.extend(source.quality.state for source in sources)
    flags = set(frame.snapshot.quality.flags)
    for source in sources:
        flags.update(source.quality.flags)
    if QualityState.INVALID in states:
        state = QualityState.INVALID
    elif QualityState.DEGRADED in states or QualityState.UNKNOWN in states:
        state = QualityState.DEGRADED
    else:
        state = QualityState.GOOD
    return QualitySummary(state=state, flags=tuple(sorted(flags)))


def _order_flow_severity(magnitude: float) -> DetectionSeverity:
    if magnitude >= 1.5:
        return DetectionSeverity.CRITICAL
    if magnitude >= 1.0:
        return DetectionSeverity.HIGH
    if magnitude >= 0.6:
        return DetectionSeverity.MEDIUM
    return DetectionSeverity.LOW


def _liquidity_severity(spread_bps: float, entry_bps: float) -> DetectionSeverity:
    ratio = spread_bps / entry_bps
    if ratio >= 4.0:
        return DetectionSeverity.CRITICAL
    if ratio >= 2.0:
        return DetectionSeverity.HIGH
    if ratio >= 1.5:
        return DetectionSeverity.MEDIUM
    return DetectionSeverity.LOW


def _change_severity(relative_change: float) -> DetectionSeverity:
    magnitude = abs(relative_change)
    if magnitude >= 1.0:
        return DetectionSeverity.CRITICAL
    if magnitude >= 0.5:
        return DetectionSeverity.HIGH
    if magnitude >= 0.25:
        return DetectionSeverity.MEDIUM
    return DetectionSeverity.LOW


class EventDetectorEngine:
    """Owns bounded detector-visible state; detectors never query repositories."""

    def __init__(self, policy: DetectionPolicyV1 | None = None) -> None:
        self.policy = policy or DetectionPolicyV1()
        self._states: OrderedDict[str, _ScopeState] = OrderedDict()

    def reset(self) -> None:
        self._states.clear()

    def state_snapshot(self) -> DetectorStateSnapshot:
        return DetectorStateSnapshot(
            scope_count=len(self._states),
            scope_keys=tuple(self._states.keys()),
        )

    def support_matrix(self) -> tuple[DetectorSupport, ...]:
        return (
            DetectorSupport(
                SemanticEventType.ORDER_FLOW_REVERSAL,
                "net_signed_share@300s from cvd-calculator v1",
                DetectorSupportStatus.IMPLEMENTED,
                "edge-triggered NSS reversal detector",
            ),
            DetectorSupport(
                SemanticEventType.UNUSUAL_OPTIONS_ACTIVITY,
                "canonical option volume/OI/IV signals",
                DetectorSupportStatus.INACTIVE_INPUT_UNAVAILABLE,
                "inactive",
                "standard SnapshotV1/SignalV1 path has no canonical option-chain signals",
            ),
            DetectorSupport(
                SemanticEventType.BORROW_CHANGE,
                "sequential canonical SHORT_INTEREST EventV1 observations",
                DetectorSupportStatus.IMPLEMENTED,
                "relative short-interest change detector",
            ),
            DetectorSupport(
                SemanticEventType.LIQUIDITY_EVENT,
                "spread_bps from spread-calculator v1",
                DetectorSupportStatus.IMPLEMENTED,
                "spread stress hysteresis detector",
            ),
            DetectorSupport(
                SemanticEventType.NEWS_EVENT,
                "canonical NEWS EventV1 normalization",
                DetectorSupportStatus.INACTIVE_INPUT_UNAVAILABLE,
                "inactive",
                "no canonical news normalizer or NEWS snapshot lane exists",
            ),
            DetectorSupport(
                SemanticEventType.REGIME_SHIFT,
                "caller-supplied RegimeContext",
                DetectorSupportStatus.IMPLEMENTED_WITH_EXTERNAL_CONTEXT,
                "explicit regime-key transition detector",
                "BUILD 09 does not produce regime keys",
            ),
        )

    def detect(self, frame: DetectionFrame) -> DetectionEngineResult:
        if frame.snapshot.quality.state == QualityState.INVALID:
            return DetectionEngineResult((), ("FRAME_SNAPSHOT_QUALITY_INVALID",))
        action = frame.quality_decision.action
        if action == DecisionAction.FAIL_CLOSED:
            return DetectionEngineResult((), ("FRAME_QUALITY_FAIL_CLOSED",))
        if action == DecisionAction.ABSTAIN:
            return DetectionEngineResult((), ("FRAME_QUALITY_ABSTAIN",))

        key = _scope_key(frame)
        state = self._state_for(key)
        detections: list[DetectionV1] = []
        diagnostics: list[str] = []
        self._detect_order_flow(frame, state, detections, diagnostics)
        self._detect_liquidity(frame, state, detections, diagnostics)
        self._detect_short_interest(frame, state, detections, diagnostics)
        self._detect_regime(frame, state, detections)
        ordered = tuple(
            sorted(
                detections,
                key=lambda row: (
                    row.semantic_event_type.value,
                    row.scope.instrument_ids,
                    row.detection_id,
                ),
            )
        )
        return DetectionEngineResult(ordered, tuple(sorted(set(diagnostics))))

    def _state_for(self, key: str) -> _ScopeState:
        state = self._states.get(key)
        if state is not None:
            return state
        if len(self._states) >= self.policy.max_scopes:
            self._states.popitem(last=False)
        state = _ScopeState()
        self._states[key] = state
        return state

    def _select_signal(
        self,
        frame: DetectionFrame,
        *,
        signal_type: str,
        window_ns: int | None,
        calculator_id: str,
    ) -> tuple[SignalV1 | None, str | None]:
        matches = []
        for row in frame.signals:
            if row.signal_type != signal_type:
                continue
            actual_window = row.calculation_window.duration_ns if row.calculation_window is not None else None
            if actual_window != window_ns:
                continue
            if row.calculation_lineage.get("calculator_id") != calculator_id:
                continue
            if row.calculation_lineage.get("calculator_version") != "1":
                continue
            matches.append(row)
        if not matches:
            return None, "MISSING_REQUIRED_SIGNAL"
        if len(matches) != 1:
            return None, "AMBIGUOUS_REQUIRED_SIGNAL"
        selected = matches[0]
        if signal_type == "net_signed_share" and not -1.0 <= selected.value <= 1.0:
            return None, "INVALID_SIGNAL_VALUE"
        if signal_type == "spread_bps" and selected.value < 0.0:
            return None, "INVALID_SIGNAL_VALUE"
        if selected.quality.state == QualityState.INVALID:
            return None, "INPUT_QUALITY_REJECTED"
        if selected.quality.state in {QualityState.DEGRADED, QualityState.UNKNOWN} and not self.policy.allow_degraded_inputs:
            return None, "INPUT_QUALITY_REJECTED"
        return selected, None

    def _build_detection(
        self,
        frame: DetectionFrame,
        *,
        event_type: SemanticEventType,
        detector_id: str,
        source_signals: tuple[SignalV1, ...] = (),
        source_events: tuple[EventV1, ...] = (),
        severity: DetectionSeverity,
        reason_code: str,
        identity_context: dict[str, str],
        metadata: dict[str, Any],
    ) -> DetectionV1:
        signal_refs = tuple(_ref(ContractKind.SIGNAL, row.signal_id) for row in source_signals)
        event_refs = tuple(_ref(ContractKind.EVENT, row.event_id) for row in source_events)
        detection_id = derive_detection_id(
            semantic_event_type=event_type,
            source_snapshot_id=frame.snapshot.snapshot_id,
            source_signal_refs=signal_refs,
            source_event_refs=event_refs,
            detector_id=detector_id,
            detector_version="1",
            policy_id=self.policy.policy_id,
            policy_version=self.policy.policy_version,
            identity_context=identity_context,
        )
        return DetectionV1(
            detection_id=detection_id,
            schema_version="1",
            semantic_event_type=event_type,
            detected_at_ns=frame.snapshot.decision_time_ns,
            source_snapshot_ref=_ref(ContractKind.SNAPSHOT, frame.snapshot.snapshot_id),
            source_signal_refs=signal_refs,
            source_event_refs=event_refs,
            detector_lineage=ComponentLineage(component_id=detector_id, component_version="1"),
            scope=frame.snapshot.scope,
            severity=severity,
            reason_codes=(reason_code,),
            quality=_quality_summary(frame, (*source_signals, *source_events)),
            identity_context=identity_context,
            metadata=metadata,
        )

    def _detect_order_flow(
        self,
        frame: DetectionFrame,
        state: _ScopeState,
        detections: list[DetectionV1],
        diagnostics: list[str],
    ) -> None:
        current, diagnostic = self._select_signal(
            frame,
            signal_type="net_signed_share",
            window_ns=self.policy.order_flow_window_ns,
            calculator_id="cvd-calculator",
        )
        if current is None:
            diagnostics.append(f"ORDER_FLOW_REVERSAL:{diagnostic}")
            return
        threshold = self.policy.order_flow_threshold
        if -threshold < current.value < threshold:
            return
        previous = state.last_material_nss
        state.last_material_nss = current
        if previous is None:
            return
        bullish = previous.value <= -threshold and current.value >= threshold
        bearish = previous.value >= threshold and current.value <= -threshold
        if not bullish and not bearish:
            return
        transition = "NEGATIVE_TO_POSITIVE" if bullish else "POSITIVE_TO_NEGATIVE"
        reason = "NSS_NEGATIVE_TO_POSITIVE" if bullish else "NSS_POSITIVE_TO_NEGATIVE"
        magnitude = abs(current.value - previous.value)
        detections.append(
            self._build_detection(
                frame,
                event_type=SemanticEventType.ORDER_FLOW_REVERSAL,
                detector_id="order-flow-reversal",
                source_signals=(previous, current),
                severity=_order_flow_severity(magnitude),
                reason_code=reason,
                identity_context={"transition": transition},
                metadata={
                    "previous_nss": previous.value,
                    "current_nss": current.value,
                    "reversal_magnitude": magnitude,
                    "threshold": threshold,
                    "severity_semantics": "deterministic_magnitude_not_probability",
                },
            )
        )

    def _detect_liquidity(
        self,
        frame: DetectionFrame,
        state: _ScopeState,
        detections: list[DetectionV1],
        diagnostics: list[str],
    ) -> None:
        current, diagnostic = self._select_signal(
            frame,
            signal_type="spread_bps",
            window_ns=None,
            calculator_id="spread-calculator",
        )
        if current is None:
            diagnostics.append(f"LIQUIDITY_EVENT:{diagnostic}")
            return
        previous = state.last_spread
        state.last_spread = current
        if state.liquidity_stressed:
            if current.value <= self.policy.liquidity_exit_bps:
                state.liquidity_stressed = False
            return
        if previous is None:
            return
        if previous.value < self.policy.liquidity_entry_bps <= current.value:
            state.liquidity_stressed = True
            detections.append(
                self._build_detection(
                    frame,
                    event_type=SemanticEventType.LIQUIDITY_EVENT,
                    detector_id="liquidity-spread-stress",
                    source_signals=(previous, current),
                    severity=_liquidity_severity(current.value, self.policy.liquidity_entry_bps),
                    reason_code="SPREAD_ENTERED_STRESS",
                    identity_context={"transition": "NORMAL_TO_STRESSED"},
                    metadata={
                        "previous_spread_bps": previous.value,
                        "current_spread_bps": current.value,
                        "entry_threshold_bps": self.policy.liquidity_entry_bps,
                        "exit_threshold_bps": self.policy.liquidity_exit_bps,
                        "severity_semantics": "deterministic_magnitude_not_probability",
                    },
                )
            )

    def _detect_short_interest(
        self,
        frame: DetectionFrame,
        state: _ScopeState,
        detections: list[DetectionV1],
        diagnostics: list[str],
    ) -> None:
        candidates = [row for row in frame.events if row.event_type == "SHORT_INTEREST"]
        if not candidates:
            diagnostics.append("BORROW_CHANGE:MISSING_SHORT_INTEREST_EVENT")
            return
        current = max(candidates, key=lambda row: (row.available_time_ns, row.event_time_ns, row.event_id))
        if state.last_short_interest is not None and current.event_id == state.last_short_interest.event_id:
            return
        if current.quality.state == QualityState.INVALID or (
            current.quality.state in {QualityState.DEGRADED, QualityState.UNKNOWN}
            and not self.policy.allow_degraded_inputs
        ):
            diagnostics.append("BORROW_CHANGE:INPUT_QUALITY_REJECTED")
            return
        current_value = current.payload.get("current_short_position_quantity")
        if (
            isinstance(current_value, bool)
            or not isinstance(current_value, (int, float))
            or not math.isfinite(float(current_value))
            or current_value < 0
        ):
            diagnostics.append("BORROW_CHANGE:INVALID_SHORT_INTEREST_VALUE")
            return
        previous = state.last_short_interest
        if previous is None:
            state.last_short_interest = current
            return
        previous_value = previous.payload.get("current_short_position_quantity")
        if (
            isinstance(previous_value, bool)
            or not isinstance(previous_value, (int, float))
            or not math.isfinite(float(previous_value))
            or previous_value <= 0
        ):
            diagnostics.append("BORROW_CHANGE:INVALID_SHORT_INTEREST_VALUE")
            state.last_short_interest = current
            return
        state.last_short_interest = current
        relative_change = (float(current_value) - float(previous_value)) / float(previous_value)
        if abs(relative_change) < self.policy.short_interest_relative_change_threshold:
            return
        reason = "SHORT_INTEREST_INCREASE" if relative_change > 0 else "SHORT_INTEREST_DECREASE"
        detections.append(
            self._build_detection(
                frame,
                event_type=SemanticEventType.BORROW_CHANGE,
                detector_id="short-interest-change",
                source_events=(previous, current),
                severity=_change_severity(relative_change),
                reason_code=reason,
                identity_context={"direction": "INCREASE" if relative_change > 0 else "DECREASE"},
                metadata={
                    "previous_short_interest": float(previous_value),
                    "current_short_interest": float(current_value),
                    "relative_change": relative_change,
                    "relative_threshold": self.policy.short_interest_relative_change_threshold,
                    "severity_semantics": "deterministic_magnitude_not_probability",
                },
            )
        )

    def _detect_regime(
        self,
        frame: DetectionFrame,
        state: _ScopeState,
        detections: list[DetectionV1],
    ) -> None:
        context = frame.regime_context
        if context is None:
            return
        repeated = state.last_regime_key == context.current_regime_key
        state.last_regime_key = context.current_regime_key
        if repeated or context.previous_regime_key == context.current_regime_key:
            return
        detections.append(
            self._build_detection(
                frame,
                event_type=SemanticEventType.REGIME_SHIFT,
                detector_id="external-regime-transition",
                severity=DetectionSeverity.HIGH,
                reason_code="REGIME_KEY_CHANGED",
                identity_context={
                    "previous_regime_key": context.previous_regime_key,
                    "current_regime_key": context.current_regime_key,
                    "source_context_version": context.source_context_version,
                },
                metadata={
                    "previous_regime_key": context.previous_regime_key,
                    "current_regime_key": context.current_regime_key,
                    "source_context_version": context.source_context_version,
                    "regime_generated_by_build_09": False,
                },
            )
        )


__all__ = ["EventDetectorEngine"]
