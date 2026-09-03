"""Feature schema and vector extraction (BUILD 08)."""

from __future__ import annotations

import math
from dataclasses import dataclass

from ..contracts.common import ContractKind, QualityState
from ..contracts.signal import SignalV1
from ..contracts.snapshot import SnapshotV1
from .identity import feature_schema_fingerprint
from .types import (
    BaselineFeatureVector,
    PredictionDiagnostic,
    PredictionDiagnosticCode,
)


@dataclass(frozen=True, slots=True)
class FeatureSelector:
    """Identifies one canonical SignalV1 within a snapshot-bound set."""

    signal_type: str
    window_ns: int | None = None
    calculator_id: str | None = None
    calculator_version: str | None = None

    def feature_key(self) -> str:
        parts = [self.signal_type]
        if self.window_ns is not None:
            parts.append(f"@{self.window_ns}ns")
        else:
            parts.append("@point")
        if self.calculator_id is not None:
            parts.append(f"calc={self.calculator_id}")
        if self.calculator_version is not None:
            parts.append(f"v={self.calculator_version}")
        return "|".join(parts)

    def selector_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {"signal_type": self.signal_type}
        if self.window_ns is not None:
            payload["window_ns"] = self.window_ns
        if self.calculator_id is not None:
            payload["calculator_id"] = self.calculator_id
        if self.calculator_version is not None:
            payload["calculator_version"] = self.calculator_version
        return payload

    def matches(self, signal: SignalV1) -> bool:
        if signal.signal_type != self.signal_type:
            return False
        signal_window = (
            signal.calculation_window.duration_ns if signal.calculation_window is not None else None
        )
        if self.window_ns is not None and signal_window != self.window_ns:
            return False
        if self.window_ns is None and signal_window is not None:
            return False
        lineage = signal.calculation_lineage
        if self.calculator_id is not None and lineage.get("calculator_id") != self.calculator_id:
            return False
        if self.calculator_version is not None and lineage.get("calculator_version") != self.calculator_version:
            return False
        return True


@dataclass(frozen=True, slots=True)
class BaselineFeatureSchema:
    selectors: tuple[FeatureSelector, ...]

    def __post_init__(self) -> None:
        keys = [selector.feature_key() for selector in self.selectors]
        if len(keys) != len(set(keys)):
            raise ValueError("FEATURE_SCHEMA_DUPLICATE_SELECTOR")

    @property
    def fingerprint(self) -> str:
        payload = [selector.selector_payload() for selector in self.selectors]
        return feature_schema_fingerprint(payload)

    @property
    def feature_keys(self) -> tuple[str, ...]:
        return tuple(selector.feature_key() for selector in self.selectors)


DEFAULT_STATISTICAL_WINDOW_NS = 300 * 1_000_000_000

DEFAULT_STATISTICAL_FEATURE_SCHEMA = BaselineFeatureSchema(
    selectors=(
        FeatureSelector(
            signal_type="spread_bps",
            calculator_id="spread-calculator",
            calculator_version="1",
        ),
        FeatureSelector(
            signal_type="net_signed_share",
            window_ns=DEFAULT_STATISTICAL_WINDOW_NS,
            calculator_id="cvd-calculator",
            calculator_version="1",
        ),
        FeatureSelector(
            signal_type="depth_imbalance",
            calculator_id="depth-imbalance-calculator",
            calculator_version="1",
        ),
        FeatureSelector(
            signal_type="momentum_simple",
            window_ns=DEFAULT_STATISTICAL_WINDOW_NS,
            calculator_id="momentum-calculator",
            calculator_version="1",
        ),
        FeatureSelector(
            signal_type="realized_vol",
            window_ns=DEFAULT_STATISTICAL_WINDOW_NS,
            calculator_id="realized-volatility-calculator",
            calculator_version="1",
        ),
        FeatureSelector(
            signal_type="relative_volume",
            window_ns=DEFAULT_STATISTICAL_WINDOW_NS,
            calculator_id="relative-volume-calculator",
            calculator_version="1",
        ),
    )
)


MOMENTUM_5M_SELECTOR = FeatureSelector(
    signal_type="momentum_simple",
    window_ns=DEFAULT_STATISTICAL_WINDOW_NS,
    calculator_id="momentum-calculator",
    calculator_version="1",
)


def _signal_belongs_to_snapshot(signal: SignalV1, snapshot: SnapshotV1) -> bool:
    ref = signal.source_snapshot_ref
    if ref is None:
        return False
    return ref.kind == ContractKind.SNAPSHOT.value and ref.id == snapshot.snapshot_id


class FeatureVectorBuilder:
    """Canonical SignalV1 → ordered feature vector extraction."""

    def __init__(self, schema: BaselineFeatureSchema) -> None:
        self._schema = schema

    @property
    def schema(self) -> BaselineFeatureSchema:
        return self._schema

    def extract(
        self,
        snapshot: SnapshotV1,
        signals: tuple[SignalV1, ...] | list[SignalV1],
        *,
        allow_degraded: bool = False,
    ) -> tuple[BaselineFeatureVector | None, tuple[PredictionDiagnostic, ...]]:
        diagnostics: list[PredictionDiagnostic] = []
        selected: list[SignalV1] = []
        values: list[float] = []

        for selector in self._schema.selectors:
            matches = [signal for signal in signals if selector.matches(signal)]
            if not matches:
                diagnostics.append(
                    PredictionDiagnostic(
                        code=PredictionDiagnosticCode.MISSING_FEATURE,
                        message=f"Missing required feature: {selector.feature_key()}",
                        details={"feature_key": selector.feature_key()},
                    )
                )
                continue
            if len(matches) > 1:
                diagnostics.append(
                    PredictionDiagnostic(
                        code=PredictionDiagnosticCode.DUPLICATE_FEATURE,
                        message=f"Ambiguous feature match: {selector.feature_key()}",
                        details={
                            "feature_key": selector.feature_key(),
                            "signal_ids": [signal.signal_id for signal in matches],
                        },
                    )
                )
                continue
            signal = matches[0]
            if not _signal_belongs_to_snapshot(signal, snapshot):
                diagnostics.append(
                    PredictionDiagnostic(
                        code=PredictionDiagnosticCode.SIGNAL_SNAPSHOT_MISMATCH,
                        message="Signal does not belong to source snapshot",
                        details={"signal_id": signal.signal_id, "snapshot_id": snapshot.snapshot_id},
                    )
                )
                continue
            if signal.as_of_time_ns > snapshot.decision_time_ns:
                diagnostics.append(
                    PredictionDiagnostic(
                        code=PredictionDiagnosticCode.SIGNAL_TIME_VIOLATION,
                        message="Signal as_of_time exceeds snapshot decision time",
                        details={
                            "signal_id": signal.signal_id,
                            "as_of_time_ns": signal.as_of_time_ns,
                            "decision_time_ns": snapshot.decision_time_ns,
                        },
                    )
                )
                continue
            if signal.quality.state == QualityState.INVALID:
                diagnostics.append(
                    PredictionDiagnostic(
                        code=PredictionDiagnosticCode.INVALID_FEATURE,
                        message="Required signal quality is INVALID",
                        details={"signal_id": signal.signal_id},
                    )
                )
                continue
            if signal.quality.state == QualityState.DEGRADED and not allow_degraded:
                diagnostics.append(
                    PredictionDiagnostic(
                        code=PredictionDiagnosticCode.DEGRADED_FEATURE_REJECTED,
                        message="Degraded feature rejected by policy",
                        details={"signal_id": signal.signal_id},
                    )
                )
                continue
            if not math.isfinite(signal.value):
                diagnostics.append(
                    PredictionDiagnostic(
                        code=PredictionDiagnosticCode.INVALID_FEATURE,
                        message="Non-finite feature value",
                        details={"signal_id": signal.signal_id},
                    )
                )
                continue
            selected.append(signal)
            values.append(float(signal.value))

        if diagnostics:
            return None, tuple(diagnostics)
        return (
            BaselineFeatureVector(
                values=tuple(values),
                source_signals=tuple(selected),
                feature_keys=self._schema.feature_keys,
            ),
            (),
        )


__all__ = [
    "DEFAULT_STATISTICAL_FEATURE_SCHEMA",
    "DEFAULT_STATISTICAL_WINDOW_NS",
    "MOMENTUM_5M_SELECTOR",
    "BaselineFeatureSchema",
    "FeatureSelector",
    "FeatureVectorBuilder",
]
