"""Deterministic provider adapters used by contract and integration tests."""

from __future__ import annotations

from .identity import InstrumentIdentity
from .observations import Observation, ObservationClocks


class DeterministicQuoteProvider:
    def __init__(self, provider_id: str, *, price: float) -> None:
        self.provider_id = provider_id
        self.price = price

    def quote(self, instrument: InstrumentIdentity, *, now_ns: int) -> Observation:
        return Observation(
            observation_id=f"{self.provider_id}:{instrument.qualified_id()}:{now_ns}",
            instrument=instrument,
            capability_id="quote",
            provider_id=self.provider_id,
            source_instance_id=f"{self.provider_id}-fixture",
            clocks=ObservationClocks(
                event_time_ns=now_ns,
                source_publish_time_ns=now_ns,
                effective_time_ns=now_ns,
                available_time_ns=now_ns,
                received_time_ns=now_ns,
                ingested_time_ns=now_ns,
                normalized_time_ns=now_ns,
                published_time_ns=None,
                validity_start_ns=now_ns,
                validity_end_ns=None,
            ),
            value={"price": self.price},
            raw_record_id=f"raw:{self.provider_id}:{instrument.qualified_id()}:{now_ns}",
            quality=("COMPLETE", "DETERMINISTIC_FIXTURE"),
            confidence=1.0,
            revision_id="fixture/1",
            adjustment_state="UNADJUSTED",
            license_class="RESEARCH_ONLY",
            normalizer_version="quote/fixture/1",
        )


__all__ = ["DeterministicQuoteProvider"]
