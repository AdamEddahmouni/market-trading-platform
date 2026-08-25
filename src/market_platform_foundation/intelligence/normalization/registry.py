"""Provider normalizer registry (BUILD 03)."""

from __future__ import annotations

from typing import Any, Callable, Protocol

from .models import NormalizationContext, NormalizationResult


class EventNormalizer(Protocol):
    def normalize(self, raw: Any, *, context: NormalizationContext) -> NormalizationResult:
        ...


NormalizerFn = Callable[..., NormalizationResult]

_REGISTRY: dict[str, NormalizerFn] = {}


def register_normalizer(source_key: str, fn: NormalizerFn) -> None:
    _REGISTRY[source_key] = fn


def get_normalizer(source_key: str) -> NormalizerFn | None:
    return _REGISTRY.get(source_key)


def registered_sources() -> frozenset[str]:
    return frozenset(_REGISTRY)


def _register_defaults() -> None:
    from .providers.finviz import normalize_finviz_candidate
    from .providers.finra import normalize_short_interest_observation
    from .providers.ibkr import normalize_ibkr_record
    from .providers.macro import normalize_macro_observation
    from .providers.moomoo import normalize_moomoo_capture
    from .providers.sec_edgar import normalize_sec_filing
    from .providers.sec_ftd import normalize_ftd_observation
    from .envelope_bridge import normalize_envelope

    register_normalizer("moomoo.capture", normalize_moomoo_capture)
    register_normalizer("moomoo", normalize_moomoo_capture)
    register_normalizer("envelope", normalize_envelope)
    register_normalizer("sec.edgar.filing", normalize_sec_filing)
    register_normalizer("sec.edgar", normalize_sec_filing)
    register_normalizer("finviz.candidate", normalize_finviz_candidate)
    register_normalizer("finviz", normalize_finviz_candidate)
    register_normalizer("sec.ftd", normalize_ftd_observation)
    register_normalizer("finra.short_interest", normalize_short_interest_observation)
    register_normalizer("fred.macro", normalize_macro_observation)
    register_normalizer("macro", normalize_macro_observation)
    register_normalizer("ibkr", normalize_ibkr_record)


_register_defaults()


__all__ = [
    "EventNormalizer",
    "get_normalizer",
    "register_normalizer",
    "registered_sources",
]
