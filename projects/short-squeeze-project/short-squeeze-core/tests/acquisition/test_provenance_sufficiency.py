from datetime import UTC, datetime

import pytest

from squeeze_core.acquisition.models import (
    EvidenceSufficiencyState, HistoricalOrCurrent, ProviderProvenance,
)
from squeeze_core.acquisition.provenance import review_historical_provenance
from squeeze_core.acquisition.sufficiency import review_evidence_sufficiency


def _provenance(**changes):
    values = {
        "provider_provenance_id": "prov-1", "provider_name": "Example",
        "provider_product": "Feed", "provider_dataset": "Dataset",
        "provider_scope": "US_EQUITY", "access_method": "LOCAL_EXPORT",
        "artifact_timestamp": datetime(2024, 5, 14, 12, 5, tzinfo=UTC),
        "event_at": datetime(2024, 5, 14, 12, 0, tzinfo=UTC),
        "observed_at": datetime(2024, 5, 14, 12, 1, tzinfo=UTC),
        "effective_at": datetime(2024, 5, 14, 12, 2, tzinfo=UTC),
        "published_at": datetime(2024, 5, 14, 12, 3, tzinfo=UTC),
        "received_at": datetime(2024, 5, 14, 12, 4, tzinfo=UTC),
        "timezone": "UTC", "latency_status": "KNOWN",
        "historical_or_current": HistoricalOrCurrent.HISTORICAL,
        "revision_status": "ORIGINAL", "source_artifact_id": "artifact-1",
    }
    values.update(changes)
    return ProviderProvenance(**values)


def test_current_data_cannot_masquerade_as_historical_and_scope_must_be_explicit():
    current = review_historical_provenance(_provenance(
        historical_or_current=HistoricalOrCurrent.CURRENT
    ))
    missing_scope = review_historical_provenance(_provenance(provider_scope="UNKNOWN"))
    assert current == ("MODERN_DATA_MISREPRESENTED_AS_HISTORICAL",)
    assert missing_scope == ("PROVIDER_SCOPE_UNRESOLVED",)


@pytest.mark.parametrize(
    ("constructible", "outcome", "identity_conflict", "blocked", "expected"),
    (
        (True, False, False, False, EvidenceSufficiencyState.SUFFICIENT_FOR_PHASE_3A),
        (False, True, False, False, EvidenceSufficiencyState.SUFFICIENT_FOR_PHASE_3B_OUTCOME_ONLY),
        (False, False, False, False, EvidenceSufficiencyState.SUFFICIENT_FOR_REGISTRY_ONLY),
        (False, False, True, False, EvidenceSufficiencyState.CONFLICTED),
        (False, False, False, True, EvidenceSufficiencyState.BLOCKED),
    ),
)
def test_evidence_sufficiency_states_are_explicit(
    constructible, outcome, identity_conflict, blocked, expected,
):
    review = review_evidence_sufficiency(
        present_domains=("MARKET_BARS",), missing_domains=("SHORT_PRESSURE",),
        phase_3a_request_constructible=constructible, outcome_only_available=outcome,
        identity_conflicted=identity_conflict, publication_blocked=blocked,
    )
    assert review.state is expected
    assert review.missing_domains == ("SHORT_PRESSURE",)


def test_missing_short_pressure_does_not_prevent_phase3a_sufficiency():
    review = review_evidence_sufficiency(
        present_domains=("MARKET_BARS",), missing_domains=("SHORT_PRESSURE",),
        phase_3a_request_constructible=True, outcome_only_available=False,
        identity_conflicted=False, publication_blocked=False,
    )
    assert review.state is EvidenceSufficiencyState.SUFFICIENT_FOR_PHASE_3A
