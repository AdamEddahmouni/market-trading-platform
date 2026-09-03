from __future__ import annotations

from datetime import UTC, datetime

from apps.research_screener.collectors.merge import supplemental_fields
from apps.research_screener.collectors.models import CollectorRecord
from apps.research_screener.collectors.store import EvidenceStore
from apps.research_screener.truth import ValueStatus, known


def test_supplemental_does_not_overwrite_known_finviz_cell() -> None:
    store = EvidenceStore()
    received = datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")
    store.merge(
        [
            CollectorRecord(
                symbol="GME",
                payload={},
                received_at=received,
                source_id="FinraPublishedSI",
                field_hints={
                    "published_short_interest": 99.0,
                    "research_admissibility": "RESEARCH_ADMISSIBLE",
                },
            )
        ]
    )
    fields = {
        "published_short_interest": known(
            14.0,
            unit="PERCENT",
            provider="Finviz Elite",
            research_admissibility="RESEARCH_ADMISSIBLE",
        )
    }
    merged = supplemental_fields("GME", fields, store)
    assert "published_short_interest" not in merged
    assert fields["published_short_interest"].value == 14.0
    assert fields["published_short_interest"].status == ValueStatus.KNOWN


def test_supplemental_fills_not_configured_with_display_fallback(monkeypatch) -> None:
    monkeypatch.setenv("COLLECTOR_OVERRIDE_POLICY", "display_fallback")
    store = EvidenceStore()
    received = datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")
    store.merge(
        [
            CollectorRecord(
                symbol="GME",
                payload={},
                received_at=received,
                source_id="FinraPublishedSI",
                field_hints={
                    "published_short_interest": 22.5,
                    "research_admissibility": "RESEARCH_ADMISSIBLE",
                },
            )
        ]
    )
    from apps.research_screener.session_state import _not_configured

    fields = {
        "published_short_interest": _not_configured("missing", "SHORT_FLOAT_NOT_CONFIGURED")
    }
    merged = supplemental_fields("GME", fields, store)
    assert merged["published_short_interest"].value == 22.5
