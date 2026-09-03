"""Cross-domain lifecycle consistency guards.

Uses the multi-domain Phase 1I normalized fixture (which carries all ten evidence domains,
including immutable trade/quote original -> corrected -> cancelled chains) to prove three
cross-domain lifecycle invariants at the bundle level:

* Monotonic accumulation -- as ``as_of`` advances, no previously eligible observation ever
  disappears (there is no look-ahead removal).
* Historical stability -- rebuilding a bundle at an earlier ``as_of`` is byte-identical across
  runs, so a later record never rewrites an earlier bundle.
* Immutability -- a correction or cancellation never deletes or overwrites the prior
  observation; the original remains present alongside its successors.
"""

from datetime import datetime

import pytest

from squeeze_core.evidence import PointInTimeEvidencePolicy, build_point_in_time_evidence
from squeeze_core.replay import load_fixture
from squeeze_core.serialization import canonical_hash
from pathlib import Path

ROOT = Path(__file__).parents[1] / "fixtures"
FIXTURE = ROOT / "evidence" / "normalized_phase_1i_point_in_time.jsonl"

AS_OF_SEQUENCE = [
    "2026-01-31T14:30:00.300000Z",  # after original receipt
    "2026-01-31T14:31:01Z",         # after correction receipt
    "2026-01-31T14:32:01Z",         # after cancellation receipt
    "2026-01-31T14:36:01Z",         # final
]


def _bundle(as_of_iso: str):
    observations = load_fixture(FIXTURE)
    return build_point_in_time_evidence(
        "TESTA",
        observations,
        PointInTimeEvidencePolicy(
            as_of=datetime.fromisoformat(as_of_iso.replace("Z", "+00:00")),
            allow_stale=True,
            allow_delayed=True,
            allow_unknown_freshness=True,
            include_trades_domain=True,
            include_quotes_domain=True,
        ),
    )


def _source_ids(bundle) -> set[str]:
    return {item.source_record_id for item in bundle.observations}


def test_eligibility_is_monotonic_as_of_advances() -> None:
    previous: set[str] = set()
    for as_of in AS_OF_SEQUENCE:
        current = _source_ids(_bundle(as_of))
        assert previous <= current, "an earlier-eligible observation disappeared as as_of advanced"
        previous = current


@pytest.mark.parametrize("as_of", AS_OF_SEQUENCE)
def test_historical_bundle_is_byte_stable_across_rebuilds(as_of) -> None:
    first = _bundle(as_of)
    second = _bundle(as_of)
    assert first.bundle_hash == second.bundle_hash
    assert canonical_hash(first) == canonical_hash(second)


def test_correction_and_cancellation_preserve_prior_observations() -> None:
    final = _source_ids(_bundle("2026-01-31T14:36:01Z"))
    # The corrected and cancelled trade/quote lifecycle rows never delete their originals.
    for base in ("phase1i-trade", "phase1i-quote"):
        assert f"{base}-original" in final
        assert f"{base}-corrected" in final
        assert f"{base}-cancelled" in final


def test_cancellation_does_not_empty_the_domain_coverage() -> None:
    bundle = _bundle("2026-01-31T14:36:01Z")
    coverage = {item.domain.value: item for item in bundle.source_coverage}
    # Even after a cancellation lifecycle row, prior evidence keeps the domain populated.
    assert coverage["TRADES"].observation_ids
    assert coverage["QUOTES"].observation_ids
