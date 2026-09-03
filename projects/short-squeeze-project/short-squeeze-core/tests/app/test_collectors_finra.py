from __future__ import annotations

import time
from pathlib import Path

from apps.research_screener.collectors.finra_published_si import (
    FinraPublishedSICollector,
    parse_finra_daily_volume_text,
    parse_finra_si_text,
)
from apps.research_screener.collectors.models import CollectorRecord
from apps.research_screener.collectors.store import EvidenceStore


from datetime import UTC, datetime


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


def test_store_ttl_prunes_stale_records() -> None:
    store = EvidenceStore(default_ttl_s=1)
    store.set_source_ttl("Test", 1)
    old = CollectorRecord(
        symbol="AAA",
        payload={},
        received_at=_now_iso(),
        source_id="Test",
    )
    store.merge([old])
    assert store.get("AAA")
    time.sleep(1.1)
    assert store.get("AAA") == []


def test_parse_finra_si_fixture_shape() -> None:
    fixture = Path(__file__).resolve().parents[1] / "fixtures" / "collectors" / "finra_si_sample.txt"
    parsed = parse_finra_si_text(fixture.read_text(encoding="utf-8"))
    assert "TESTA" in parsed
    assert parsed["TESTA"]["short_shares"] == "2500000"


def test_finra_collector_poll_from_fixture() -> None:
    fixture = Path(__file__).resolve().parents[1] / "fixtures" / "collectors" / "finra_si_sample.txt"
    collector = FinraPublishedSICollector(
        enabled=True,
        fixture_path=str(fixture),
    )
    records = collector.poll(["TESTA"], force=True)
    assert len(records) == 1
    assert records[0].field_hints["finra_si_shares"] == 2_500_000
    assert records[0].field_hints["research_admissibility"] == "RESEARCH_ADMISSIBLE"


def test_parse_finra_daily_volume_pipe_file() -> None:
    text = "Date|Symbol|ShortVolume|...\n20260115|GME|1000|x\n"
    parsed = parse_finra_daily_volume_text(text)
    assert parsed["GME"]["short_volume"] == "1000"
