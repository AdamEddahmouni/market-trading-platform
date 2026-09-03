"""RT-01 domain equivalence — tracing OFF vs FULL must not change domain output."""

from __future__ import annotations

from typing import Any, Callable


def prove_equivalence(
    workload_fn: Callable[[], dict[str, Any]],
    *,
    iterations: int = 3,
) -> dict[str, Any]:
    from .enums import SamplingMode
    from .tracer import Tracer, configure_tracer

    results: list[dict[str, Any]] = []
    for mode in (SamplingMode.OFF, SamplingMode.FULL):
        configure_tracer(Tracer(mode=mode))
        for _ in range(iterations):
            results.append(workload_fn())
    off_hashes = [r.get("domain_hash") for r in results[:iterations]]
    full_hashes = [r.get("domain_hash") for r in results[iterations:]]
    equivalent = off_hashes == full_hashes and all(h is not None for h in off_hashes)
    return {
        "equivalent": equivalent,
        "off_domain_hashes": off_hashes,
        "full_domain_hashes": full_hashes,
        "iterations": iterations,
    }


__all__ = ["prove_equivalence"]
