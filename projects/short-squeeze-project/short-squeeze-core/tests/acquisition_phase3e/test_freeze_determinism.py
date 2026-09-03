"""Phase 3A freeze determinism for Phase 3E (offline synthetic Batch 05)."""

from __future__ import annotations

from pathlib import Path

from squeeze_core.acquisition.phase3a_freeze.cli import generate, verify

ROOT = Path(__file__).resolve().parents[2]
SYNTHETIC_ROOT = ROOT / "tests" / "fixtures" / "acquisition" / "batch08" / "synthetic-batch05"


def test_phase3a_freeze_verify_round_trips_offline(tmp_path):
    out = tmp_path / "batch-08"
    assert generate(SYNTHETIC_ROOT, out) == 0
    assert verify(SYNTHETIC_ROOT, out) == 0


def test_phase3a_freeze_regeneration_is_byte_identical(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    generate(SYNTHETIC_ROOT, first)
    generate(SYNTHETIC_ROOT, second)
    left = sorted(item.relative_to(first) for item in first.rglob("*") if item.is_file())
    right = sorted(item.relative_to(second) for item in second.rglob("*") if item.is_file())
    assert left == right
    for relative in left:
        assert (first / relative).read_bytes() == (second / relative).read_bytes()
