from __future__ import annotations

from pathlib import Path

from .canonical import sha256_bytes
from .adapters.equity_intraday_jsonl import EquityIntradayJsonlAdapter
from .execution.options_conservative import OptionsConservativeSimulator
from .execution.book_aware import BookAwareL2Simulator
from .execution.simulator import BarConservativeSimulator, SimulatorDescriptor
from .offline.fixture_manifest import ManifestOnlyReader

_REGISTRY = {
    "offline.equity_intraday_jsonl": EquityIntradayJsonlAdapter,
    "offline.fixture_manifest": ManifestOnlyReader,
    "simulation.bar_conservative": BarConservativeSimulator,
    "simulation.book_aware_l2_v1": BookAwareL2Simulator,
    "simulation.noop": SimulatorDescriptor,
    "simulation.options_conservative": OptionsConservativeSimulator,
}

_CAPABILITIES = {
    "offline.equity_intraday_jsonl": (
        "Read and normalize the admitted equity intraday JSONL fixture from an "
        "authorized collection path without network access."
    ),
    "offline.fixture_manifest": (
        "Read an embedded, synthetic, non-market structural manifest without "
        "filesystem discovery."
    ),
    "simulation.bar_conservative": (
        "Conservative bar-only execution simulation for BAR_OHLCV_1M capability; "
        "no broker routing."
    ),
    "simulation.book_aware_l2_v1": (
        "Conservative bar execution with displayed L2 touch-depth partial-fill cap; "
        "no broker routing."
    ),
    "simulation.noop": (
        "Expose a non-routing simulator descriptor; no order, fill, account, "
        "or transport method exists."
    ),
    "simulation.options_conservative": (
        "Conservative NBBO multi-leg options execution simulation; spread crossing "
        "at bid/ask with liquidity gating; no broker routing."
    ),
}


def resolve_registry(registry_id: str) -> type:
    if registry_id not in _REGISTRY:
        raise KeyError(f"registry identifier is not allowed: {registry_id}")
    return _REGISTRY[registry_id]


def registry_snapshot() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for key, value in sorted(_REGISTRY.items()):
        source = Path(__file__).parent / Path(*value.__module__.split(".")[1:])
        source = source.with_suffix(".py")
        rows.append(
            {
                "capability": _CAPABILITIES[key],
                "implementation": f"{value.__module__}:{value.__name__}",
                "registry_id": key,
                "source_file_sha256": sha256_bytes(source.read_bytes()),
            }
        )
    return rows

