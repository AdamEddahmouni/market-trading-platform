"""Join IMP simulator and external Paper observations on a locked intent.

Pairing is a join, never a blend. Unpaired rows stay NOT_OBSERVABLE.
Correlation identity: ``forward_test:{forward_test_id}`` plus an explicit
pairing table when the comparator cannot echo the client order id.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from ...execution.simulator import SIMULATOR_VERSION, SOURCE_CAPABILITY
from ...intelligence.paper_forward_bridge.paper_handoff import (
    forward_test_correlation_id,
)
from .metrics import CalibrationDivergenceClass, FillObservation

PAIR_METHOD_CORRELATION_ID = "CORRELATION_ID"
PAIR_METHOD_CLIENT_ORDER_ID = "CLIENT_ORDER_ID"
PAIR_METHOD_PAIRING_TABLE = "PAIRING_TABLE"
PAIR_CONFIDENCE_HIGH = "HIGH"
PAIR_CONFIDENCE_LOW = "LOW"


@dataclass(frozen=True, slots=True)
class ComparatorPairingRecord:
    """Explicit join row when the comparator cannot echo IMP's client order id."""

    forward_test_id: str
    paper_order_id: str
    comparator_order_id: str
    pair_method: str
    pair_confidence: str
    pair_time_ns: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "forward_test_id": self.forward_test_id,
            "paper_order_id": self.paper_order_id,
            "comparator_order_id": self.comparator_order_id,
            "pair_method": self.pair_method,
            "pair_confidence": self.pair_confidence,
            "pair_time_ns": self.pair_time_ns,
        }

    @classmethod
    def from_mapping(cls, row: Mapping[str, Any]) -> ComparatorPairingRecord:
        return cls(
            forward_test_id=str(row.get("forward_test_id") or ""),
            paper_order_id=str(row.get("paper_order_id") or ""),
            comparator_order_id=str(row.get("comparator_order_id") or ""),
            pair_method=str(row.get("pair_method") or PAIR_METHOD_PAIRING_TABLE),
            pair_confidence=str(row.get("pair_confidence") or PAIR_CONFIDENCE_LOW),
            pair_time_ns=int(row.get("pair_time_ns") or 0),
        )


@dataclass(frozen=True, slots=True)
class PairedObservation:
    correlation_id: str
    forward_test_id: str
    paper_order_id: str
    comparator_order_id: str
    pair_method: str
    pair_confidence: str
    simulator_version: str
    source_capability: str
    paper_account_id: str
    instrument_id: str
    asset_class: str
    imp: FillObservation
    comparator: FillObservation
    observable: bool

    @property
    def divergence_class(self) -> CalibrationDivergenceClass:
        if not self.observable or self.pair_confidence == PAIR_CONFIDENCE_LOW:
            return CalibrationDivergenceClass.NOT_OBSERVABLE
        return CalibrationDivergenceClass.WITHIN_TOLERANCE

    def to_dict(self) -> dict[str, Any]:
        return {
            "correlation_id": self.correlation_id,
            "forward_test_id": self.forward_test_id,
            "paper_order_id": self.paper_order_id,
            "comparator_order_id": self.comparator_order_id,
            "pair_method": self.pair_method,
            "pair_confidence": self.pair_confidence,
            "simulator_version": self.simulator_version,
            "source_capability": self.source_capability,
            "paper_account_id": self.paper_account_id,
            "instrument_id": self.instrument_id,
            "asset_class": self.asset_class,
            "imp": self.imp.to_dict(),
            "comparator": self.comparator.to_dict(),
            "observable": self.observable,
        }


@dataclass(frozen=True, slots=True)
class PairingResult:
    pairs: tuple[PairedObservation, ...]
    unpaired_imp: tuple[FillObservation, ...]
    unpaired_comparator: tuple[FillObservation, ...]

    @property
    def pair_count(self) -> int:
        return len(self.pairs)

    def to_dict(self) -> dict[str, Any]:
        return {
            "pair_count": self.pair_count,
            "unpaired_imp_count": len(self.unpaired_imp),
            "unpaired_comparator_count": len(self.unpaired_comparator),
            "pairs": [item.to_dict() for item in self.pairs],
        }


def _observation_key(row: FillObservation) -> str:
    if row.correlation_id:
        return row.correlation_id
    return row.order_id


def _index_observations(
    rows: Sequence[FillObservation] | Sequence[Mapping[str, Any]],
) -> dict[str, FillObservation]:
    indexed: dict[str, FillObservation] = {}
    for item in rows:
        row = item if isinstance(item, FillObservation) else FillObservation.from_mapping(item)
        key = _observation_key(row)
        if key:
            indexed[key] = row
    return indexed


def pair_imp_and_comparator(
    *,
    forward_test_id: str,
    imp_fills: Sequence[FillObservation] | Sequence[Mapping[str, Any]],
    comparator_fills: Sequence[FillObservation] | Sequence[Mapping[str, Any]],
    pairing_table: Sequence[ComparatorPairingRecord] | Sequence[Mapping[str, Any]] = (),
    paper_account_id: str = "",
    instrument_id: str = "",
    asset_class: str = "EQUITY",
    simulator_version: str = SIMULATOR_VERSION,
) -> PairingResult:
    """Join IMP and comparator legs for one locked forward-test intent."""
    correlation_id = forward_test_correlation_id(forward_test_id)
    imp = _index_observations(imp_fills)
    comp = _index_observations(comparator_fills)
    table_rows = [
        item if isinstance(item, ComparatorPairingRecord) else ComparatorPairingRecord.from_mapping(item)
        for item in pairing_table
    ]
    table_by_paper = {
        row.paper_order_id: row
        for row in table_rows
        if row.forward_test_id == forward_test_id and row.paper_order_id
    }
    used_imp: set[str] = set()
    used_comp: set[str] = set()
    pairs: list[PairedObservation] = []

    shared_keys = sorted(set(imp) & set(comp))
    for key in shared_keys:
        imp_row = imp[key]
        comp_row = comp[key]
        method = (
            PAIR_METHOD_CORRELATION_ID
            if key == correlation_id or imp_row.correlation_id or comp_row.correlation_id
            else PAIR_METHOD_CLIENT_ORDER_ID
        )
        pairs.append(
            PairedObservation(
                correlation_id=imp_row.correlation_id or comp_row.correlation_id or correlation_id,
                forward_test_id=forward_test_id,
                paper_order_id=imp_row.order_id,
                comparator_order_id=comp_row.order_id,
                pair_method=method,
                pair_confidence=PAIR_CONFIDENCE_HIGH,
                simulator_version=simulator_version,
                source_capability=SOURCE_CAPABILITY,
                paper_account_id=imp_row.paper_account_id or paper_account_id,
                instrument_id=imp_row.instrument_id or instrument_id,
                asset_class=imp_row.asset_class or asset_class,
                imp=imp_row,
                comparator=comp_row,
                observable=True,
            )
        )
        used_imp.add(key)
        used_comp.add(key)

    for paper_key, table_row in table_by_paper.items():
        if paper_key in used_imp:
            continue
        if table_row.pair_confidence == PAIR_CONFIDENCE_LOW:
            continue
        imp_row = next((row for key, row in imp.items() if row.order_id == paper_key), None)
        comp_row = next(
            (row for key, row in comp.items() if row.order_id == table_row.comparator_order_id),
            None,
        )
        if imp_row is None or comp_row is None:
            continue
        pairs.append(
            PairedObservation(
                correlation_id=correlation_id,
                forward_test_id=forward_test_id,
                paper_order_id=imp_row.order_id,
                comparator_order_id=comp_row.order_id,
                pair_method=PAIR_METHOD_PAIRING_TABLE,
                pair_confidence=table_row.pair_confidence,
                simulator_version=simulator_version,
                source_capability=SOURCE_CAPABILITY,
                paper_account_id=imp_row.paper_account_id or paper_account_id,
                instrument_id=imp_row.instrument_id or instrument_id,
                asset_class=imp_row.asset_class or asset_class,
                imp=imp_row,
                comparator=comp_row,
                observable=table_row.pair_confidence == PAIR_CONFIDENCE_HIGH,
            )
        )
        used_imp.add(_observation_key(imp_row))
        used_comp.add(_observation_key(comp_row))

    unpaired_imp = tuple(row for key, row in imp.items() if key not in used_imp)
    unpaired_comp = tuple(row for key, row in comp.items() if key not in used_comp)
    return PairingResult(
        pairs=tuple(pairs),
        unpaired_imp=unpaired_imp,
        unpaired_comparator=unpaired_comp,
    )


__all__ = [
    "PAIR_CONFIDENCE_HIGH",
    "PAIR_CONFIDENCE_LOW",
    "PAIR_METHOD_CLIENT_ORDER_ID",
    "PAIR_METHOD_CORRELATION_ID",
    "PAIR_METHOD_PAIRING_TABLE",
    "ComparatorPairingRecord",
    "PairedObservation",
    "PairingResult",
    "forward_test_correlation_id",
    "pair_imp_and_comparator",
]
