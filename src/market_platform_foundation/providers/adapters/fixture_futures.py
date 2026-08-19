"""Fixture-first ES futures depth adapter (PORT_ADAPT from Eric_futuresX concepts)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from ...canonical import canonical_bytes, sha256_bytes
from ...contracts.identity import normalized_event_id
from ...order_flow.impact import compute_impact_dynamics
from ...order_flow.execution_forecast import compute_execution_forecast
from ...order_flow.forecast import compute_microstructure_forecast
from ...order_flow.liquidity import (
    compute_liquidity_dynamics,
    compute_trajectory_resiliency,
    snapshot_total_depth,
)
from ...order_flow.ofi import OFI_METHOD_MULTILEVEL_CS, compute_ofi
from ...donor_patterns.futures_lane import depth_imbalance_signal, is_rth
from ...donor_patterns.order_book_lane import book_pressure_side
from ...donor_patterns.order_book_lane import best_bid_ask
from ...normalization.equity_bars import iso_to_epoch_ns
from ..contracts import ProviderResult, SymbolMapping
from ...order_flow.queue import compute_queue_imbalance_mbo
from .fixture_mbo import FixtureMboProvider
from ..envelope import (
    build_futures_envelope,
    build_provider_metadata,
    snapshot_to_futures_event,
)

DEFAULT_FUTURES_FIXTURE = (
    Path(__file__).resolve().parents[4]
    / "tests"
    / "fixtures"
    / "providers"
    / "futures"
    / "es_depth_slice.json"
)


def _impact_kwargs_from_result(result) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "impact_method": result.impact_method,
        "impact_version": result.impact_version,
        "mid_delta": result.mid_delta,
        "impact_regime": result.impact_regime.value,
        "impact_quality_flags": list(result.quality_flags),
        "opposing_replenishment": result.opposing_replenishment,
    }
    if result.aggression_signed_volume is not None:
        fields["aggression_signed_volume"] = result.aggression_signed_volume
    if result.price_efficiency is not None:
        fields["price_efficiency"] = result.price_efficiency
    if result.absorption_score is not None:
        fields["absorption_score"] = result.absorption_score
    if result.exhaustion_score is not None:
        fields["exhaustion_score"] = result.exhaustion_score
    return fields


def _forecast_kwargs_from_result(result) -> dict[str, Any]:
    return {
        "forecast_method": result.forecast_method,
        "forecast_version": result.forecast_version,
        "forecast_horizon_seconds": result.forecast_horizon_seconds,
        "expected_mid_delta": result.expected_mid_delta,
        "direction_bias": result.direction_bias.value,
        "continuation_probability": result.continuation_probability,
        "reversal_probability": result.reversal_probability,
        "volatility_proxy": result.volatility_proxy,
        "composite_bias": result.composite_bias,
        "model_confidence": result.model_confidence,
        "forecast_quality_flags": list(result.quality_flags),
    }


def _execution_kwargs_from_result(result) -> dict[str, Any]:
    return {
        "execution_method": result.execution_method,
        "execution_version": result.execution_version,
        "book_model_version": result.book_model_version,
        "queue_model_version": result.queue_model_version,
        "aggressive_fill_probability": result.aggressive_fill_probability,
        "passive_fill_probability": result.passive_fill_probability,
        "expected_slippage_spread_fraction": result.expected_slippage_spread_fraction,
        "expected_slippage_absolute": result.expected_slippage_absolute,
        "adverse_selection_risk": result.adverse_selection_risk,
        "touch_depth_bid": result.touch_depth_bid,
        "touch_depth_ask": result.touch_depth_ask,
        "displayed_depth_consumed_fraction": result.displayed_depth_consumed_fraction,
        "execution_quality_flags": list(result.quality_flags),
    }


def _queue_kwargs_from_snapshot(mbo_snapshot) -> dict[str, Any]:
    if mbo_snapshot is None:
        return {"mbo_capability_available": False}
    return {
        "queue_method": mbo_snapshot.queue_method,
        "queue_version": mbo_snapshot.queue_version,
        "queue_imbalance_mbo": compute_queue_imbalance_mbo(mbo_snapshot),
        "mbo_capability_available": True,
    }


class FixtureFuturesProvider:
    """Offline ES futures depth adapter using bounded synthetic demo slice."""

    provider_id = "depth.fixture.futures"
    capability = "futures_depth"
    entitlement = "L2_ES_DEMO_FIXTURE"

    def __init__(self, *, fixture_path: Path | None = None, ingest_run_id: str | None = None) -> None:
        self.fixture_path = fixture_path or DEFAULT_FUTURES_FIXTURE
        self.ingest_run_id = ingest_run_id or sha256_bytes(
            canonical_bytes({"fixture_path": str(self.fixture_path), "provider": self.provider_id})
        )
        self._fixture = self._load_fixture()
        self._mbo_provider = FixtureMboProvider()

    def _load_fixture(self) -> dict[str, Any]:
        payload = json.loads(
            self.fixture_path.read_text(encoding="utf-8"),
            object_pairs_hook=_pairs_no_duplicates,
        )
        if not isinstance(payload, dict):
            raise ValueError("FUTURES_FIXTURE_INVALID")
        return payload

    def fetch_futures_depth(
        self,
        symbol: str,
        *,
        as_of_time_ns: int | None = None,
    ) -> ProviderResult:
        fixture_symbol = str(self._fixture.get("symbol", "")).upper()
        if symbol.upper() != fixture_symbol:
            return ProviderResult(
                status="unavailable",
                reason_code="FUTURES_SYMBOL_NOT_IN_FIXTURE",
                provider_id=self.provider_id,
                capability=self.capability,
            )
        events = self.build_envelopes(as_of_time_ns=as_of_time_ns)
        if not events:
            return ProviderResult(
                status="unavailable",
                reason_code="FUTURES_NO_ELIGIBLE_SNAPSHOTS",
                provider_id=self.provider_id,
                capability=self.capability,
            )
        return ProviderResult(
            status="available",
            events=tuple(events),
            provider_id=self.provider_id,
            capability=self.capability,
        )

    def build_envelopes(self, *, as_of_time_ns: int | None = None) -> list[dict[str, Any]]:
        symbol = str(self._fixture["symbol"]).upper()
        instrument_id = symbol
        mapping = SymbolMapping(
            provider_symbol=symbol,
            instrument_id=instrument_id,
            venue_id="CME",
        )
        snapshots = self._fixture.get("snapshots", [])
        if not isinstance(snapshots, list):
            return []
        level_count = int(self._fixture.get("level_count", 10))
        imbalance_threshold = float(self._fixture.get("imbalance_threshold", 1.5))
        contract_month = str(self._fixture.get("contract_month", ""))
        exchange = str(self._fixture.get("exchange", "CME"))
        session = str(self._fixture.get("session", "RTH"))
        valid_snapshots = [
            snapshot
            for snapshot in snapshots
            if isinstance(snapshot, dict) and snapshot.get("event_time")
        ]
        trajectory_resiliency = compute_trajectory_resiliency(
            valid_snapshots,
            level_count=level_count,
        )
        envelopes: list[dict[str, Any]] = []
        prev_snapshot: dict[str, Any] | None = None
        prev_mid: float | None = None
        recent_mid_deltas: list[float] = []
        for index, snapshot in enumerate(snapshots):
            if not isinstance(snapshot, dict):
                continue
            event_time = str(snapshot.get("event_time", ""))
            if not event_time:
                continue
            available_time_ns = iso_to_epoch_ns(event_time)
            if as_of_time_ns is not None and available_time_ns > as_of_time_ns:
                continue
            bids = snapshot.get("bids", [])
            asks = snapshot.get("asks", [])
            if not isinstance(bids, list) or not isinstance(asks, list):
                continue
            bbo = best_bid_ask(snapshot)
            if bbo is None:
                continue
            signal, ratio = depth_imbalance_signal(
                bids,
                asks,
                level_count=min(level_count, 5),
                threshold=imbalance_threshold,
            )
            pressure = book_pressure_side(ratio, threshold=imbalance_threshold)
            ofi_method: str | None = None
            ofi_version: str | None = None
            book_state_valid: bool | None = None
            liquidity_method: str | None = None
            liquidity_version: str | None = None
            net_depth_delta: float | None = None
            depth_withdrawal: float | None = None
            depth_replenishment: float | None = None
            fragility_score: float | None = None
            resiliency_score: float | None = trajectory_resiliency
            total_depth: float | None = None
            spread_delta: float | None = None
            impact_kwargs: dict[str, Any] = {}
            if prev_snapshot is None:
                ofi_value = 0.0
                total_depth = snapshot_total_depth(snapshot, level_count=level_count)
            else:
                ofi_result = compute_ofi(
                    prev_snapshot,
                    snapshot,
                    method=OFI_METHOD_MULTILEVEL_CS,
                    level_count=level_count,
                )
                ofi_value = ofi_result.value
                ofi_method = ofi_result.ofi_method
                ofi_version = ofi_result.ofi_version
                book_state_valid = ofi_result.book_state_valid
                liquidity = compute_liquidity_dynamics(
                    prev_snapshot,
                    snapshot,
                    level_count=level_count,
                    trajectory_resiliency=trajectory_resiliency,
                )
                liquidity_method = liquidity.liquidity_method
                liquidity_version = liquidity.liquidity_version
                net_depth_delta = liquidity.net_depth_delta
                depth_withdrawal = liquidity.depth_withdrawal
                depth_replenishment = liquidity.depth_replenishment
                fragility_score = liquidity.fragility_score
                resiliency_score = liquidity.resiliency_score
                total_depth = liquidity.total_depth
                spread_delta = liquidity.spread_delta
                impact = compute_impact_dynamics(
                    prev_snapshot,
                    snapshot,
                    bar_delta=None,
                    level_count=level_count,
                    trajectory_resiliency=trajectory_resiliency,
                )
                impact_kwargs = _impact_kwargs_from_result(impact)
            impact_regime = impact_kwargs.get("impact_regime")
            absorption_score = impact_kwargs.get("absorption_score")
            exhaustion_score = impact_kwargs.get("exhaustion_score")
            forecast = compute_microstructure_forecast(
                snapshot,
                ofi_value=ofi_value,
                book_state_valid=book_state_valid if book_state_valid is not None else True,
                fragility_score=fragility_score,
                resiliency_score=resiliency_score,
                impact_regime=impact_regime,
                absorption_score=absorption_score,
                exhaustion_score=exhaustion_score,
                bar_delta=None,
                recent_mid_deltas=recent_mid_deltas,
            )
            forecast_kwargs = _forecast_kwargs_from_result(forecast)
            mbo_snapshot = self._mbo_provider.queue_snapshot_for_event_time(event_time)
            execution = compute_execution_forecast(
                snapshot,
                book_state_valid=book_state_valid if book_state_valid is not None else True,
                fragility_score=fragility_score,
                continuation_probability=forecast.continuation_probability,
                reversal_probability=forecast.reversal_probability,
                direction_bias=forecast.direction_bias,
                exhaustion_score=exhaustion_score,
                impact_regime=impact_regime,
                level_count=level_count,
                mbo_queue_snapshot=mbo_snapshot,
            )
            execution_kwargs = _execution_kwargs_from_result(execution)
            queue_kwargs = _queue_kwargs_from_snapshot(mbo_snapshot)
            curr_mid = (bbo["bid_price"] + bbo["ask_price"]) / 2.0
            if prev_mid is not None and (book_state_valid is None or book_state_valid):
                recent_mid_deltas.append(curr_mid - prev_mid)
                if len(recent_mid_deltas) > 5:
                    recent_mid_deltas = recent_mid_deltas[-5:]
            prev_mid = curr_mid
            event_dt = datetime.fromisoformat(event_time.replace("Z", "+00:00"))
            rth = is_rth(event_dt)
            source_record_id = f"{event_time}:{index}"
            whale_event = snapshot_to_futures_event(
                event_time=event_time,
                contract_month=contract_month,
                exchange=exchange,
                session_state=session if rth else "OUTSIDE_RTH",
                level_count=level_count,
                best_bid=bbo["bid_price"],
                best_ask=bbo["ask_price"],
                bid_size=bbo["bid_size"],
                ask_size=bbo["ask_size"],
                imbalance_ratio=ratio,
                imbalance_signal=signal,
                ofi_value=ofi_value,
                rth=rth,
                snapshot_provenance=str(snapshot.get("source", "fixture_synthetic")),
                book_pressure_side=pressure,
                interpretation_policy="contrarian_depth",
                ofi_method=ofi_method,
                ofi_version=ofi_version,
                book_state_valid=book_state_valid,
                liquidity_method=liquidity_method,
                liquidity_version=liquidity_version,
                net_depth_delta=net_depth_delta,
                depth_withdrawal=depth_withdrawal,
                depth_replenishment=depth_replenishment,
                fragility_score=fragility_score,
                resiliency_score=resiliency_score,
                total_depth=total_depth,
                spread_delta=spread_delta,
                **impact_kwargs,
                **forecast_kwargs,
                **execution_kwargs,
                **queue_kwargs,
            )
            normalized_id = normalized_event_id(
                provider_id=self.provider_id,
                venue_id="CME",
                publisher_id="L2_ES_FIXTURE",
                channel_id=symbol,
                source_instance_id=str(self._fixture.get("fixture_id", "FIXTURE-L2-ES")),
                source_record_id=source_record_id,
                source_revision_id="1",
                event_family="FUTURES_DEPTH_EVENT",
            )
            provider_metadata = build_provider_metadata(
                provider_id=self.provider_id,
                entitlement=self.entitlement,
                event_time_ns=available_time_ns,
                receive_time_ns=available_time_ns,
                symbol_mapping=mapping,
                raw_source_reference=f"{self.fixture_path.name}:{source_record_id}",
            )
            envelopes.append(
                build_futures_envelope(
                    normalized_event_id=normalized_id,
                    source_record_id=source_record_id,
                    instrument_id=instrument_id,
                    event_time_ns=available_time_ns,
                    available_time_ns=available_time_ns,
                    ingest_run_id=self.ingest_run_id,
                    provider_metadata=provider_metadata,
                    whale_event=whale_event,
                )
            )
            prev_snapshot = snapshot
        return _sort_envelopes(envelopes)


def _sort_envelopes(envelopes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        envelopes,
        key=lambda row: (
            int(row["available_time"]),
            str(row["source_record_id"]),
            str(row["source_revision_id"]),
        ),
    )


def _pairs_no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


__all__ = [
    "DEFAULT_FUTURES_FIXTURE",
    "FixtureFuturesProvider",
]
