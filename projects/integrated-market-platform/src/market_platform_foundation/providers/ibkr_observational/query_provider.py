"""G11 IBKR read-only query provider boundary.

Outer ``tools/ibkr`` implementations satisfy ``IbkrReadOnlyQueryProvider``.
Canonical src owns normalization, capability gating, and replay capture — never
imports tools.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, Sequence

from ..runtime_capability import (
    CAP_ACCOUNT_READ,
    CAP_CONTRACT_RESOLUTION,
    CAP_HISTORICAL_BARS,
    CAP_HISTORICAL_TRADES,
    RuntimeCapabilityRegistry,
    RuntimeCapabilityState,
)
from .capability import (
    IBKR_CAPABILITY_ACCOUNT_READ,
    IBKR_CAPABILITY_CONTRACT_RESOLUTION,
    IBKR_CAPABILITY_HISTORICAL_BARS,
    IBKR_CAPABILITY_HISTORICAL_TRADES,
    IBKR_PROVIDER_ID,
)
from .account_observation import (
    ProviderAccountObservation,
    normalize_ibkr_account_discovery,
)
from .capture import CallbackCapture, capture_query_record
from .contract_resolution import (
    ContractQualification,
    qualification_from_contract,
    resolve_equity_contract,
    resolve_specific_contract,
)
from .historical_bars import (
    ObservationalHistoricalBar,
    normalize_ibkr_history_payload,
)
from .historical_trades import (
    ObservationalHistoricalTrade,
    normalize_ibkr_historical_trades_payload,
)
from .identity import IdentityAdmissionError, InstrumentLookup, Xa01Admission


class IbkrReadOnlyQueryProvider(Protocol):
    """Injected read-only IBKR request/response surface (outer-owned)."""

    def is_available(self) -> bool: ...

    def fetch_secdef_search(self, symbol: str) -> Sequence[Mapping[str, Any]]: ...

    def fetch_historical_bars(
        self,
        *,
        con_id: int,
        period: str,
        bar: str,
    ) -> Mapping[str, Any]: ...

    def fetch_historical_trades(
        self,
        *,
        con_id: int,
        start_time_ns: int,
        end_time_ns: int,
    ) -> Mapping[str, Any]: ...

    def fetch_portfolio_accounts(self) -> Mapping[str, Any]: ...

    def shutdown(self) -> None: ...


@dataclass(frozen=True, slots=True)
class ContractResolutionResult:
    accepted: bool
    instrument_id: str | None = None
    qualification: ContractQualification | None = None
    reason: str | None = None
    selection: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "instrument_id": self.instrument_id,
            "qualification": None
            if self.qualification is None
            else self.qualification.as_dict(),
            "reason": self.reason,
            "selection": dict(self.selection),
        }


@dataclass(frozen=True, slots=True)
class HistoricalBarsResult:
    accepted: bool
    bars: tuple[ObservationalHistoricalBar, ...] = ()
    reason: str | None = None
    selection: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "bar_count": len(self.bars),
            "bars": [bar.to_dict() for bar in self.bars],
            "reason": self.reason,
            "selection": dict(self.selection),
        }


@dataclass(frozen=True, slots=True)
class HistoricalTradesResult:
    accepted: bool
    trades: tuple[ObservationalHistoricalTrade, ...] = ()
    reason: str | None = None
    selection: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "trade_count": len(self.trades),
            "trades": [trade.to_dict() for trade in self.trades],
            "reason": self.reason,
            "selection": dict(self.selection),
        }


@dataclass(frozen=True, slots=True)
class AccountObservationResult:
    accepted: bool
    observation: ProviderAccountObservation | None = None
    reason: str | None = None
    selection: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "observation": None
            if self.observation is None
            else self.observation.to_dict(),
            "reason": self.reason,
            "selection": dict(self.selection),
        }


class _SecdefQualifyBroker:
    """Adapt secdef search rows to ``QualifyBroker`` for XA-01 admission."""

    def __init__(self, rows: Sequence[Mapping[str, Any]]) -> None:
        self._rows = list(rows)

    def qualifyContracts(self, *contracts: Any) -> list[Any]:
        from types import SimpleNamespace

        symbol = str(getattr(contracts[0], "symbol", "") or "").upper()
        con_id = getattr(contracts[0], "conId", None)
        matches: list[Any] = []
        for row in self._rows:
            row_symbol = str(row.get("symbol") or row.get("companyHeader") or "").upper()
            row_conid = row.get("conid") or row.get("conId")
            if con_id is not None and row_conid == con_id:
                matches.append(
                    SimpleNamespace(
                        conId=int(row_conid),
                        symbol=str(row.get("symbol") or symbol),
                        secType=str(row.get("secType") or "STK"),
                        exchange=str(row.get("exchange") or "SMART"),
                        currency=str(row.get("currency") or "USD"),
                        localSymbol=row.get("localSymbol"),
                        lastTradeDateOrContractMonth=row.get("expiry"),
                        strike=row.get("strike"),
                        right=row.get("right"),
                        tradingClass=row.get("tradingClass"),
                        multiplier=row.get("multiplier"),
                    )
                )
            elif row_symbol == symbol and con_id is None:
                if row_conid is None:
                    continue
                matches.append(
                    SimpleNamespace(
                        conId=int(row_conid),
                        symbol=str(row.get("symbol") or symbol),
                        secType=str(row.get("secType") or "STK"),
                        exchange=str(row.get("exchange") or "SMART"),
                        currency=str(row.get("currency") or "USD"),
                    )
                )
        if len(matches) == 1:
            return matches
        if len(matches) > 1:
            return matches
        if con_id is not None:
            return [
                SimpleNamespace(
                    conId=int(con_id),
                    symbol=symbol,
                    secType=str(getattr(contracts[0], "secType", "STK") or "STK"),
                    exchange=str(getattr(contracts[0], "exchange", "SMART") or "SMART"),
                    currency=str(getattr(contracts[0], "currency", "USD") or "USD"),
                )
            ]
        return []


@dataclass
class IbkrObservationalQueryService:
    """Canonical read-only query service — injected provider, src normalization."""

    provider: IbkrReadOnlyQueryProvider
    lookup: InstrumentLookup | None = None
    admission: Xa01Admission | None = None
    capability_registry: RuntimeCapabilityRegistry | None = None
    capture: CallbackCapture | None = None
    _shutdown_complete: bool = False

    def _gate(
        self,
        lane_capability_id: str,
        instrument_id: str,
        *,
        require_real_time: bool = False,
    ) -> dict[str, Any]:
        registry = self.capability_registry
        if registry is None:
            return {"outcome": "SELECTED", "provider_id": IBKR_PROVIDER_ID}
        registry_cap = {
            CAP_CONTRACT_RESOLUTION: IBKR_CAPABILITY_CONTRACT_RESOLUTION,
            CAP_HISTORICAL_BARS: IBKR_CAPABILITY_HISTORICAL_BARS,
            CAP_HISTORICAL_TRADES: IBKR_CAPABILITY_HISTORICAL_TRADES,
            CAP_ACCOUNT_READ: IBKR_CAPABILITY_ACCOUNT_READ,
        }.get(lane_capability_id, lane_capability_id)
        view = registry.view_capability(
            IBKR_PROVIDER_ID,
            registry_cap,
            instrument_id=instrument_id,
        )
        outcome = view.to_dict()
        state = view.runtime_state
        if state in {
            RuntimeCapabilityState.UNAVAILABLE,
            RuntimeCapabilityState.PROVIDER_UNAVAILABLE,
            RuntimeCapabilityState.NOT_ENTITLED,
        }:
            outcome["outcome"] = "REJECTED"
        elif require_real_time and state not in {
            RuntimeCapabilityState.READY,
            RuntimeCapabilityState.LIVE_PROVIDER_UNVERIFIED,
            RuntimeCapabilityState.DEGRADED,
        }:
            outcome["outcome"] = "REJECTED"
        elif not view.implemented:
            outcome["outcome"] = "REJECTED"
        else:
            outcome["outcome"] = "SELECTED"
        return outcome

    def resolve_contract(
        self,
        instrument_id: str,
        *,
        contract_builder: Any | None = None,
        con_id: int | None = None,
    ) -> ContractResolutionResult:
        if self._shutdown_complete or not self.provider.is_available():
            return ContractResolutionResult(
                accepted=False, reason="QUERY_PROVIDER_UNAVAILABLE"
            )
        selection = self._gate(CAP_CONTRACT_RESOLUTION, instrument_id)
        if selection.get("outcome") != "SELECTED":
            return ContractResolutionResult(
                accepted=False, reason="CAPABILITY_REJECTED", selection=selection
            )
        gate = self.admission or Xa01Admission()
        lookup = self.lookup
        try:
            if contract_builder is not None:
                broker = _SecdefQualifyBroker(
                    self.provider.fetch_secdef_search(
                        str(getattr(contract_builder, "symbol", instrument_id) or instrument_id)
                    )
                )
                canonical, qualification = resolve_specific_contract(
                    broker,
                    instrument_id=instrument_id,
                    contract_builder=contract_builder,
                    admission=gate,
                    lookup=lookup,
                )
            else:
                rows = self.provider.fetch_secdef_search(instrument_id)
                broker = _SecdefQualifyBroker(rows)
                if con_id is not None:
                    from types import SimpleNamespace

                    contract = SimpleNamespace(
                        symbol=instrument_id,
                        secType="STK",
                        exchange="SMART",
                        currency="USD",
                        conId=con_id,
                    )
                    qualified = broker.qualifyContracts(contract)
                    if not qualified:
                        raise IdentityAdmissionError(
                            "CONTRACT_RESOLUTION_FAILED", instrument_id=instrument_id
                        )
                    if lookup is not None:
                        admitted = gate.admit_with_lookup(
                            instrument_id=instrument_id, lookup=lookup
                        )
                    else:
                        admitted = gate.admit(instrument_id=instrument_id)
                    canonical = admitted.instrument_id
                    qualification = qualification_from_contract(qualified[0])
                else:
                    canonical, qualification = resolve_equity_contract(
                        broker,
                        instrument_id=instrument_id,
                        admission=gate,
                        lookup=lookup,
                    )
        except IdentityAdmissionError as exc:
            return ContractResolutionResult(
                accepted=False,
                instrument_id=instrument_id,
                reason=str(exc),
                selection=selection,
            )
        except (ValueError, TypeError) as exc:
            return ContractResolutionResult(
                accepted=False,
                instrument_id=instrument_id,
                reason=str(exc),
                selection=selection,
            )
        if self.capture is not None:
            self.capture.record(
                capture_query_record(
                    query_kind="CONTRACT_RESOLUTION",
                    instrument_id=canonical,
                    request={"instrument_id": instrument_id, "con_id": con_id},
                    response=qualification.as_dict(),
                )
            )
        return ContractResolutionResult(
            accepted=True,
            instrument_id=canonical,
            qualification=qualification,
            selection=selection,
        )

    def fetch_historical_bars(
        self,
        instrument_id: str,
        *,
        period: str = "1d",
        bar: str = "1h",
        con_id: int | None = None,
        received_time_ns: int | None = None,
        pit_cutoff_ns: int | None = None,
    ) -> HistoricalBarsResult:
        if self._shutdown_complete or not self.provider.is_available():
            return HistoricalBarsResult(
                accepted=False, reason="QUERY_PROVIDER_UNAVAILABLE"
            )
        selection = self._gate(
            CAP_HISTORICAL_BARS, instrument_id, require_real_time=False
        )
        if selection.get("outcome") != "SELECTED":
            return HistoricalBarsResult(
                accepted=False, reason="CAPABILITY_REJECTED", selection=selection
            )
        resolved_con_id = con_id
        if resolved_con_id is None:
            resolution = self.resolve_contract(instrument_id)
            if not resolution.accepted or resolution.qualification is None:
                return HistoricalBarsResult(
                    accepted=False,
                    reason=resolution.reason or "CONTRACT_RESOLUTION_FAILED",
                    selection=selection,
                )
            resolved_con_id = resolution.qualification.con_id
        try:
            payload = self.provider.fetch_historical_bars(
                con_id=int(resolved_con_id),
                period=period,
                bar=bar,
            )
            bars = normalize_ibkr_history_payload(
                payload,
                instrument_id=instrument_id,
                interval=bar,
                received_time_ns=received_time_ns,
            )
        except ValueError as exc:
            return HistoricalBarsResult(
                accepted=False, reason=str(exc), selection=selection
            )
        except Exception as exc:
            return HistoricalBarsResult(
                accepted=False, reason=f"PROVIDER_ERROR:{exc}", selection=selection
            )
        if pit_cutoff_ns is not None:
            bars = [
                bar_row
                for bar_row in bars
                if bar_row.source_time_ns is not None
                and bar_row.source_time_ns <= pit_cutoff_ns
            ]
        if self.capture is not None:
            self.capture.record(
                capture_query_record(
                    query_kind="HISTORICAL_BARS",
                    instrument_id=instrument_id.upper(),
                    request={
                        "con_id": resolved_con_id,
                        "period": period,
                        "bar": bar,
                    },
                    response={"bar_count": len(bars)},
                )
            )
        return HistoricalBarsResult(
            accepted=True, bars=tuple(bars), selection=selection
        )

    def fetch_historical_trades(
        self,
        instrument_id: str,
        *,
        start_time_ns: int,
        end_time_ns: int,
        con_id: int | None = None,
        received_time_ns: int | None = None,
        request_time_ns: int | None = None,
        terminal_window_end_ns: int | None = None,
    ) -> HistoricalTradesResult:
        if self._shutdown_complete or not self.provider.is_available():
            return HistoricalTradesResult(
                accepted=False, reason="QUERY_PROVIDER_UNAVAILABLE"
            )
        if request_time_ns is None or terminal_window_end_ns is None:
            return HistoricalTradesResult(
                accepted=False,
                reason="POST_HORIZON_RETRIEVAL_TIMING_REQUIRED",
                selection={
                    "request_time_ns": request_time_ns,
                    "terminal_window_end_ns": terminal_window_end_ns,
                },
            )
        if request_time_ns < terminal_window_end_ns:
            return HistoricalTradesResult(
                accepted=False,
                reason="RETRIEVAL_BEFORE_TERMINAL_WINDOW_END",
                selection={
                    "request_time_ns": request_time_ns,
                    "terminal_window_end_ns": terminal_window_end_ns,
                },
            )
        selection = self._gate(
            CAP_HISTORICAL_TRADES, instrument_id, require_real_time=False
        )
        if selection.get("outcome") != "SELECTED":
            return HistoricalTradesResult(
                accepted=False, reason="CAPABILITY_REJECTED", selection=selection
            )
        resolved_con_id = con_id
        if resolved_con_id is None:
            resolution = self.resolve_contract(instrument_id)
            if not resolution.accepted or resolution.qualification is None:
                return HistoricalTradesResult(
                    accepted=False,
                    reason=resolution.reason or "CONTRACT_RESOLUTION_FAILED",
                    selection=selection,
                )
            resolved_con_id = resolution.qualification.con_id
        fetch = getattr(self.provider, "fetch_historical_trades", None)
        if not callable(fetch):
            return HistoricalTradesResult(
                accepted=False,
                reason="HISTORICAL_TRADES_NOT_IMPLEMENTED",
                selection=selection,
            )
        try:
            payload = fetch(
                con_id=int(resolved_con_id),
                start_time_ns=int(start_time_ns),
                end_time_ns=int(end_time_ns),
            )
            trades = normalize_ibkr_historical_trades_payload(
                payload,
                instrument_id=instrument_id,
                received_time_ns=received_time_ns,
            )
        except ValueError as exc:
            return HistoricalTradesResult(
                accepted=False, reason=str(exc), selection=selection
            )
        except Exception as exc:
            return HistoricalTradesResult(
                accepted=False, reason=f"PROVIDER_ERROR:{exc}", selection=selection
            )
        if self.capture is not None:
            self.capture.record(
                capture_query_record(
                    query_kind="HISTORICAL_TRADES",
                    instrument_id=instrument_id.upper(),
                    request={
                        "con_id": resolved_con_id,
                        "start_time_ns": start_time_ns,
                        "end_time_ns": end_time_ns,
                    },
                    response={"trade_count": len(trades)},
                )
            )
        return HistoricalTradesResult(
            accepted=True, trades=tuple(trades), selection=selection
        )

    def fetch_account_observation(
        self,
        *,
        received_time_ns: int | None = None,
    ) -> AccountObservationResult:
        if self._shutdown_complete or not self.provider.is_available():
            return AccountObservationResult(
                accepted=False, reason="QUERY_PROVIDER_UNAVAILABLE"
            )
        selection = self._gate(CAP_ACCOUNT_READ, "_ACCOUNT_")
        if selection.get("outcome") != "SELECTED":
            return AccountObservationResult(
                accepted=False, reason="CAPABILITY_REJECTED", selection=selection
            )
        try:
            payload = self.provider.fetch_portfolio_accounts()
            observation = normalize_ibkr_account_discovery(
                payload,
                received_time_ns=received_time_ns,
            )
        except Exception as exc:
            return AccountObservationResult(
                accepted=False, reason=f"PROVIDER_ERROR:{exc}", selection=selection
            )
        if self.capture is not None:
            self.capture.record(
                capture_query_record(
                    query_kind="ACCOUNT_READ",
                    instrument_id="_ACCOUNT_",
                    request={},
                    response={"account_count": len(observation.account_ids)},
                )
            )
        return AccountObservationResult(
            accepted=True, observation=observation, selection=selection
        )

    def shutdown(self) -> None:
        if self._shutdown_complete:
            return
        self._shutdown_complete = True
        self.provider.shutdown()


__all__ = [
    "AccountObservationResult",
    "ContractResolutionResult",
    "HistoricalBarsResult",
    "HistoricalTradesResult",
    "IbkrObservationalQueryService",
    "IbkrReadOnlyQueryProvider",
]
